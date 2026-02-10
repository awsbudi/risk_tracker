from django import forms
from django.contrib.auth.models import User
from .models import Proyek, Tugas, TemplateBAU

# Form untuk Upload Excel
class ImportTugasForm(forms.Form):
    file_excel = forms.FileField(label="Upload File Excel (.xlsx)", widget=forms.FileInput(attrs={'class': 'form-control'}))

class ProyekForm(forms.ModelForm):
    class Meta:
        model = Proyek
        fields = ['nama_proyek', 'deskripsi', 'tanggal_mulai', 'tanggal_selesai', 'tanggal_mulai_aktual', 'tanggal_selesai_aktual', 'status']
        widgets = {
            'nama_proyek': forms.TextInput(attrs={'class': 'form-control'}),
            'deskripsi': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            # FIX: Tambahkan format='%Y-%m-%d' agar nilai muncul saat Edit
            'tanggal_mulai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_mulai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'tanggal_mulai': 'Start Date (Plan)',
            'tanggal_selesai': 'End Date (Plan)',
            'tanggal_mulai_aktual': 'Start Date (Actual/Realisasi)',
            'tanggal_selesai_aktual': 'End Date (Actual/Realisasi)',
        }

class TugasForm(forms.ModelForm):
    class Meta:
        model = Tugas
        fields = [
            'nama_tugas', 'tipe_tugas', 'proyek', 'pemberi_tugas',
            'induk', 'tergantung_pada', 
            'tanggal_mulai', 'tenggat_waktu', 
            'tanggal_mulai_aktual', 'tanggal_selesai_aktual',
            'ditugaskan_ke', 'progress', 'status'
        ]
        widgets = {
            'nama_tugas': forms.TextInput(attrs={'class': 'form-control'}),
            'tipe_tugas': forms.Select(attrs={'class': 'form-select'}),
            'proyek': forms.Select(attrs={'class': 'form-select'}),
            'pemberi_tugas': forms.TextInput(attrs={'class': 'form-control', 'list': 'user-list', 'placeholder': 'Ketik nama atau pilih...'}),
            'induk': forms.Select(attrs={'class': 'form-select'}),
            'tergantung_pada': forms.Select(attrs={'class': 'form-select'}),
            'ditugaskan_ke': forms.Select(attrs={'class': 'form-select'}),
            
            # FIX: Tambahkan format='%Y-%m-%d' di sini
            'tanggal_mulai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tenggat_waktu': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_mulai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            
            'progress': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, user, *args, **kwargs):
        super(TugasForm, self).__init__(*args, **kwargs)
        
        active_users = User.objects.filter(is_active=True)
        self.fields['ditugaskan_ke'].queryset = active_users
        
        user_groups = user.groups.all()
        
        if not user.is_superuser:
            self.fields['proyek'].queryset = Proyek.objects.filter(pemilik_grup__in=user_groups)
            self.fields['induk'].queryset = Tugas.objects.filter(pemilik_grup__in=user_groups)
            self.fields['tergantung_pada'].queryset = Tugas.objects.filter(pemilik_grup__in=user_groups)

            role = user.profile.role if hasattr(user, 'profile') else 'MEMBER'
            
            if role == 'MEMBER':
                self.fields['ditugaskan_ke'].queryset = User.objects.filter(pk=user.pk)
            elif role in ['ADMIN', 'LEADER']:
                team_users = User.objects.filter(groups__in=user_groups, is_active=True).distinct()
                self.fields['ditugaskan_ke'].queryset = team_users
            
            if not self.instance.pk:
                self.initial['pemberi_tugas'] = user.get_full_name() or user.username