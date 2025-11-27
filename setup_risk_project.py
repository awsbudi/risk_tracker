import os
import sys
import subprocess

# Konfigurasi Nama Proyek
PROJECT_NAME = "risk_tracker"
APP_NAME = "core"

def create_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    print(f"Created: {path}")

def run_command(command):
    print(f"Running: {command}")
    subprocess.check_call(command, shell=True)

# --- 1. STRUKTUR FILE DJANGO ---

# requirements.txt
requirements_content = """
Django>=5.0
gunicorn
psycopg2-binary
whitenoise
"""

# manage.py
manage_py_content = f"""
#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{PROJECT_NAME}.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
"""

# settings.py
settings_content = f"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-risk-management-dev-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    '{APP_NAME}',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{PROJECT_NAME}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

WSGI_APPLICATION = '{PROJECT_NAME}.wsgi.application'

DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }}
}}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'id-id' # Bahasa Indonesia
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
"""

# urls.py (Project Level)
urls_project_content = f"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('{APP_NAME}.urls')),
]
"""

# --- 2. APLIKASI CORE (Models, Views, dll) ---

# models.py
models_content = """
from django.db import models
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.utils import timezone

class Proyek(models.Model):
    kode_proyek = models.CharField(max_length=20, unique=True, editable=False)
    nama_proyek = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True)
    tanggal_mulai = models.DateField()
    tanggal_selesai = models.DateField()
    # Group/Divisi pemilik proyek (misal: Risk Mgmt, Compliance, dll)
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)
    
    dibuat_oleh = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        if not self.kode_proyek:
            last_id = Proyek.objects.all().order_by('id').last()
            new_id = last_id.id + 1 if last_id else 1
            self.kode_proyek = f"P-{{new_id:03d}}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kode_proyek} - {self.nama_proyek}"

class Tugas(models.Model):
    TIPE_CHOICES = [
        ('PROJECT', 'Proyek'),
        ('BAU', 'Business As Usual'),
        ('ADHOC', 'Adhoc'),
    ]
    STATUS_CHOICES = [
        ('TODO', 'Akan Dikerjakan'),
        ('IN_PROGRESS', 'Sedang Dikerjakan'),
        ('REVIEW', 'Dalam Review'),
        ('DONE', 'Selesai'),
        ('OVERDUE', 'Terlambat'),
    ]

    kode_tugas = models.CharField(max_length=50, unique=True, editable=False)
    nama_tugas = models.CharField(max_length=200)
    tipe_tugas = models.CharField(max_length=20, choices=TIPE_CHOICES, default='PROJECT')
    
    # Relasi
    proyek = models.ForeignKey(Proyek, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')
    induk = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subtasks')
    tergantung_pada = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='dependents')
    
    # Data Kerja
    tanggal_mulai = models.DateField()
    tenggat_waktu = models.DateField()
    ditugaskan_ke = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_tasks')
    progress = models.IntegerField(default=0, help_text="Persentase 0-100")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    
    # Keamanan
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)

    def clean(self):
        # Validasi Level Hierarki (Max 3 Level: Proyek -> Tugas -> Subtugas)
        if self.induk:
            # Jika induk punya induk, maka ini level 3. Tidak boleh punya anak lagi nanti.
            if self.induk.induk:
                # Level 3: Subtugas
                pass 
            else:
                # Level 2: Tugas biasa di bawah Tugas Utama (secara teknis Tugas Utama adalah level 1 di tabel Tugas)
                pass
            
            # Validasi Tanggal Subtugas
            if self.tanggal_mulai < self.induk.tanggal_mulai:
                raise ValidationError({'tanggal_mulai': 'Tanggal mulai subtugas tidak boleh mendahului induk.'})
            if self.tenggat_waktu > self.induk.tenggat_waktu:
                raise ValidationError({'tenggat_waktu': 'Tenggat waktu subtugas tidak boleh melebihi induk.'})

        # Validasi Proyek
        if self.tipe_tugas == 'PROJECT' and not self.proyek:
            raise ValidationError({'proyek': 'Tugas tipe Proyek harus memilih Proyek.'})

    def save(self, *args, **kwargs):
        # Auto Numbering
        if not self.kode_tugas:
            if self.induk:
                # Logic Subtugas: T-001-01.1
                count = self.induk.subtasks.count() + 1
                self.kode_tugas = f"{self.induk.kode_tugas}.{{count}}"
                self.proyek = self.induk.proyek # Inherit proyek
            else:
                # Logic Tugas Utama: T-001-01
                last_id = Tugas.objects.filter(induk__isnull=True).count() + 1
                self.kode_tugas = f"T-{{last_id:03d}}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kode_tugas} - {self.nama_tugas}"
"""

