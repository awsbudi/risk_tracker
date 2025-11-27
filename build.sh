#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install Library
pip install -r requirements.txt

# 2. Siapkan Static Files (CSS/JS)
python manage.py collectstatic --no-input

# 3. Migrasi Database (Buat Tabel di Cloud)
python manage.py migrate