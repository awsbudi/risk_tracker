from django.urls import path
from . import views

urlpatterns = [
    # --- DASHBOARD ---
    path('', views.dashboard, name='dashboard'),

    # --- PROYEK ---
    path('proyek/', views.ProyekListView.as_view(), name='proyek-list'),
    path('proyek/create/', views.ProyekCreateView.as_view(), name='proyek-create'),
    path('proyek/<int:pk>/', views.ProyekDetailView.as_view(), name='proyek-detail'),
    path('proyek/<int:pk>/update/', views.ProyekUpdateView.as_view(), name='proyek-update'),
    path('proyek/<int:pk>/delete/', views.ProyekDeleteView.as_view(), name='proyek-delete'),

    # --- TUGAS ---
    path('tugas/', views.TugasListView.as_view(), name='tugas-list'),
    path('tugas/create/', views.TugasCreateView.as_view(), name='tugas-create'),
    path('tugas/import/', views.import_tugas, name='tugas-import'),
    path('tugas/import/template/', views.download_template_tugas, name='tugas-import-template'),
    path('tugas/<int:pk>/update/', views.TugasUpdateView.as_view(), name='tugas-update'),
    path('tugas/<int:pk>/delete/', views.TugasDeleteView.as_view(), name='tugas-delete'),

    # --- USER MANAGEMENT (UPDATE) ---
    path('users/', views.UserListView.as_view(), name='user-list'), # Halaman List
    path('users/delete/', views.bulk_delete_users, name='user-bulk-delete'), # Aksi Delete
    path('users/import/', views.import_user, name='user-import'),
    path('users/import/template/', views.download_template_user, name='user-import-template'),

    # --- GANTT CHART ---
    path('gantt/', views.gantt_view, name='gantt-view'),          
    path('gantt-data/', views.gantt_data, name='gantt-data'),
    path('gantt/export/', views.export_gantt_excel, name='gantt-export'),

    # --- BAU ---
    path('bau/', views.TemplateBAUListView.as_view(), name='bau-list'),
    path('bau/create/', views.TemplateBAUCreateView.as_view(), name='bau-create'),
    path('bau/<int:pk>/update/', views.TemplateBAUUpdateView.as_view(), name='bau-update'),
    path('bau/<int:pk>/delete/', views.TemplateBAUDeleteView.as_view(), name='bau-delete'),
    path('bau/<int:pk>/trigger/', views.trigger_bau_single, name='trigger-bau'),

    # --- CALENDAR ---
    path('calendar/', views.calendar_view, name='calendar-view'),
    path('calendar-data/', views.calendar_data, name='calendar-data'),

    # --- API ---
    path('api/task/<int:pk>/update-progress/', views.update_progress_api, name='api-update-progress'),
    path('api/task/<int:pk>/update-date/', views.update_task_date_api, name='api-update-date'),
    path('api/get-dates/', views.get_entity_dates_api, name='api-get-dates'),
]