# forms.py
forms_content = """
from django import forms
from .models import Proyek, Tugas

class ProyekForm(forms.ModelForm):
    class Meta:
        model = Proyek
        fields = ['nama_proyek', 'deskripsi', 'tanggal_mulai', 'tanggal_selesai']
        widgets = {
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nama_proyek': forms.TextInput(attrs={'class': 'form-control'}),
            'deskripsi': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class TugasForm(forms.ModelForm):
    class Meta:
        model = Tugas
        fields = ['nama_tugas', 'tipe_tugas', 'proyek', 'induk', 'tergantung_pada', 'tanggal_mulai', 'tenggat_waktu', 'ditugaskan_ke', 'progress', 'status']
        widgets = {
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tenggat_waktu': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nama_tugas': forms.TextInput(attrs={'class': 'form-control'}),
            'tipe_tugas': forms.Select(attrs={'class': 'form-select'}),
            'proyek': forms.Select(attrs={'class': 'form-select'}),
            'induk': forms.Select(attrs={'class': 'form-select'}),
            'tergantung_pada': forms.Select(attrs={'class': 'form-select'}),
            'ditugaskan_ke': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'progress': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
        }

    def __init__(self, user, *args, **kwargs):
        super(TugasForm, self).__init__(*args, **kwargs)
        # Filter berdasarkan grup user
        if not user.is_superuser:
            user_group = user.groups.first()
            if user_group:
                self.fields['proyek'].queryset = Proyek.objects.filter(pemilik_grup=user_group)
                self.fields['induk'].queryset = Tugas.objects.filter(pemilik_grup=user_group)
                self.fields['tergantung_pada'].queryset = Tugas.objects.filter(pemilik_grup=user_group)
"""

# views.py
views_content = """
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q
from .models import Proyek, Tugas
from .forms import ProyekForm, TugasForm

# --- Mixin untuk Permission ---
class GroupPermissionMixin:
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_superuser:
            return qs
        # Direktur/Head melihat semua (Asumsi ada grup bernama 'Management')
        if user.groups.filter(name='Management').exists():
            return qs
        # User biasa hanya melihat grup sendiri
        return qs.filter(pemilik_grup=user.groups.first())

# --- Dashboard ---
@login_required
def dashboard(request):
    user = request.user
    group = user.groups.first()
    
    tasks = Tugas.objects.all()
    projects = Proyek.objects.all()
    
    if not user.is_superuser and not user.groups.filter(name='Management').exists():
        tasks = tasks.filter(pemilik_grup=group)
        projects = projects.filter(pemilik_grup=group)

    context = {
        'total_projects': projects.count(),
        'total_tasks': tasks.count(),
        'overdue_tasks': tasks.filter(status='OVERDUE').count(),
        'in_progress': tasks.filter(status='IN_PROGRESS').count(),
        'todo_count': tasks.filter(status='TODO').count(),
        'done_count': tasks.filter(status='DONE').count(),
    }
    return render(request, 'core/dashboard.html', context)

# --- Proyek CRUD ---
class ProyekListView(LoginRequiredMixin, GroupPermissionMixin, ListView):
    model = Proyek
    template_name = 'core/proyek_list.html'
    context_object_name = 'proyek_list'

class ProyekCreateView(LoginRequiredMixin, CreateView):
    model = Proyek
    form_class = ProyekForm
    template_name = 'core/proyek_form.html'
    success_url = reverse_lazy('proyek-list')

    def form_valid(self, form):
        form.instance.pemilik_grup = self.request.user.groups.first()
        form.instance.dibuat_oleh = self.request.user
        return super().form_valid(form)

class ProyekDetailView(LoginRequiredMixin, GroupPermissionMixin, DetailView):
    model = Proyek
    template_name = 'core/proyek_detail.html'

# --- Tugas CRUD ---
class TugasListView(LoginRequiredMixin, GroupPermissionMixin, ListView):
    model = Tugas
    template_name = 'core/tugas_list.html'
    context_object_name = 'tugas_list'

    def get_queryset(self):
        qs = super().get_queryset()
        # Tampilkan hierarki root saja di list utama, child di expand
        return qs.order_by('kode_tugas')

class TugasCreateView(LoginRequiredMixin, CreateView):
    model = Tugas
    form_class = TugasForm
    template_name = 'core/tugas_form.html'
    success_url = reverse_lazy('tugas-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.pemilik_grup = self.request.user.groups.first()
        return super().form_valid(form)

# --- GANTT CHART DATA ---
@login_required
def gantt_data(request):
    user = request.user
    tasks = Tugas.objects.all()
    if not user.is_superuser:
         tasks = tasks.filter(pemilik_grup=user.groups.first())
    
    data = []
    for t in tasks:
        deps = [d.kode_tugas for d in t.dependents.all()] if t.dependents else []
        # Dependencies string logic for Frappe Gantt
        dep_str = ", ".join([str(d.id) for d in list(t.dependents.all())]) if t.tergantung_pada else ""
        
        data.append({
            'id': str(t.id),
            'name': t.nama_tugas,
            'start': t.tanggal_mulai.strftime('%Y-%m-%d'),
            'end': t.tenggat_waktu.strftime('%Y-%m-%d'),
            'progress': t.progress,
            'dependencies': str(t.tergantung_pada.id) if t.tergantung_pada else ""
        })
    return JsonResponse(data, safe=False)

@login_required
def gantt_view(request):
    return render(request, 'core/gantt.html')
"""

