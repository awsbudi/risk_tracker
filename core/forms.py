from django import forms
from django.contrib.auth.models import User, Group
from .models import Proyek, Tugas, TemplateBAU

class ImportTugasForm(forms.Form):
    file_excel = forms.FileField(label="Upload File Excel Tugas (.xlsx)", widget=forms.FileInput(attrs={'class': 'form-control'}))

class ImportUserForm(forms.Form):
    file_excel = forms.FileField(label="Upload File Excel User (.xlsx)", widget=forms.FileInput(attrs={'class': 'form-control'}))

# --- FORM PROYEK ---
class ProyekForm(forms.ModelForm):
    class Meta:
        model = Proyek
        # UPDATE: Tambahkan pemilik_grup
        fields = ['nama_proyek', 'deskripsi', 'tanggal_mulai', 'tanggal_selesai', 'tanggal_mulai_aktual', 'tanggal_selesai_aktual', 'status', 'pemilik_grup']
        widgets = {
            'nama_proyek': forms.TextInput(attrs={'class': 'form-control'}),
            'deskripsi': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tanggal_mulai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_mulai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'pemilik_grup': forms.Select(attrs={'class': 'form-select'}), # Widget baru
        }
        labels = {
            'tanggal_mulai': 'Start Date (Plan)',
            'tanggal_selesai': 'End Date (Plan)',
            'tanggal_mulai_aktual': 'Start Date (Actual/Realisasi)',
            'tanggal_selesai_aktual': 'End Date (Actual/Realisasi)',
            'pemilik_grup': 'Divisi / Group',
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Jika bukan superadmin, sembunyikan kolom pemilihan divisi (karena akan di-set otomatis)
        if not user.is_superuser:
            del self.fields['pemilik_grup']
        else:
            self.fields['pemilik_grup'].queryset = Group.objects.all().order_by('name')
            self.fields['pemilik_grup'].required = True

# --- FORM TUGAS ---
class TugasForm(forms.ModelForm):
    class Meta:
        model = Tugas
        # UPDATE: Tambahkan pemilik_grup
        fields = [
            'nama_tugas', 'tipe_tugas', 'proyek', 'pemberi_tugas',
            'induk', 'tergantung_pada', 
            'tanggal_mulai', 'tenggat_waktu', 
            'tanggal_mulai_aktual', 'tanggal_selesai_aktual',
            'ditugaskan_ke', 'progress', 'status', 'pemilik_grup'
        ]
        widgets = {
            'nama_tugas': forms.TextInput(attrs={'class': 'form-control'}),
            'tipe_tugas': forms.Select(attrs={'class': 'form-select'}),
            'proyek': forms.Select(attrs={'class': 'form-select'}),
            'pemberi_tugas': forms.TextInput(attrs={'class': 'form-control', 'list': 'user-list', 'placeholder': 'Ketik nama atau pilih...'}),
            'induk': forms.Select(attrs={'class': 'form-select'}),
            'tergantung_pada': forms.Select(attrs={'class': 'form-select'}),
            'ditugaskan_ke': forms.Select(attrs={'class': 'form-select'}),
            'tanggal_mulai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tenggat_waktu': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_mulai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai_aktual': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'progress': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'pemilik_grup': forms.Select(attrs={'class': 'form-select'}), # Widget baru
        }

    def __init__(self, user, *args, **kwargs):
        super(TugasForm, self).__init__(*args, **kwargs)
        
        if not user.is_superuser:
            # Hapus field pemilik grup untuk user biasa
            del self.fields['pemilik_grup']
            
            user_groups = list(user.groups.all())
            group_names = [g.name.upper() for g in user_groups]
            role = user.profile.role if hasattr(user, 'profile') else 'MEMBER'
            
            if 'RISK MANAGEMENT' in group_names and role == 'ADMIN':
                sub_groups = Group.objects.filter(name__in=[
                    'RISK PROCESS CONTROL', 'PORTFOLIO MANAGEMENT & GOVERNANCE', 'RISK PRODUCT & DEVELOPMENT'
                ])
                user_groups.extend(list(sub_groups))
                
            accessible_groups = Group.objects.filter(id__in=[g.id for g in user_groups]).distinct()

            self.fields['proyek'].queryset = Proyek.objects.filter(pemilik_grup__in=accessible_groups)
            self.fields['induk'].queryset = Tugas.objects.filter(pemilik_grup__in=accessible_groups)
            self.fields['tergantung_pada'].queryset = Tugas.objects.filter(pemilik_grup__in=accessible_groups)
            
            if role == 'MEMBER':
                self.fields['ditugaskan_ke'].queryset = User.objects.filter(pk=user.pk)
            else:
                team_users = User.objects.filter(groups__in=accessible_groups, is_active=True).distinct()
                self.fields['ditugaskan_ke'].queryset = team_users
        else:
            # SUPERADMIN BEBAS MELIHAT SEMUA
            self.fields['proyek'].queryset = Proyek.objects.all()
            self.fields['induk'].queryset = Tugas.objects.all()
            self.fields['tergantung_pada'].queryset = Tugas.objects.all()
            self.fields['ditugaskan_ke'].queryset = User.objects.filter(is_active=True)
            self.fields['pemilik_grup'].queryset = Group.objects.all().order_by('name')
            self.fields['pemilik_grup'].required = True
            
        if not self.instance.pk:
            self.initial['pemberi_tugas'] = user.get_full_name() or user.username