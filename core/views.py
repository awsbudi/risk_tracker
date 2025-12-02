from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.db.models import Q, Min, Max
from django.contrib import messages
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import timedelta, datetime, date
import calendar
import openpyxl 
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Import Models & Forms
from .models import Proyek, Tugas, TemplateBAU 
from .forms import ProyekForm, TugasForm

# --- HELPER: ROLE CHECKER ---
def get_role(user):
    return user.profile.role if hasattr(user, 'profile') else 'MEMBER'

def is_admin(user):
    return user.is_superuser or get_role(user) == 'ADMIN'

def is_leader(user):
    return get_role(user) == 'LEADER'

def is_member(user):
    return get_role(user) == 'MEMBER'

# --- MIXINS ---
class GroupAccessMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser: 
            return qs
        return qs.filter(pemilik_grup=user.groups.first())

# --- DASHBOARD ---
@login_required
def dashboard(request):
    user = request.user
    group = user.groups.first()
    
    tasks = Tugas.objects.all()
    projects = Proyek.objects.all()
    
    if not user.is_superuser:
        if group:
            tasks = tasks.filter(pemilik_grup=group)
            projects = projects.filter(pemilik_grup=group)
        else:
            tasks = tasks.none()
            projects = projects.none()
    
    context = {
        'total_projects': projects.count(),
        'total_tasks': tasks.count(),
        'overdue_tasks': tasks.filter(status='OVERDUE').count(),
        'in_progress': tasks.filter(status='IN_PROGRESS').count(),
        'todo_count': tasks.filter(status='TODO').count(),
        'done_count': tasks.filter(status='DONE').count(),
        'user_role': get_role(user),
    }
    return render(request, 'core/dashboard.html', context)

# --- PROYEK VIEWS ---
class ProyekListView(LoginRequiredMixin, GroupAccessMixin, ListView):
    model = Proyek
    template_name = 'core/proyek_list.html'
    context_object_name = 'proyek_list'

class ProyekCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Proyek
    form_class = ProyekForm
    template_name = 'core/proyek_form.html'
    success_url = reverse_lazy('proyek-list')
    
    def test_func(self):
        return is_admin(self.request.user) or is_leader(self.request.user)

    def form_valid(self, form):
        user_group = self.request.user.groups.first()
        if not user_group:
            form.add_error(None, "ERROR: User tidak punya grup.")
            return self.form_invalid(form)
        form.instance.pemilik_grup = user_group
        form.instance.dibuat_oleh = self.request.user
        return super().form_valid(form)

class ProyekUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Proyek
    form_class = ProyekForm
    template_name = 'core/proyek_form.html'
    success_url = reverse_lazy('proyek-list')

    def test_func(self):
        return is_admin(self.request.user)

class ProyekDetailView(LoginRequiredMixin, GroupAccessMixin, DetailView):
    model = Proyek
    template_name = 'core/proyek_detail.html'

class ProyekDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Proyek
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('proyek-list')
    def test_func(self): return is_admin(self.request.user)


# --- TUGAS VIEWS ---
class TugasListView(LoginRequiredMixin, GroupAccessMixin, ListView):
    model = Tugas
    template_name = 'core/tugas_list.html'
    context_object_name = 'tugas_list'
    
    def get_queryset(self): 
        return super().get_queryset().order_by('kode_tugas')

class TugasCreateView(LoginRequiredMixin, CreateView):
    model = Tugas
    form_class = TugasForm
    template_name = 'core/tugas_form.html'
    success_url = reverse_lazy('tugas-list')

    # Auto Fill Server Side (saat klik +)
    def get_initial(self):
        initial = super().get_initial()
        parent_id = self.request.GET.get('parent_id')
        if parent_id:
            try:
                parent_task = Tugas.objects.get(pk=parent_id)
                initial['induk'] = parent_task
                initial['proyek'] = parent_task.proyek 
                initial['tanggal_mulai'] = parent_task.tanggal_mulai
            except Tugas.DoesNotExist: pass
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user_group = self.request.user.groups.first()
        if not user_group:
            form.add_error(None, "ERROR: User tidak punya grup.")
            return self.form_invalid(form)
        form.instance.pemilik_grup = user_group
        return super().form_valid(form)

class TugasUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Tugas
    form_class = TugasForm
    template_name = 'core/tugas_form.html'
    success_url = reverse_lazy('tugas-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        obj = self.get_object()
        user = self.request.user
        if is_admin(user) or is_leader(user): return True 
        if is_member(user): return obj.ditugaskan_ke == user
        return False

class TugasDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Tugas
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('tugas-list')
    def test_func(self): return is_admin(self.request.user)


# --- API HELPERS (Dates, Gantt, Progress) ---

@login_required
def get_entity_dates_api(request):
    entity_type = request.GET.get('type')
    entity_id = request.GET.get('id')
    
    data = {}
    try:
        if entity_type == 'project' and entity_id:
            obj = Proyek.objects.get(pk=entity_id)
            data['start_date'] = obj.tanggal_mulai
            data['end_date'] = obj.tanggal_selesai
        elif entity_type == 'task' and entity_id:
            obj = Tugas.objects.get(pk=entity_id)
            data['start_date'] = obj.tanggal_mulai
            data['end_date'] = obj.tenggat_waktu
            
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def update_progress_api(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_progress = int(data.get('progress', 0))
            task = get_object_or_404(Tugas, pk=pk)
            
            task.progress = new_progress
            if new_progress == 100: task.status = 'DONE'
            elif new_progress > 0 and task.status == 'TODO': task.status = 'IN_PROGRESS'
            elif new_progress == 0: task.status = 'TODO'
            
            task.save()
            return JsonResponse({'status': 'success', 'new_status': task.get_status_display()})
        except Exception as e: return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)

@login_required
def update_task_date_api(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            start_str = data.get('start')
            end_str = data.get('end')

            new_start = datetime.strptime(start_str, "%Y-%m-%d").date()
            new_end = datetime.strptime(end_str, "%Y-%m-%d").date()

            user = request.user
            if not (user.is_superuser or is_admin(user) or is_leader(user)):
                task_check = get_object_or_404(Tugas, pk=pk)
                if task_check.ditugaskan_ke != user:
                     return JsonResponse({'error': 'Permission denied'}, status=403)

            task = get_object_or_404(Tugas, pk=pk)
            task.tanggal_mulai = new_start
            task.tenggat_waktu = new_end
            task.save()

            # Cascade Logic
            def push_dependents(parent_task):
                dependents = Tugas.objects.filter(tergantung_pada=parent_task)
                for child in dependents:
                    if child.tanggal_mulai <= parent_task.tenggat_waktu:
                        duration = child.tenggat_waktu - child.tanggal_mulai
                        child.tanggal_mulai = parent_task.tenggat_waktu
                        child.tenggat_waktu = child.tanggal_mulai + duration
                        child.save()
                        push_dependents(child)

            push_dependents(task)

            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)


# --- VISUALIZATION VIEWS (NO FILTER) ---

@login_required
def gantt_data(request):
    user = request.user
    group = user.groups.first()
    tasks = Tugas.objects.all()
    projects = Proyek.objects.all()
    
    if not user.is_superuser:
        if group:
            tasks = tasks.filter(pemilik_grup=group)
            projects = projects.filter(pemilik_grup=group)
        else: return JsonResponse([], safe=False)
    
    # FILTER LOGIC DIHAPUS (DROP)
    
    data = []
    for p in projects:
        data.append({
            'id': f"PROJ-{p.id}", 'name': f"📁 {p.nama_proyek}",
            'start': p.tanggal_mulai.strftime('%Y-%m-%d'), 'end': p.tanggal_selesai.strftime('%Y-%m-%d'),
            'progress': 0, 'dependencies': "", 'custom_class': 'bar-project'
        })
    for t in tasks:
        dep = str(t.tergantung_pada.id) if t.tergantung_pada else ""
        data.append({
            'id': str(t.id), 'name': t.nama_tugas,
            'start': t.tanggal_mulai.strftime('%Y-%m-%d'), 'end': t.tenggat_waktu.strftime('%Y-%m-%d'),
            'progress': t.progress, 'dependencies': dep
        })
    return JsonResponse(data, safe=False)

@login_required
def gantt_view(request):
    return render(request, 'core/gantt.html')


# --- EXPORT EXCEL VISUAL GANTT (NO FILTER) ---
@login_required
def export_gantt_excel(request):
    user = request.user
    group = user.groups.first()
    tasks = Tugas.objects.all()
    
    if not user.is_superuser:
        if group: tasks = tasks.filter(pemilik_grup=group)
        else: return HttpResponseForbidden("Anda tidak punya grup.")
    
    # Filter Dihapus, Otomatis deteksi range dari seluruh data
    global_start = None
    global_end = None

    if tasks.exists():
        global_start = tasks.aggregate(Min('tanggal_mulai'))['tanggal_mulai__min']
        global_end = tasks.aggregate(Max('tenggat_waktu'))['tenggat_waktu__max']

    if not global_start: global_start = date.today()
    if not global_end: global_end = date.today() + timedelta(days=30)
    
    # Safety Check: Jangan sampai kolomnya ribuan (max 1 tahun)
    if (global_end - global_start).days > 365:
        global_end = global_start + timedelta(days=365)

    # Setup Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gantt Visual"

    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    bar_fill_todo = PatternFill(start_color="3498DB", end_color="3498DB", fill_type="solid")
    bar_fill_done = PatternFill(start_color="2ECC71", end_color="2ECC71", fill_type="solid")
    bar_fill_overdue = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
    bar_fill_progress = PatternFill(start_color="F1C40F", end_color="F1C40F", fill_type="solid")
    
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    ws['A1'] = "PROJECT GANTT CHART"
    ws['A1'].font = Font(bold=True, size=16)
    ws['A2'] = "Laporan Seluruh Tugas"
    
    # Header Kiri
    data_headers = ["KODE", "NAMA TUGAS", "PIC", "START", "END"]
    for idx, h in enumerate(data_headers, 1):
        cell = ws.cell(row=4, column=idx)
        cell.value = h
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Header Kanan (Timeline)
    timeline_start_col = 6
    current_date = global_start
    col_idx = timeline_start_col
    
    while current_date <= global_end:
        cell = ws.cell(row=4, column=col_idx)
        cell.value = current_date.day
        cell.font = Font(size=9, bold=True)
        cell.alignment = Alignment(horizontal="center")
        
        if current_date.weekday() >= 5: 
            cell.fill = PatternFill(start_color="ECF0F1", end_color="ECF0F1", fill_type="solid")

        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 3.5
        
        current_date += timedelta(days=1)
        col_idx += 1

    # Isi Data
    row_idx = 5
    for t in tasks:
        ws.cell(row=row_idx, column=1).value = t.kode_tugas
        ws.cell(row=row_idx, column=2).value = t.nama_tugas
        ws.cell(row=row_idx, column=3).value = t.ditugaskan_ke.username if t.ditugaskan_ke else "-"
        ws.cell(row=row_idx, column=4).value = t.tanggal_mulai
        ws.cell(row=row_idx, column=5).value = t.tenggat_waktu
        
        # Gambar Bar
        t_start = max(t.tanggal_mulai, global_start)
        t_end = min(t.tenggat_waktu, global_end)
        
        if t_end >= t_start:
            start_offset = (t_start - global_start).days
            duration_days = (t_end - t_start).days + 1
            
            col_start = timeline_start_col + start_offset
            col_end = col_start + duration_days
            
            fill_color = bar_fill_todo
            if t.status == 'DONE': fill_color = bar_fill_done
            elif t.status == 'OVERDUE': fill_color = bar_fill_overdue
            elif t.status == 'IN_PROGRESS': fill_color = bar_fill_progress
            
            for c in range(col_start, col_end):
                cell = ws.cell(row=row_idx, column=c)
                cell.fill = fill_color
                cell.border = thin_border

        row_idx += 1

    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 35
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Gantt_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response


# --- BAU / ROUTINE TASKS ---
class TemplateBAUListView(LoginRequiredMixin, GroupAccessMixin, ListView):
    model = TemplateBAU
    template_name = 'core/bau_list.html'
    context_object_name = 'bau_list'

class TemplateBAUCreateView(LoginRequiredMixin, CreateView):
    model = TemplateBAU
    fields = ['nama_tugas', 'deskripsi', 'frekuensi', 'default_pic']
    template_name = 'core/bau_form.html'
    success_url = reverse_lazy('bau-list')
    def form_valid(self, form):
        user_group = self.request.user.groups.first()
        if not user_group:
            form.add_error(None, "User tidak punya grup.")
            return self.form_invalid(form)
        form.instance.pemilik_grup = user_group
        return super().form_valid(form)

@login_required
def trigger_bau_generation(request):
    if not (request.user.is_superuser or is_admin(request.user) or is_leader(request.user)):
        messages.error(request, "Anda tidak memiliki izin menjalankan generator.")
        return redirect('bau-list')
    try:
        call_command('generate_bau')
        messages.success(request, "Tugas rutin berhasil digenerate! Cek Daftar Tugas.")
    except Exception as e: messages.error(request, f"Gagal generate: {str(e)}")
    return redirect('bau-list')


# --- CALENDAR (OPSIONAL) ---
@login_required
def calendar_view(request):
    return render(request, 'core/calendar.html')

@login_required
def calendar_data(request):
    user = request.user
    group = user.groups.first()
    tasks = Tugas.objects.all()
    if not user.is_superuser:
        if group: tasks = tasks.filter(pemilik_grup=group)
        else: return JsonResponse([], safe=False)
    events = []
    for t in tasks:
        color = '#3788d8'
        if t.status == 'DONE': color = '#198754'
        elif t.status == 'OVERDUE': color = '#dc3545'
        elif t.status == 'IN_PROGRESS': color = '#ffc107'
        events.append({
            'title': f"{t.kode_tugas} - {t.nama_tugas}",
            'start': t.tenggat_waktu.strftime('%Y-%m-%d'),
            'url': f"/tugas/{t.id}/edit/",
            'backgroundColor': color, 'borderColor': color
        })
    return JsonResponse(events, safe=False)
