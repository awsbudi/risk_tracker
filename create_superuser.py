import os
import django

# Setup environment Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "risk_tracker.settings")
django.setup()

from django.contrib.auth.models import User

# --- KONFIGURASI ADMIN ---
# Ganti password ini dengan yang Anda mau
USERNAME = 'admin'
EMAIL = 'admin@kantor.com'
PASSWORD = 'RiskManager2025!' 

def create_admin():
    if not User.objects.filter(username=USERNAME).exists():
        print(f"Creating superuser: {USERNAME}...")
        User.objects.create_superuser(USERNAME, EMAIL, PASSWORD)
        print("Superuser created successfully!")
    else:
        print(f"Superuser {USERNAME} already exists. Skipping.")

if __name__ == "__main__":
    create_admin()