from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import TemplateBAU, Tugas
from datetime import timedelta, date

class Command(BaseCommand):
    help = 'Generate tugas rutin dari Template BAU'

    def handle(self, *args, **kwargs):
        templates = TemplateBAU.objects.all()
        today = date.today()
        count = 0

        self.stdout.write("Memulai proses generate BAU...")

        for tmpl in templates:
            # Tentukan Start/End date berdasarkan frekuensi
            start_date = today
            due_date = today
            suffix_code = ""

            if tmpl.frekuensi == 'WEEKLY':
                # Logic: Generate untuk minggu ini jika belum ada
                start_of_week = today - timedelta(days=today.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                suffix_code = f"W{today.isocalendar()[1]}" # W42 (Minggu ke-42)
                start_date = start_of_week
                due_date = end_of_week

            elif tmpl.frekuensi == 'MONTHLY':
                # Logic: Generate untuk bulan ini jika belum ada
                suffix_code = today.strftime("%b-%Y") # Nov-2025
                # Awal bulan & Akhir bulan (simple logic)
                start_date = today.replace(day=1)
                import calendar
                last_day = calendar.monthrange(today.year, today.month)[1]
                due_date = today.replace(day=last_day)

            # --- CEK DUPLIKASI ---
            # Kita cek apakah sudah ada tugas dengan nama mirip di periode ini
            nama_tugas_baru = f"{tmpl.nama_tugas} ({suffix_code})"
            
            exists = Tugas.objects.filter(
                nama_tugas=nama_tugas_baru,
                pemilik_grup=tmpl.pemilik_grup
            ).exists()

            if not exists:
                # Buat Tugas Baru
                Tugas.objects.create(
                    nama_tugas=nama_tugas_baru,
                    tipe_tugas='BAU',
                    tanggal_mulai=start_date,
                    tenggat_waktu=due_date,
                    ditugaskan_ke=tmpl.default_pic,
                    pemilik_grup=tmpl.pemilik_grup,
                    status='TODO',
                    progress=0
                )
                self.stdout.write(self.style.SUCCESS(f"Generated: {nama_tugas_baru}"))
                count += 1
            else:
                self.stdout.write(f"Skipped: {nama_tugas_baru} (Already exists)")

        self.stdout.write(self.style.SUCCESS(f"Selesai! {count} tugas baru dibuat."))