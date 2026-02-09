from django.db import models, IntegrityError
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date

# --- EXTENSION: USER ROLE ---
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Group Admin'),      
        ('LEADER', 'Team Leader'),     
        ('MEMBER', 'Member'),          
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')

    def __str__(self): return f"{self.user.username} - {self.role}"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created: UserProfile.objects.get_or_create(user=instance)
    else: 
        if hasattr(instance, 'profile'): instance.profile.save()

# --- PROYEK ---
class Proyek(models.Model):
    STATUS_CHOICES = [
        ('RUNNING', 'Berjalan'),
        ('ON_HOLD', 'Ditunda (On Hold)'), # UAT: Status On Hold
        ('DROP', 'Dibatalkan (Drop)'),    # UAT: Status Drop
        ('DONE', 'Selesai'),
    ]

    kode_proyek = models.CharField(max_length=20, unique=True, editable=False)
    nama_proyek = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True)
    
    # UAT: Plan vs Actual
    tanggal_mulai = models.DateField(verbose_name="Start (Plan)")
    tanggal_selesai = models.DateField(verbose_name="End (Plan)")
    tanggal_mulai_aktual = models.DateField(null=True, blank=True, verbose_name="Start (Actual)")
    tanggal_selesai_aktual = models.DateField(null=True, blank=True, verbose_name="End (Actual)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RUNNING')
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)
    dibuat_oleh = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def clean(self):
        # UAT: Validasi Tanggal Merah (Sabtu=5/Minggu=6) saat Plan
        if self.tanggal_mulai and self.tanggal_mulai.weekday() >= 5:
            raise ValidationError({'tanggal_mulai': 'Tanggal Mulai Plan tidak boleh jatuh pada hari libur (Sabtu/Minggu).'})
        
        if self.tanggal_mulai and self.tanggal_selesai:
            if self.tanggal_selesai < self.tanggal_mulai:
                raise ValidationError({'tanggal_selesai': 'Tanggal selesai tidak boleh mendahului tanggal mulai.'})

    def save(self, *args, **kwargs):
        if not self.kode_proyek:
            last = Proyek.objects.all().order_by('id').last()
            new_id = last.id + 1 if last else 1
            self.kode_proyek = f"P-{new_id:03d}"
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.kode_proyek} - {self.nama_proyek}"

# --- TUGAS ---
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
        ('ON_HOLD', 'Ditunda'), # UAT
        ('DROP', 'Dibatalkan'), # UAT
    ]

    kode_tugas = models.CharField(max_length=50, unique=True, editable=False)
    nama_tugas = models.CharField(max_length=200)
    tipe_tugas = models.CharField(max_length=20, choices=TIPE_CHOICES, default='PROJECT')
    
    proyek = models.ForeignKey(Proyek, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks')
    induk = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subtasks')
    tergantung_pada = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='dependents')
    
    # UAT: Adhoc butuh Pemberi Tugas
    pemberi_tugas = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='given_tasks')
    
    # UAT: Plan vs Actual di Tugas juga
    tanggal_mulai = models.DateField(verbose_name="Start (Plan)")
    tenggat_waktu = models.DateField(verbose_name="End (Plan)")
    tanggal_mulai_aktual = models.DateField(null=True, blank=True, verbose_name="Start (Actual)")
    tanggal_selesai_aktual = models.DateField(null=True, blank=True, verbose_name="End (Actual)")

    ditugaskan_ke = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_tasks')
    progress = models.IntegerField(default=0, help_text="Persentase 0-100")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)

    def clean(self):
        # UAT: Progress Logic
        if self.status == 'DONE' and self.progress < 100:
            raise ValidationError({'status': 'Status DONE hanya boleh jika Progress 100%.'})
        
        if self.progress == 100 and self.status not in ['DONE', 'OVERDUE', 'DROP']:
             raise ValidationError({'progress': 'Jika Progress 100%, Status harus DONE/Selesai.'})

        # UAT: Validasi Tanggal Merah (Plan)
        if self.tanggal_mulai and self.tanggal_mulai.weekday() >= 5:
            raise ValidationError({'tanggal_mulai': 'Tanggal Mulai tidak boleh hari libur (Sabtu/Minggu).'})

        # Basic Validation
        if self.tipe_tugas == 'PROJECT' and not self.proyek:
            raise ValidationError({'proyek': 'Tugas tipe Proyek WAJIB memilih Proyek.'})
        
        if self.tipe_tugas == 'ADHOC' and not self.pemberi_tugas:
            raise ValidationError({'pemberi_tugas': 'Tugas Adhoc WAJIB mengisi Pemberi Tugas.'})

    def save(self, *args, **kwargs):
        # UAT: Subtask inherit tipe dari induk
        if self.induk:
            self.tipe_tugas = self.induk.tipe_tugas
            self.proyek = self.induk.proyek

        # Auto Code
        if not self.kode_tugas:
            if self.induk:
                count = self.induk.subtasks.count() + 1
                self.kode_tugas = f"{self.induk.kode_tugas}.{count}"
            else:
                last_id = Tugas.objects.filter(induk__isnull=True).count() + 1
                self.kode_tugas = f"T-{last_id:03d}"
        
        # UAT: Jika DONE, set Actual End Date otomatis jika kosong
        if self.status == 'DONE' and not self.tanggal_selesai_aktual:
            self.tanggal_selesai_aktual = date.today()

        super().save(*args, **kwargs)

    def __str__(self): return f"{self.kode_tugas} - {self.nama_tugas}"

class TemplateBAU(models.Model):
    FREKUENSI_CHOICES = [
        ('WEEKLY', 'Mingguan'), ('MONTHLY', 'Bulanan'),
        ('QUARTERLY', 'Triwulan'), ('YEARLY', 'Tahunan'),
    ]
    nama_tugas = models.CharField(max_length=200)
    deskripsi = models.TextField(blank=True)
    frekuensi = models.CharField(max_length=20, choices=FREKUENSI_CHOICES)
    default_pic = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    pemilik_grup = models.ForeignKey(Group, on_delete=models.CASCADE)
    def __str__(self): return f"{self.nama_tugas} ({self.frekuensi})"

class AuditLog(models.Model):
    ACTION_CHOICES = [('CREATE', 'Membuat'), ('UPDATE', 'Mengubah'), ('DELETE', 'Menghapus')]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=50)
    target_id = models.CharField(max_length=50)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)