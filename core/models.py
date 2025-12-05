from django.db import models, IntegrityError
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver

# --- EXTENSION: USER ROLE ---
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Group Admin'),      
        ('LEADER', 'Team Leader'),     
        ('MEMBER', 'Member'),          
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            UserProfile.objects.create(user=instance)
        except IntegrityError:
            pass
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()

# --- EXISTING MODELS ---
class Proyek(models.Model):
    kode_proyek = models.CharField(max_length=20, unique=True, editable=False)
    nama_proyek = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True)
    tanggal_mulai = models.DateField()
    tanggal_selesai = models.DateField()
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)
    dibuat_oleh = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Proyek"
        verbose_name_plural = "Proyek"

    def clean(self):
        if self.tanggal_mulai and self.tanggal_selesai:
            if self.tanggal_selesai < self.tanggal_mulai:
                raise ValidationError({'tanggal_selesai': 'Tanggal selesai proyek tidak boleh mendahului tanggal mulai.'})

    def save(self, *args, **kwargs):
        if not self.kode_proyek:
            last_id = Proyek.objects.all().order_by('id').last()
            new_id = last_id.id + 1 if last_id else 1
            self.kode_proyek = f"P-{new_id:03d}"
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
    
    proyek = models.ForeignKey(Proyek, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')
    induk = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subtasks')
    tergantung_pada = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='dependents')
    
    tanggal_mulai = models.DateField()
    tenggat_waktu = models.DateField()
    ditugaskan_ke = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_tasks')
    progress = models.IntegerField(default=0, help_text="Persentase 0-100")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Tugas"
        verbose_name_plural = "Tugas"

    def clean(self):
        if self.tipe_tugas in ['BAU', 'ADHOC']:
            self.proyek = None 
        elif self.tipe_tugas == 'PROJECT' and not self.proyek:
            raise ValidationError({'proyek': 'Tugas tipe Proyek WAJIB memilih Proyek.'})

        if self.tanggal_mulai and self.tenggat_waktu:
            if self.tenggat_waktu < self.tanggal_mulai:
                raise ValidationError({
                    'tenggat_waktu': f'Tenggat waktu ({self.tenggat_waktu}) tidak boleh lebih awal dari tanggal mulai ({self.tanggal_mulai}).'
                })

        if self.tanggal_mulai:
            if self.proyek and self.tanggal_mulai < self.proyek.tanggal_mulai:
                raise ValidationError({
                    'tanggal_mulai': f'Tanggal mulai tugas tidak boleh mendahului tanggal mulai proyek ({self.proyek.tanggal_mulai}).'
                })

            if self.induk:
                if self.tanggal_mulai < self.induk.tanggal_mulai:
                    raise ValidationError({
                        'tanggal_mulai': f'Subtugas tidak boleh mulai sebelum induknya ({self.induk.tanggal_mulai}).'
                    })
                if self.tenggat_waktu > self.induk.tenggat_waktu:
                    raise ValidationError({
                        'tenggat_waktu': f'Subtugas tidak boleh selesai setelah induknya ({self.induk.tenggat_waktu}).'
                    })

            if self.tergantung_pada:
                if self.tanggal_mulai <= self.tergantung_pada.tenggat_waktu:
                     raise ValidationError({
                        'tanggal_mulai': f'Tugas ini tergantung pada "{self.tergantung_pada.kode_tugas}". Baru boleh mulai setelah tanggal {self.tergantung_pada.tenggat_waktu}.'
                    })

    def save(self, *args, **kwargs):
        if self.tipe_tugas in ['BAU', 'ADHOC']:
            self.proyek = None

        if not self.kode_tugas:
            if self.induk:
                count = self.induk.subtasks.count() + 1
                self.kode_tugas = f"{self.induk.kode_tugas}.{count}"
                self.proyek = self.induk.proyek
            else:
                last_id = Tugas.objects.filter(induk__isnull=True).count() + 1
                self.kode_tugas = f"T-{last_id:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kode_tugas} - {self.nama_tugas}"
    

class TemplateBAU(models.Model):
    FREKUENSI_CHOICES = [
        ('DAILY', 'Harian'),  # NEW: REQ 1 - Tambah opsi harian
        ('WEEKLY', 'Mingguan'),
        ('MONTHLY', 'Bulanan'),
        ('QUARTERLY', 'Triwulan'),
        ('YEARLY', 'Tahunan'),
    ]

    nama_tugas = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True)
    frekuensi = models.CharField(max_length=20, choices=FREKUENSI_CHOICES)
    
    default_pic = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)
    
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Template BAU"
        verbose_name_plural = "Template BAU"

    def __str__(self):
        return f"{self.nama_tugas} ({self.frekuensi})"

# NEW: REQ 5 - Model Audit Log
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Membuat'),
        ('UPDATE', 'Mengubah'),
        ('DELETE', 'Menghapus'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=50) # 'Proyek' atau 'Tugas'
    target_id = models.CharField(max_length=50)    # ID atau Kode objek
    details = models.TextField()                   # Apa yang berubah?
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.target_model} at {self.timestamp}"