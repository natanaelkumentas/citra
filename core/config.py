# core/config.py — Konfigurasi global aplikasi
# Semua nilai hardcoded dikumpulkan di sini.
# Jika ada nilai yang perlu diganti, cukup ubah di file ini.

# ── Supabase ──
SUPABASE_URL = "https://lvvaydjnadyywvdbiueu.supabase.co"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2dmF5ZGpuYWR5eXd2ZGJpdWV1Iiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3NzA3MDQ0ODIsImV4cCI6MjA4NjI4MDQ4Mn0."
    "PjWS-pF5M0nW5WzcI77Ux26OI-_nVt_mRxkFrtgZc68"
)

# Nama tabel Supabase
SUPABASE_TABLE_IMAGE_STATS = "image_statistics"   # dipakai ImageAnalysisWindow
SUPABASE_TABLE_ANALISIS    = "analisis_gambar"    # dipakai AnalisisWarnaWindow

# ── IoT / ESP32 ──
ESP32_DEFAULT_HOST = "10.192.232.248"

# ── Kamera ──
DEFAULT_CAMERA_URL   = "http://172.29.241.86:8081/video"
DEFAULT_CAMERA_INDEX = 0

# ── Penyimpanan ──
GDRIVE_LINK = "https://drive.google.com/drive/folders/1gaDzV0LcwAUo8n-DmGdlNS9dyLRf-guE"
