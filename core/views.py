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

# ... (HELPER & MIXINS TETAP SAMA, TIDAK DIUBAH) ...
def get_role(user): return user.profile.role if hasattr(user, 'profile') else 'MEMBER'
def is_admin(user): return user.is_superuser or get_role(user) == 'ADMIN'
def is_leader(user): return get_role(user) == 'LEADER'
def is_member(user): return get_role(user) == 'MEMBER'

class GroupAccessMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser: return qs
        return qs.filter(pemilik_grup=user.groups.first())

# --- DASHBOARD, PROYEK, TUGAS, BAU VIEWS TETAP SAMA ---
# (Pastikan kode Dashboard, ProyekListView, TugasCreateView dll TETAP ADA di sini)
# Agar tidak kepanjangan, saya hanya tulis bagian yang BERUBAH di bawah ini.
# Copy-paste bagian atas file lama Anda, lalu GANTI bagian "VISUALIZATION VIEWS" ke bawah.

# ... (KODE LAMA ...)

@login_required
def dashboard(request):
    # ... (Isi dashboard sama) ...
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

# ... (Proyek & Tugas Views tetap sama) ...
# ... (API Helpers tetap sama) ...
# ... (Pastikan update_task_date_api dan get_entity_dates_api ada) ...

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
    except Exception as e: return JsonResponse({'error': str(e)}, status=400)

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
                if task_check.ditugaskan_ke != user: return JsonResponse({'error': 'Permission denied'}, status=403)
            task = get_object_or_404(Tugas, pk=pk)
            task.tanggal_mulai = new_start
            task.tenggat_waktu = new_end
            task.save()
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
        except Exception as e: return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)

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

# --- VISUALIZATION VIEWS (FIXED) ---

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
    
    # FILTER LOGIC (Fixed)
    start_filter = request.GET.get('start')
    end_filter = request.GET.get('end')
    
    if start_filter and end_filter:
        try:
            filter_start = datetime.strptime(start_filter, "%Y-%m-%d").date()
            filter_end = datetime.strptime(end_filter, "%Y-%m-%d").date()
            # Overlap Logic: (StartA <= EndB) and (EndA >= StartB)
            tasks = tasks.filter(tanggal_mulai__lte=filter_end, tenggat_waktu__gte=filter_start)
            projects = projects.filter(tanggal_mulai__lte=filter_end, tanggal_selesai__gte=filter_start)
        except ValueError: pass

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

