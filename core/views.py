from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.db.models import Q, Count
from django.contrib import messages
import json
from datetime import timedelta, datetime, date
import calendar
import openpyxl 
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import Proyek, Tugas, TemplateBAU, AuditLog, User
from .forms import ProyekForm, TugasForm, ImportTugasForm

# --- HELPER (Tetap) ---
def log_activity(user, action, model_name, obj_id, details):
    AuditLog.objects.create(user=user, action=action, target_model=model_name, target_id=str(obj_id), details=details)

def get_role(user): return user.profile.role if hasattr(user, 'profile') else 'MEMBER'
def is_admin(user): return user.is_superuser or get_role(user) == 'ADMIN'
def is_leader(user): return get_role(user) == 'LEADER'
def is_member(user): return get_role(user) == 'MEMBER'

class GroupAccessMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser: return qs
        user_groups = user.groups.all()
        if self.model == Tugas:
            return qs.filter(Q(pemilik_grup__in=user_groups) | Q(ditugaskan_ke=user)).distinct()
        return qs.filter(pemilik_grup__in=user_groups).distinct()

@login_required
def dashboard(request):
    user = request.user
    if user.is_superuser:
        tasks = Tugas.objects.all()
        projects = Proyek.objects.all()
    else:
        user_groups = user.groups.all()
        tasks = Tugas.objects.filter(Q(pemilik_grup__in=user_groups) | Q(ditugaskan_ke=user)).distinct()
        projects = Proyek.objects.filter(pemilik_grup__in=user_groups).distinct()
    
    assignee_id = request.GET.get('assignee')
    if assignee_id: tasks = tasks.filter(ditugaskan_ke_id=assignee_id)

    context = {
        'total_projects': projects.count(),
        'total_tasks': tasks.count(),
        'overdue_tasks': tasks.filter(status='OVERDUE').count(),
        'in_progress': tasks.filter(status='IN_PROGRESS').count(),
        'todo_count': tasks.filter(status='TODO').count(),
        'done_count': tasks.filter(status='DONE').count(),
        'on_hold_count': tasks.filter(status='ON_HOLD').count(), 
        'drop_count': tasks.filter(status='DROP').count(),
        'user_role': get_role(user),
        'team_members': User.objects.filter(groups__in=user.groups.all()).distinct() if not user.is_superuser else User.objects.all()
    }
    return render(request, 'core/dashboard.html', context)

# --- PROYEK VIEWS (Tetap) ---
class ProyekListView(LoginRequiredMixin, GroupAccessMixin, ListView):
    model = Proyek
    template_name = 'core/proyek_list.html'
    context_object_name = 'proyek_list'

class ProyekCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Proyek
    form_class = ProyekForm
    template_name = 'core/proyek_form.html'
    success_url = reverse_lazy('proyek-list')
    def test_func(self): return is_admin(self.request.user) or is_leader(self.request.user)
    def form_valid(self, form):
        user_group = self.request.user.groups.first()
        if not user_group:
            form.add_error(None, "User tidak punya grup.")
            return self.form_invalid(form)
        form.instance.pemilik_grup = user_group
        form.instance.dibuat_oleh = self.request.user
        resp = super().form_valid(form)
        log_activity(self.request.user, 'CREATE', 'Proyek', self.object.kode_proyek, f"Created: {self.object.nama_proyek}")
        return resp

class ProyekUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Proyek
    form_class = ProyekForm
    template_name = 'core/proyek_form.html'
    success_url = reverse_lazy('proyek-list')
    def test_func(self): return is_admin(self.request.user)
    def form_valid(self, form):
        resp = super().form_valid(form)
        log_activity(self.request.user, 'UPDATE', 'Proyek', self.object.kode_proyek, "Updated details")
        return resp

class ProyekDetailView(LoginRequiredMixin, GroupAccessMixin, DetailView):
    model = Proyek
    template_name = 'core/proyek_detail.html'

class ProyekDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Proyek
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('proyek-list')
    def test_func(self): return is_admin(self.request.user)
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        log_activity(request.user, 'DELETE', 'Proyek', obj.kode_proyek, f"Deleted: {obj.nama_proyek}")
        return super().delete(request, *args, **kwargs)

# --- IMPORT & DOWNLOAD TEMPLATE (UPDATED FIX) ---
@login_required
def download_template_tugas(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=Template_Import_Tugas.xlsx'
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Tugas"
    
    headers = ['Nama Tugas', 'Tipe Tugas', 'Kode Proyek', 'Pemberi Tugas', 'Username PIC', 'Start Date', 'End Date', 'Deskripsi']
    ws.append(headers)
    
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    
    # Contoh data valid (Senin-Jumat)
    sample_data = [
        ['Laporan Keuangan Q1', 'ADHOC', '', 'Pak Direktur', request.user.username, '2025-02-03', '2025-02-07', 'Contoh Adhoc'],
        ['Integrasi API', 'PROJECT', 'P-001', '', '', '2025-02-10', '2025-02-14', 'Contoh Project'],
    ]
    for row in sample_data: ws.append(row)
    
    for column in ws.columns:
        max_length = 0
        column = [cell for cell in column]
        for cell in column:
            try:
                if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
            except: pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[get_column_letter(column[0].column)].width = adjusted_width

    wb.save(response)
    return response

@login_required
def import_tugas(request):
    if not (is_admin(request.user) or is_leader(request.user)):
        return HttpResponseForbidden("Anda tidak memiliki akses untuk import data.")

    if request.method == 'POST':
        form = ImportTugasForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file_excel']
            try:
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                success_count = 0
                errors = []
                
                # Iterasi Baris
                for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    if not row[0]: continue 
                    
                    try:
                        # 1. Parsing Data
                        nama_tugas = row[0]
                        tipe_tugas = row[1].upper().strip() if row[1] else 'ADHOC'
                        kode_proyek = row[2]
                        pemberi_tugas = row[3] or request.user.get_full_name() or request.user.username
                        pic_username = row[4]
                        
                        # 2. Parsing Tanggal (Robust)
                        def parse_date(d):
                            if isinstance(d, datetime): return d.date()
                            if isinstance(d, date): return d
                            if isinstance(d, str):
                                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                                    try: return datetime.strptime(d.strip(), fmt).date()
                                    except: continue
                            return None

                        start_date = parse_date(row[5])
                        end_date = parse_date(row[6])

                        if not start_date or not end_date:
                            raise ValueError("Format tanggal salah. Gunakan YYYY-MM-DD.")

                        # 3. Validasi
                        if tipe_tugas not in ['PROJECT', 'ADHOC', 'BAU']:
                            raise ValueError(f"Tipe tugas '{tipe_tugas}' tidak valid.")

                        proyek_obj = None
                        if tipe_tugas == 'PROJECT':
                            if not kode_proyek: raise ValueError("Tugas PROJECT wajib isi Kode Proyek.")
                            proyek_obj = Proyek.objects.filter(kode_proyek=kode_proyek).first()
                            if not proyek_obj: raise ValueError(f"Proyek {kode_proyek} tidak ditemukan.")

                        pic_user = None
                        if pic_username:
                            pic_user = User.objects.filter(username=pic_username).first()

                        # 4. Validasi Weekend (Penyebab data ke-2 Anda gagal)
                        if start_date.weekday() >= 5: # 5=Sabtu, 6=Minggu
                            raise ValueError(f"Tanggal Mulai {start_date} adalah hari libur (Sabtu/Minggu).")

                        # 5. Create
                        Tugas.objects.create(
                            nama_tugas=nama_tugas,
                            tipe_tugas=tipe_tugas,
                            proyek=proyek_obj,
                            pemberi_tugas=pemberi_tugas,
                            ditugaskan_ke=pic_user,
                            tanggal_mulai=start_date,
                            tenggat_waktu=end_date,
                            pemilik_grup=request.user.groups.first(),
                            status='TODO',
                            progress=0
                        )
                        success_count += 1
                        
                    except Exception as e:
                        errors.append(f"Baris {idx} ({row[0] if row[0] else 'Unknown'}): {str(e)}")
                
                # Feedback User
                if success_count > 0:
                    messages.success(request, f"Sukses import {success_count} tugas.")
                
                if errors:
                    # Tampilkan list error secara detail
                    error_msg = f"<b>{len(errors)} data gagal diimport:</b><br><ul class='mb-0 text-start'>"
                    for err in errors[:10]: # Max 10 error agar tidak spam
                        error_msg += f"<li>{err}</li>"
                    if len(errors) > 10: error_msg += "<li>... dan lainnya.</li>"
                    error_msg += "</ul>"
                    messages.warning(request, error_msg)
                
                return redirect('tugas-list')
            except Exception as e:
                messages.error(request, f"File Excel rusak/tidak valid: {str(e)}")
    else:
        form = ImportTugasForm()

    return render(request, 'core/import_tugas.html', {'form': form})

# --- TUGAS VIEWS (Standard) ---
class TugasListView(LoginRequiredMixin, GroupAccessMixin, ListView):
    model = Tugas
    template_name = 'core/tugas_list.html'
    context_object_name = 'tugas_list'
    def get_queryset(self):
        qs = super().get_queryset()
        assignee_id = self.request.GET.get('assignee')
        if assignee_id: qs = qs.filter(ditugaskan_ke_id=assignee_id)
        return qs.order_by('kode_tugas')

class TugasCreateView(LoginRequiredMixin, CreateView):
    model = Tugas
    form_class = TugasForm
    template_name = 'core/tugas_form.html'
    success_url = reverse_lazy('tugas-list')
    
    def get_initial(self):
        initial = super().get_initial()
        initial['pemberi_tugas'] = self.request.user.get_full_name() or self.request.user.username
        parent_id = self.request.GET.get('parent_id')
        if parent_id:
            try:
                parent = Tugas.objects.get(pk=parent_id)
                initial['induk'] = parent
                initial['proyek'] = parent.proyek 
                initial['tanggal_mulai'] = parent.tanggal_mulai
            except: pass
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user 
        return kwargs

    def form_valid(self, form):
        user_group = self.request.user.groups.first()
        if not user_group:
            form.add_error(None, "User tidak punya grup.")
            return self.form_invalid(form)
        form.instance.pemilik_grup = user_group
        resp = super().form_valid(form)
        log_activity(self.request.user, 'CREATE', 'Tugas', self.object.kode_tugas, f"Created: {self.object.nama_tugas}")
        return resp

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
    
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status == 'DONE' and not request.user.is_superuser:
             messages.warning(request, "Tugas yang sudah SELESAI tidak dapat diedit.")
             return redirect('tugas-list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        resp = super().form_valid(form)
        if form.has_changed():
            log_activity(self.request.user, 'UPDATE', 'Tugas', self.object.kode_tugas, f"Changed: {', '.join(form.changed_data)}")
        return resp

class TugasDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Tugas
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('tugas-list')
    def test_func(self): return is_admin(self.request.user)
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        log_activity(request.user, 'DELETE', 'Tugas', obj.kode_tugas, f"Deleted: {obj.nama_tugas}")
        return super().delete(request, *args, **kwargs)

# --- API HELPERS (Tetap) ---
@login_required
def get_entity_dates_api(request):
    type_ = request.GET.get('type')
    id_ = request.GET.get('id')
    data = {}
    try:
        if type_ == 'project' and id_:
            obj = Proyek.objects.get(pk=id_)
            data['start_date'] = obj.tanggal_mulai
            data['end_date'] = obj.tanggal_selesai
        elif type_ == 'task' and id_:
            obj = Tugas.objects.get(pk=id_)
            data['start_date'] = obj.tanggal_mulai
            data['end_date'] = obj.tenggat_waktu
        return JsonResponse(data)
    except: return JsonResponse({}, status=400)

@login_required
def update_progress_api(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_prog = int(data.get('progress', 0))
            task = get_object_or_404(Tugas, pk=pk)
            task.progress = new_prog
            if new_prog == 100: task.status = 'DONE'
            elif new_prog > 0 and task.status == 'TODO': task.status = 'IN_PROGRESS'
            elif new_prog == 0: task.status = 'TODO'
            task.save()
            log_activity(request.user, 'UPDATE', 'Tugas', task.kode_tugas, f"Progress: {new_prog}%")
            return JsonResponse({'status': 'success', 'new_status': task.get_status_display()})
        except Exception as e: return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)

@login_required
def update_task_date_api(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            start_str, end_str = data.get('start'), data.get('end')
            new_start = datetime.strptime(start_str, "%Y-%m-%d").date()
            new_end = datetime.strptime(end_str, "%Y-%m-%d").date()
            
            # UAT: Validasi Sabtu Minggu (Actual Drag di Gantt)
            if new_start.weekday() >= 5:
                return JsonResponse({'error': 'Tanggal Mulai tidak boleh hari libur (Sabtu/Minggu)!'}, status=400)
                
            task = get_object_or_404(Tugas, pk=pk)
            # Permission check
            if not (request.user.is_superuser or is_admin(request.user) or is_leader(request.user) or task.ditugaskan_ke == request.user):
                return JsonResponse({'error': 'Permission denied'}, status=403)
            
            task.tanggal_mulai = new_start
            task.tenggat_waktu = new_end
            task.save()
            log_activity(request.user, 'UPDATE', 'Tugas', task.kode_tugas, f"Gantt: {new_start} -> {new_end}")
            return JsonResponse({'status': 'success'})
        except Exception as e: return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# --- GANTT & REPORT (Tetap) ---
@login_required
def gantt_data(request):
    user = request.user
    if user.is_superuser: all_tasks = Tugas.objects.all()
    else:
        user_groups = user.groups.all()
        all_tasks = Tugas.objects.filter(Q(pemilik_grup__in=user_groups) | Q(ditugaskan_ke=user)).distinct()
    
    assignee_id = request.GET.get('assignee')
    if assignee_id: all_tasks = all_tasks.filter(ditugaskan_ke_id=assignee_id)

    visible_task_ids = set(all_tasks.values_list('id', flat=True))
    gantt_list = []
    
    def get_custom_html(t):
        act_start = t.tanggal_mulai_aktual.strftime('%d/%m') if t.tanggal_mulai_aktual else "-"
        act_end = t.tanggal_selesai_aktual.strftime('%d/%m') if t.tanggal_selesai_aktual else "-"
        return f"Plan: {t.tanggal_mulai.strftime('%d/%m')} - {t.tenggat_waktu.strftime('%d/%m')}<br>Act: {act_start} - {act_end}"

    def get_custom_class(t):
        if t.status == 'DONE': return 'bar-done' 
        if t.status == 'OVERDUE': return 'bar-overdue'
        if t.status == 'ON_HOLD': return 'bar-hold' 
        return ''

    projects = Proyek.objects.filter(id__in=all_tasks.values_list('proyek_id', flat=True)).distinct().order_by('kode_proyek')
    
    for p in projects:
        gantt_list.append({
            'id': f"PROJ-{p.id}", 'name': f"📁 {p.nama_proyek}", 
            'start': str(p.tanggal_mulai), 'end': str(p.tanggal_selesai), 
            'progress': 0, 'custom_class': 'bar-project', 'read_only': True
        })
        project_tasks = all_tasks.filter(proyek=p).order_by('kode_tugas')
        for t in project_tasks:
            dep = ""
            if t.tergantung_pada and t.tergantung_pada.id in visible_task_ids: dep = str(t.tergantung_pada.id)
            gantt_list.append({
                'id': str(t.id), 'name': t.nama_tugas, 'start': str(t.tanggal_mulai), 'end': str(t.tenggat_waktu),
                'progress': t.progress, 'dependencies': dep, 'custom_class': get_custom_class(t), 'custom_html': get_custom_html(t)
            })
    
    orphans = all_tasks.filter(proyek__isnull=True)
    bau_tasks = orphans.filter(tipe_tugas='BAU')
    regular_orphans = orphans.exclude(tipe_tugas='BAU')
    
    for t in regular_orphans:
        dep = ""
        if t.tergantung_pada and t.tergantung_pada.id in visible_task_ids: dep = str(t.tergantung_pada.id)
        gantt_list.append({
            'id': str(t.id), 'name': t.nama_tugas, 'start': str(t.tanggal_mulai), 'end': str(t.tenggat_waktu),
            'progress': t.progress, 'dependencies': dep, 'custom_class': get_custom_class(t), 'custom_html': get_custom_html(t)
        })

    bau_groups = {}
    for t in bau_tasks:
        parts = t.kode_tugas.split('-')
        if len(parts) >= 3: 
            tid = parts[1] 
            if tid not in bau_groups: 
                bau_groups[tid] = {'name': t.nama_tugas.split('(')[0], 'start': t.tanggal_mulai, 'end': t.tenggat_waktu, 'p': t.progress, 'c': 1}
            else:
                g = bau_groups[tid]
                g['start'] = min(g['start'], t.tanggal_mulai)
                g['end'] = max(g['end'], t.tenggat_waktu)
                g['p'] += t.progress
                g['c'] += 1
    
    for k,v in bau_groups.items():
        gantt_list.append({
            'id': f"BAU_{k}", 'name': f"🔄 {v['name']}", 'start': str(v['start']), 'end': str(v['end']), 'progress': v['p']/v['c'], 'custom_class': 'bar-project', 'read_only': True
        })

    return JsonResponse(gantt_list, safe=False)

@login_required
def gantt_view(request): 
    team_members = User.objects.filter(groups__in=request.user.groups.all()).distinct() if not request.user.is_superuser else User.objects.all()
    return render(request, 'core/gantt.html', {'team_members': team_members})

@login_required
def export_gantt_excel(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Gantt.xlsx'
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gantt Data"
    ws.append(['Kode', 'Tugas', 'Plan Start', 'Plan End', 'Actual Start', 'Actual End', 'Status', 'PIC', 'Pemberi Tugas'])
    
    tasks = Tugas.objects.all()
    for t in tasks:
        ws.append([
            t.kode_tugas, t.nama_tugas, t.tanggal_mulai, t.tenggat_waktu,
            t.tanggal_mulai_aktual, t.tanggal_selesai_aktual, t.get_status_display(),
            t.ditugaskan_ke.username if t.ditugaskan_ke else '-',
            t.pemberi_tugas or '-'
        ])
    wb.save(response)
    return response

# --- BAU VIEWS & Calendar (Tetap) ---
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

class TemplateBAUUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = TemplateBAU
    fields = ['nama_tugas', 'deskripsi', 'frekuensi', 'default_pic']
    template_name = 'core/bau_form.html'
    success_url = reverse_lazy('bau-list')
    def test_func(self): return is_admin(self.request.user)

class TemplateBAUDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = TemplateBAU
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('bau-list')
    def test_func(self): return is_admin(self.request.user)

@login_required
def trigger_bau_single(request, pk): return redirect('bau-list')

@login_required
def calendar_view(request): return render(request, 'core/calendar.html')
@login_required
def calendar_data(request):
    user = request.user
    if user.is_superuser: tasks = Tugas.objects.all()
    else:
        user_groups = user.groups.all()
        tasks = Tugas.objects.filter(Q(pemilik_grup__in=user_groups) | Q(ditugaskan_ke=user)).distinct()
    
    events = []
    for t in tasks:
        color = '#3788d8'
        if t.status == 'DONE': color = '#198754'
        elif t.status == 'OVERDUE': color = '#dc3545'
        events.append({'title': t.nama_tugas, 'start': str(t.tenggat_waktu), 'backgroundColor': color})
    return JsonResponse(events, safe=False)