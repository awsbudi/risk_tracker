from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User, Group
from .models import Proyek, Tugas, UserProfile, TemplateBAU, AuditLog

# 1. Definisikan Inline (Mempertahankan Fix Anda)
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Risk Management Role'
    fk_name = 'user'
    
    # Tambahan: Mencegah error duplicate saat inline ditampilkan
    extra = 0 

# 2. Definisikan User Admin Baru (Gabungan Fitur)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    # Menambahkan 'get_groups' dan 'last_name' ke list display
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_groups', 'get_role', 'is_staff')
    
    # Fungsi baru: Menampilkan Grup
    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])
    get_groups.short_description = 'Groups'

    # Fungsi Role
    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.role
        return '-'
    get_role.short_description = 'Role Project'

    # --- PERBAIKAN PENTING (DIPERTAHANKAN) ---
    def get_inline_instances(self, request, obj=None):
        # Jika obj=None, berarti kita sedang di halaman "Add User"
        if not obj:
            # Sembunyikan Inline Profile agar tidak bentrok dengan Signal creation
            return []
        # Jika obj ada, berarti sedang Edit, tampilkan Inline
        return super().get_inline_instances(request, obj)

# 3. Register ulang User
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)


# 4. Admin untuk Model Lain (Lebih Canggih dengan Filter & Search)

@admin.register(Proyek)
class ProyekAdmin(admin.ModelAdmin):
    list_display = ('kode_proyek', 'nama_proyek', 'pemilik_grup', 'tanggal_mulai', 'tanggal_selesai')
    list_filter = ('pemilik_grup',)
    search_fields = ('nama_proyek', 'kode_proyek')

@admin.register(Tugas)
class TugasAdmin(admin.ModelAdmin):
    list_display = ('kode_tugas', 'nama_tugas', 'tipe_tugas', 'proyek', 'status', 'progress', 'ditugaskan_ke')
    list_filter = ('tipe_tugas', 'status', 'pemilik_grup', 'proyek')
    search_fields = ('nama_tugas', 'kode_tugas')
    autocomplete_fields = ['induk', 'tergantung_pada'] # Agar dropdown tidak berat

@admin.register(TemplateBAU)
class TemplateBAUAdmin(admin.ModelAdmin):
    list_display = ('nama_tugas', 'frekuensi', 'pemilik_grup', 'default_pic')
    list_filter = ('frekuensi', 'pemilik_grup')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'target_model', 'target_id', 'details')
    list_filter = ('action', 'target_model', 'user')
    readonly_fields = ('timestamp', 'user', 'action', 'target_model', 'target_id', 'details') # Log read-only
    
    def has_add_permission(self, request):
        return False