# --- NEW: EXPORT EXCEL VISUAL GANTT ---
@login_required
def export_gantt_excel(request):
    user = request.user
    group = user.groups.first()
    tasks = Tugas.objects.all()
    
    if not user.is_superuser:
        if group: tasks = tasks.filter(pemilik_grup=group)
        else: return HttpResponseForbidden("Anda tidak punya grup.")
    
    # 1. Tentukan Range Tanggal Laporan
    start_filter = request.GET.get('start')
    end_filter = request.GET.get('end')
    filter_info = "Semua Periode"
    
    global_start = None
    global_end = None

    # Terapkan Filter
    if start_filter and end_filter:
        try:
            filter_start = datetime.strptime(start_filter, "%Y-%m-%d").date()
            filter_end = datetime.strptime(end_filter, "%Y-%m-%d").date()
            tasks = tasks.filter(tanggal_mulai__lte=filter_end, tenggat_waktu__gte=filter_start)
            filter_info = f"Periode: {start_filter} s/d {end_filter}"
            
            # Gunakan filter sebagai batas chart
            global_start = filter_start
            global_end = filter_end
        except ValueError: pass
    
    # Jika tidak ada filter, cari Min/Max dari data
    if not global_start and tasks.exists():
        global_start = tasks.aggregate(Min('tanggal_mulai'))['tanggal_mulai__min']
        global_end = tasks.aggregate(Max('tenggat_waktu'))['tenggat_waktu__max']

    # Fallback jika data kosong
    if not global_start: global_start = date.today()
    if not global_end: global_end = date.today() + timedelta(days=30)
    
    # Safety: Batasi Max 365 hari agar Excel tidak error
    if (global_end - global_start).days > 365:
        global_end = global_start + timedelta(days=365)

    # 2. Setup Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gantt Visual"

    # Style Definitions
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    # Warna Bar Tugas
    bar_fill_todo = PatternFill(start_color="3498DB", end_color="3498DB", fill_type="solid") # Biru Muda
    bar_fill_done = PatternFill(start_color="2ECC71", end_color="2ECC71", fill_type="solid") # Hijau
    bar_fill_overdue = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid") # Merah
    bar_fill_progress = PatternFill(start_color="F1C40F", end_color="F1C40F", fill_type="solid") # Kuning
    
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    # Judul Laporan
    ws['A1'] = "PROJECT GANTT CHART"
    ws['A1'].font = Font(bold=True, size=16)
    ws['A2'] = filter_info
    
    # --- HEADER TABEL (Kiri) ---
    data_headers = ["KODE", "NAMA TUGAS", "PIC", "START", "END"]
    for idx, h in enumerate(data_headers, 1):
        cell = ws.cell(row=4, column=idx)
        cell.value = h
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # --- HEADER TIMELINE (Kanan) ---
    # Mulai dari Kolom F (Index 6)
    timeline_start_col = 6
    current_date = global_start
    col_idx = timeline_start_col
    
    while current_date <= global_end:
        cell = ws.cell(row=4, column=col_idx)
        cell.value = current_date.day # Tulis tanggal (1, 2, 3...)
        cell.font = Font(size=9, bold=True)
        cell.alignment = Alignment(horizontal="center")
        
        # Warna abu-abu untuk weekend (Sabtu/Minggu)
        if current_date.weekday() >= 5: 
            cell.fill = PatternFill(start_color="ECF0F1", end_color="ECF0F1", fill_type="solid")

        # Set lebar kolom jadi kecil agar terlihat seperti timeline bar
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 3.5
        
        current_date += timedelta(days=1)
        col_idx += 1

    # --- ISI DATA TUGAS ---
    row_idx = 5
    for t in tasks:
        # Isi Data Teks
        ws.cell(row=row_idx, column=1).value = t.kode_tugas
        ws.cell(row=row_idx, column=2).value = t.nama_tugas
        ws.cell(row=row_idx, column=3).value = t.ditugaskan_ke.username if t.ditugaskan_ke else "-"
        ws.cell(row=row_idx, column=4).value = t.tanggal_mulai
        ws.cell(row=row_idx, column=5).value = t.tenggat_waktu
        
        # --- LOGIC GAMBAR BAR VISUAL ---
        # Hitung overlap tugas dengan global range
        t_start = max(t.tanggal_mulai, global_start)
        t_end = min(t.tenggat_waktu, global_end)
        
        # Hanya gambar jika valid (End >= Start)
        if t_end >= t_start:
            # Hitung offset kolom
            start_offset = (t_start - global_start).days
            duration_days = (t_end - t_start).days + 1
            
            col_start = timeline_start_col + start_offset
            col_end = col_start + duration_days
            
            # Tentukan Warna Bar berdasarkan Status
            fill_color = bar_fill_todo
            if t.status == 'DONE': fill_color = bar_fill_done
            elif t.status == 'OVERDUE': fill_color = bar_fill_overdue
            elif t.status == 'IN_PROGRESS': fill_color = bar_fill_progress
            
            # Warnai Sel Excel
            for c in range(col_start, col_end):
                cell = ws.cell(row=row_idx, column=c)
                cell.fill = fill_color
                cell.border = thin_border

        row_idx += 1

    # Rapikan Lebar Kolom Data
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 35
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"Gantt_Visual_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response

# ... (Sisanya: gantt_view, calendar_view, dll sama persis seperti file lama Anda) ...
@login_required
def gantt_view(request): return render(request, 'core/gantt.html')
@login_required
def calendar_view(request): return render(request, 'core/calendar.html')
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

# ... (Kode BAU juga tetap sama) ...
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
        form.instance.pemilik_grup = self.request.user.groups.first()
        return super().form_valid(form)

@login_required
def trigger_bau_generation(request):
    if not (request.user.is_superuser or is_admin(request.user) or is_leader(request.user)):
        messages.error(request, "Anda tidak memiliki izin.")
        return redirect('bau-list')
    try:
        call_command('generate_bau')
        messages.success(request, "Tugas rutin berhasil digenerate!")
    except Exception as e: messages.error(request, f"Gagal: {str(e)}")
    return redirect('bau-list')
