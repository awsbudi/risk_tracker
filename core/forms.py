from django import forms
from .models import Proyek, Tugas

class ProyekForm(forms.ModelForm):
    class Meta:
        model = Proyek
        fields = ['nama_proyek', 'deskripsi', 'tanggal_mulai', 'tanggal_selesai']
        widgets = {
            # Tambahkan format='%Y-%m-%d' agar value muncul saat Edit
            'tanggal_mulai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tanggal_selesai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'nama_proyek': forms.TextInput(attrs={'class': 'form-control'}),
            'deskripsi': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class TugasForm(forms.ModelForm):
    class Meta:
        model = Tugas
        fields = ['nama_tugas', 'tipe_tugas', 'proyek', 'induk', 'tergantung_pada', 'tanggal_mulai', 'tenggat_waktu', 'ditugaskan_ke', 'progress', 'status']
        widgets = {
            # Tambahkan format='%Y-%m-%d' agar value muncul saat Edit
            'tanggal_mulai': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tenggat_waktu': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'nama_tugas': forms.TextInput(attrs={'class': 'form-control'}),
            'tipe_tugas': forms.Select(attrs={'class': 'form-select'}),
            'proyek': forms.Select(attrs={'class': 'form-select'}),
            'induk': forms.Select(attrs={'class': 'form-select'}),
            'tergantung_pada': forms.Select(attrs={'class': 'form-select'}),
            'ditugaskan_ke': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'progress': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
        }

    # Ubah signature agar lebih aman menangkap kwargs dari View
    def __init__(self, *args, **kwargs):
        # Ambil user dari kwargs, default None jika tidak ada
        user = kwargs.pop('user', None)
        
        super(TugasForm, self).__init__(*args, **kwargs)
        
        # Filter Dropdown berdasarkan grup user (jika bukan superuser)
        if user and not user.is_superuser:
            user_group = user.groups.first()
            if user_group:
                self.fields['proyek'].queryset = Proyek.objects.filter(pemilik_grup=user_group)
                self.fields['induk'].queryset = Tugas.objects.filter(pemilik_grup=user_group)
                self.fields['tergantung_pada'].queryset = Tugas.objects.filter(pemilik_grup=user_group)