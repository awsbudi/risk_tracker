from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django import forms
from .models import Proyek, Tugas, UserProfile, AuditLog

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Role'
    extra = 0

class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'
    def clean_is_superuser(self):
        is_superuser = self.cleaned_data.get('is_superuser')
        # UAT: Prevent non-superuser from making superusers
        # Note: logic moved to ModelAdmin for request access
        return is_superuser

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'get_role', 'is_staff', 'is_superuser')
    
    def get_role(self, obj): return obj.profile.role if hasattr(obj, 'profile') else '-'
    get_role.short_description = 'Role'

    def has_delete_permission(self, request, obj=None):
        # UAT: Hanya Superuser yang boleh hapus user
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        # UAT: Admin biasa tidak boleh edit is_superuser
        if not request.user.is_superuser:
            return ('is_superuser', 'user_permissions', 'last_login', 'date_joined')
        return ()

try: admin.site.unregister(User)
except: pass
admin.site.register(User, UserAdmin)
admin.site.register(Proyek)
admin.site.register(Tugas)
admin.site.register(AuditLog)