# urls.py (App Level)
urls_app_content = """
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('proyek/', views.ProyekListView.as_view(), name='proyek-list'),
    path('proyek/baru/', views.ProyekCreateView.as_view(), name='proyek-create'),
    path('proyek/<int:pk>/', views.ProyekDetailView.as_view(), name='proyek-detail'),
    path('tugas/', views.TugasListView.as_view(), name='tugas-list'),
    path('tugas/baru/', views.TugasCreateView.as_view(), name='tugas-create'),
    path('gantt/', views.gantt_view, name='gantt-view'),
    path('gantt/data/', views.gantt_data, name='gantt-data'),
]
"""

# --- TEMPLATES ---
# base.html
base_html = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Risk Management Tracker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- Frappe Gantt -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/frappe-gantt/0.6.1/frappe-gantt.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/frappe-gantt/0.6.1/frappe-gantt.css">
    <style>
        body { display: flex; min-height: 100vh; flex-direction: column; }
        .wrapper { display: flex; flex: 1; }
        .sidebar { min-width: 250px; background: #2c3e50; color: white; padding: 20px; }
        .sidebar a { color: #bdc3c7; text-decoration: none; display: block; padding: 10px 0; }
        .sidebar a:hover { color: white; }
        .content { flex: 1; padding: 20px; background: #f8f9fa; }
        .card { border: none; shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">Risk Management Tracker</a>
            <span class="navbar-text">User: {{ request.user.username }} ({{ request.user.groups.first.name }})</span>
        </div>
    </nav>
    
    <div class="wrapper">
        <div class="sidebar">
            <h4>Menu</h4>
            <a href="{% url 'dashboard' %}">📊 Dashboard</a>
            <a href="{% url 'proyek-list' %}">📁 Proyek</a>
            <a href="{% url 'tugas-list' %}">✅ Daftar Tugas</a>
            <a href="{% url 'gantt-view' %}">📅 Gantt Chart</a>
            <hr>
            <a href="/admin/">⚙️ Admin Panel</a>
            <a href="/accounts/logout/">🚪 Logout</a>
        </div>
        <div class="content">
            {% block content %}{% endblock %}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# dashboard.html
dashboard_html = """
{% extends 'core/base.html' %}
{% block content %}
<h2>Dashboard Risiko & Proyek</h2>
<div class="row mt-4">
    <div class="col-md-3"><div class="card p-3 bg-primary text-white"><h3>{{ total_projects }}</h3> <small>Total Proyek</small></div></div>
    <div class="col-md-3"><div class="card p-3 bg-success text-white"><h3>{{ total_tasks }}</h3> <small>Total Tugas</small></div></div>
    <div class="col-md-3"><div class="card p-3 bg-danger text-white"><h3>{{ overdue_tasks }}</h3> <small>Terlambat</small></div></div>
    <div class="col-md-3"><div class="card p-3 bg-warning text-white"><h3>{{ in_progress }}</h3> <small>Sedang Berjalan</small></div></div>
</div>

<div class="row mt-4">
    <div class="col-md-6">
        <div class="card p-3">
            <h5>Status Tugas</h5>
            <canvas id="statusChart"></canvas>
        </div>
    </div>
</div>

<script>
    const ctx = document.getElementById('statusChart').getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Todo', 'In Progress', 'Done', 'Overdue'],
            datasets: [{
                data: [{{ todo_count }}, {{ in_progress }}, {{ done_count }}, {{ overdue_tasks }}],
                backgroundColor: ['#6c757d', '#ffc107', '#198754', '#dc3545']
            }]
        }
    });
</script>
{% endblock %}
"""

# tugas_list.html
tugas_list_html = """
{% extends 'core/base.html' %}
{% block content %}
<div class="d-flex justify-content-between mb-3">
    <h2>Daftar Tugas Risk Management</h2>
    <a href="{% url 'tugas-create' %}" class="btn btn-primary">+ Tambah Tugas</a>
</div>
<table class="table table-hover bg-white">
    <thead class="table-light">
        <tr>
            <th>Kode</th>
            <th>Nama Tugas</th>
            <th>Tipe</th>
            <th>PIC</th>
            <th>Deadline</th>
            <th>Status</th>
            <th>Aksi</th>
        </tr>
    </thead>
    <tbody>
        {% for tugas in tugas_list %}
        <tr>
            <td>{{ tugas.kode_tugas }}</td>
            <td style="padding-left: {% if tugas.induk %}40px{% else %}10px{% endif %}">
                {% if tugas.induk %}↳{% endif %} {{ tugas.nama_tugas }}
            </td>
            <td><span class="badge bg-info">{{ tugas.tipe_tugas }}</span></td>
            <td>{{ tugas.ditugaskan_ke.username|default:"-" }}</td>
            <td>{{ tugas.tenggat_waktu }}</td>
            <td>
                {% if tugas.status == 'DONE' %}<span class="badge bg-success">Selesai</span>
                {% elif tugas.status == 'OVERDUE' %}<span class="badge bg-danger">Telat</span>
                {% else %}<span class="badge bg-secondary">{{ tugas.get_status_display }}</span>{% endif %}
            </td>
            <td>
                <button class="btn btn-sm btn-outline-secondary">Edit</button>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
"""

# proyek_list.html
proyek_list_html = """
{% extends 'core/base.html' %}
{% block content %}
<div class="d-flex justify-content-between mb-3">
    <h2>Daftar Proyek</h2>
    <a href="{% url 'proyek-create' %}" class="btn btn-primary">+ Buat Proyek</a>
</div>
<div class="row">
    {% for p in proyek_list %}
    <div class="col-md-4">
        <div class="card p-3">
            <h5>{{ p.nama_proyek }} <small class="text-muted">{{ p.kode_proyek }}</small></h5>
            <p>{{ p.deskripsi|truncatechars:100 }}</p>
            <small>Mulai: {{ p.tanggal_mulai }} | Selesai: {{ p.tanggal_selesai }}</small>
            <a href="{% url 'proyek-detail' p.pk %}" class="btn btn-sm btn-outline-primary mt-2">Detail</a>
        </div>
    </div>
    {% empty %}
    <p>Belum ada proyek untuk divisi Anda.</p>
    {% endfor %}
</div>
{% endblock %}
"""

# proyek_form.html (Basic)
proyek_form_html = """
{% extends 'core/base.html' %}
{% block content %}
<h2>Form Proyek</h2>
<form method="post" class="card p-4">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="btn btn-success">Simpan</button>
</form>
{% endblock %}
"""

# tugas_form.html (Basic)
tugas_form_html = """
{% extends 'core/base.html' %}
{% block content %}
<h2>Form Tugas</h2>
<form method="post" class="card p-4">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="btn btn-success">Simpan</button>
</form>
{% endblock %}
"""

# proyek_detail.html
proyek_detail_html = """
{% extends 'core/base.html' %}
{% block content %}
<h2>{{ object.nama_proyek }}</h2>
<p>{{ object.deskripsi }}</p>
<hr>
<h4>Daftar Tugas Proyek Ini</h4>
<ul>
{% for task in object.tasks.all %}
    <li>{{ task.nama_tugas }} - {{ task.status }}</li>
{% endfor %}
</ul>
{% endblock %}
"""

# gantt.html
gantt_html = """
{% extends 'core/base.html' %}
{% block content %}
<h2>Gantt Chart Timeline</h2>
<div class="card p-3">
    <div id="gantt"></div>
</div>
<script>
    fetch("{% url 'gantt-data' %}")
        .then(response => response.json())
        .then(data => {
            if(data.length > 0) {
                var gantt = new Gantt("#gantt", data, {
                    header_height: 50,
                    column_width: 30,
                    step: 24,
                    view_modes: ['Quarter Day', 'Half Day', 'Day', 'Week', 'Month'],
                    bar_height: 20,
                    bar_corner_radius: 3,
                    arrow_curve: 5,
                    padding: 18,
                    view_mode: 'Week',
                    date_format: 'YYYY-MM-DD',
                    custom_popup_html: function(task) {
                        return `
                        <div class="details-container" style="padding:10px; background:white; border:1px solid #ccc;">
                          <h5>${task.name}</h5>
                          <p>Progress: ${task.progress}%</p>
                        </div>
                        `;
                    }
                });
            } else {
                document.getElementById('gantt').innerHTML = "<p>Belum ada data tugas untuk Gantt Chart.</p>";
            }
        });
</script>
{% endblock %}
"""


def main():
    print(f"--- Starting Setup for {PROJECT_NAME} ---")
    
    # 1. Create Directories
    base_path = os.getcwd()
    project_path = os.path.join(base_path, PROJECT_NAME)
    app_path = os.path.join(base_path, APP_NAME)
    templates_path = os.path.join(base_path, 'templates', 'core')
    
    os.makedirs(project_path, exist_ok=True)
    os.makedirs(app_path, exist_ok=True)
    os.makedirs(templates_path, exist_ok=True)
    
    # 2. Create Root Files
    create_file(os.path.join(base_path, 'requirements.txt'), requirements_content)
    create_file(os.path.join(base_path, 'manage.py'), manage_py_content)
    
    # 3. Create Project Config
    create_file(os.path.join(project_path, '__init__.py'), "")
    create_file(os.path.join(project_path, 'settings.py'), settings_content)
    create_file(os.path.join(project_path, 'urls.py'), urls_project_content)
    create_file(os.path.join(project_path, 'wsgi.py'), f"import os\nfrom django.core.wsgi import get_wsgi_application\nos.environ.setdefault('DJANGO_SETTINGS_MODULE', '{PROJECT_NAME}.settings')\napplication = get_wsgi_application()")
    
    # 4. Create App Files
    create_file(os.path.join(app_path, '__init__.py'), "")
    create_file(os.path.join(app_path, 'admin.py'), "from django.contrib import admin\nfrom .models import Proyek, Tugas\nadmin.site.register(Proyek)\nadmin.site.register(Tugas)")
    create_file(os.path.join(app_path, 'apps.py'), f"from django.apps import AppConfig\nclass CoreConfig(AppConfig):\n    default_auto_field = 'django.db.models.BigAutoField'\n    name = '{APP_NAME}'")
    create_file(os.path.join(app_path, 'models.py'), models_content)
    create_file(os.path.join(app_path, 'views.py'), views_content)
    create_file(os.path.join(app_path, 'urls.py'), urls_app_content)
    create_file(os.path.join(app_path, 'forms.py'), forms_content)
    
    # 5. Create Templates
    create_file(os.path.join(templates_path, 'base.html'), base_html)
    create_file(os.path.join(templates_path, 'dashboard.html'), dashboard_html)
    create_file(os.path.join(templates_path, 'tugas_list.html'), tugas_list_html)
    create_file(os.path.join(templates_path, 'proyek_list.html'), proyek_list_html)
    create_file(os.path.join(templates_path, 'proyek_form.html'), proyek_form_html)
    create_file(os.path.join(templates_path, 'tugas_form.html'), tugas_form_html)
    create_file(os.path.join(templates_path, 'proyek_detail.html'), proyek_detail_html)
    create_file(os.path.join(templates_path, 'gantt.html'), gantt_html)

    print("\n--- Setup Complete! ---")
    print(f"1. Install dependencies: pip install -r requirements.txt")
    print(f"2. Migrate DB: python manage.py makemigrations {APP_NAME} && python manage.py migrate")
    print(f"3. Create Superuser: python manage.py createsuperuser")
    print(f"4. Run Server: python manage.py runserver")
    
    # Make manage.py executable
    try:
        os.chmod(os.path.join(base_path, 'manage.py'), 0o755)
    except:
        pass

if __name__ == "__main__":
    main()