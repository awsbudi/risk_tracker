from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # Proyek
    path('proyek/', views.ProyekListView.as_view(), name='proyek-list'),
    path('proyek/baru/', views.ProyekCreateView.as_view(), name='proyek-create'),
    path('proyek/<int:pk>/', views.ProyekDetailView.as_view(), name='proyek-detail'),
    path('proyek/<int:pk>/edit/', views.ProyekUpdateView.as_view(), name='proyek-update'),
    path('proyek/<int:pk>/hapus/', views.ProyekDeleteView.as_view(), name='proyek-delete'),
    
    # Tugas
    path('tugas/', views.TugasListView.as_view(), name='tugas-list'),
    path('tugas/baru/', views.TugasCreateView.as_view(), name='tugas-create'),
    path('tugas/<int:pk>/edit/', views.TugasUpdateView.as_view(), name='tugas-update'),
    path('tugas/<int:pk>/hapus/', views.TugasDeleteView.as_view(), name='tugas-delete'),
    
    # API Updates (AJAX)
    path('tugas/<int:pk>/update-progress/', views.update_progress_api, name='tugas-update-progress'),
    path('tugas/<int:pk>/update-date/', views.update_task_date_api, name='tugas-update-date'),
    
    # NEW: API Helper untuk Form Auto-fill
    path('api/get-entity-dates/', views.get_entity_dates_api, name='api-get-dates'),

    # Gantt & Export
    path('gantt/', views.gantt_view, name='gantt-view'),
    path('gantt/data/', views.gantt_data, name='gantt-data'),
    path('gantt/export/', views.export_gantt_excel, name='gantt-export'), # NEW: Export

    # Kalender
    path('calendar/', views.calendar_view, name='calendar-view'),
    path('calendar/data/', views.calendar_data, name='calendar-data'),
    
    # BAU Templates
    path('bau/', views.TemplateBAUListView.as_view(), name='bau-list'),
    path('bau/baru/', views.TemplateBAUCreateView.as_view(), name='bau-create'),
    path('bau/generate/', views.trigger_bau_generation, name='bau-generate'),
]