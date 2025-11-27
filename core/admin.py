from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Proyek, Tugas, UserProfile

# 1. Definisikan Inline
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Risk Management Role'
    fk_name = 'user'
    
    # Tambahan: Mencegah error duplicate saat inline ditampilkan
    extra = 0 

# 2. Definisikan User Admin Baru
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'get_role', 'is_staff')
    
    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.role
        return '-'
    get_role.short_description = 'Role Project'

    # --- PERBAIKAN UTAMA DI SINI ---
    def get_inline_instances(self, request, obj=None):
        # Jika obj=None, berarti kita sedang di halaman "Add User"
        if not obj:
            # Sembunyikan Inline Profile agar tidak bentrok dengan Signal
            return []
        # Jika obj ada, berarti sedang Edit, tampilkan Inline
        return super().get_inline_instances(request, obj)

# 3. Register ulang
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, UserAdmin)
admin.site.register(Proyek)
admin.site.register(Tugas)