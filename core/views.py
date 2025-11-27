from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from django.contrib import messages
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import timedelta, datetime, date
import calendar

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
    def test_func(self): return is_admin(self.request.user) or is_leader(self.request.user)
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
    def test_func(self): return is_admin(self.request.user)

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
    def get_queryset(self): return super().get_queryset().order_by('kode_tugas')

class TugasCreateView(LoginRequiredMixin, CreateView):
    model = Tugas
    form_class = TugasForm
    template_name = 'core/tugas_form.html'
    success_url = reverse_lazy('tugas-list')
    def get_initial(self):
        initial = super().get_initial()
        parent_id = self.request.GET.get('parent_id')
        if parent_id:
            try:
                parent_task = Tugas.objects.get(pk=parent_id)
                initial['induk'] = parent_task
                initial['proyek'] = parent_task.proyek
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

# --- API HELPERS (Gantt & Progress) ---

@login_required
def update_progress_api(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_progress = int(data.get('progress', 0))
            task = get_object_or_404(Tugas, pk=pk)
            # Permission check (simplified)
            task.progress = new_progress
            if new_progress == 100: task.status = 'DONE'
            elif new_progress > 0 and task.status == 'TODO': task.status = 'IN_PROGRESS'
            elif new_progress == 0: task.status = 'TODO'
            task.save()
            return JsonResponse({'status': 'success', 'new_status': task.get_status_display()})
        except Exception as e: return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)

# --- NEW: API UPDATE TANGGAL GANTT (INTERACTIVE) ---
@login_required
def update_task_date_api(request, pk):
    """
    API untuk mengupdate tanggal tugas saat digeser di Gantt Chart.
    Juga melakukan 'Cascade Update' ke tugas yang tergantung padanya.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            start_str = data.get('start')
            end_str = data.get('end')

            # Parsing tanggal (Format dari Frappe Gantt biasanya YYYY-MM-DD)
            new_start = datetime.strptime(start_str, "%Y-%m-%d").date()
            new_end = datetime.strptime(end_str, "%Y-%m-%d").date()

            # Validasi permission sederhana
            user = request.user
            if not (user.is_superuser or is_admin(user) or is_leader(user)):
                # Member hanya boleh edit tugas sendiri
                task_check = get_object_or_404(Tugas, pk=pk)
                if task_check.ditugaskan_ke != user:
                     return JsonResponse({'error': 'Permission denied'}, status=403)

            # Update Tugas Utama
            task = get_object_or_404(Tugas, pk=pk)
            task.tanggal_mulai = new_start
            task.tenggat_waktu = new_end
            task.save()

            # --- LOGIC CASCADE (EFEK DOMINO) ---
            # Cari semua tugas yang tergantung pada tugas ini
            # Logic: Jika A bergeser, B (yang depend ke A) harus mulai SETELAH A selesai.
            
            def push_dependents(parent_task):
                dependents = Tugas.objects.filter(tergantung_pada=parent_task)
                for child in dependents:
                    # Jika Tanggal Mulai Child < Tanggal Selesai Parent (Tumpang Tindih)
                    # Maka geser Child ke depan
                    if child.tanggal_mulai <= parent_task.tenggat_waktu:
                        # Hitung durasi asli child agar panjang bar tetap sama
                        duration = child.tenggat_waktu - child.tanggal_mulai
                        
                        # Set Mulai Child = Selesai Parent (atau +1 hari jika mau strict)
                        # Di sini kita set sama persis (Finish-to-Start 0 lag)
                        child.tanggal_mulai = parent_task.tenggat_waktu
                        child.tenggat_waktu = child.tanggal_mulai + duration
                        child.save()
                        
                        # Rekursif: Cek lagi anak-anak dari child ini
                        push_dependents(child)

            push_dependents(task)

            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)

# --- VISUALIZATION VIEWS ---
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
    
    data = []
    # Proyek (Read only visuals)
    for p in projects:
        data.append({
            'id': f"PROJ-{p.id}", 'name': f"📁 {p.nama_proyek}",
            'start': p.tanggal_mulai.strftime('%Y-%m-%d'), 'end': p.tanggal_selesai.strftime('%Y-%m-%d'),
            'progress': 0, 'dependencies': "", 'custom_class': 'bar-project'
        })
    # Tugas (Editable)
    for t in tasks:
        dep = str(t.tergantung_pada.id) if t.tergantung_pada else ""
        data.append({
            'id': str(t.id), 'name': t.nama_tugas,
            'start': t.tanggal_mulai.strftime('%Y-%m-%d'), 'end': t.tenggat_waktu.strftime('%Y-%m-%d'),
            'progress': t.progress, 'dependencies': dep
        })
    return JsonResponse(data, safe=False)

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

# --- BAU ---
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