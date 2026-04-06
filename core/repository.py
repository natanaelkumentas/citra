# core/repository.py — Manajemen folder penyimpanan lokal
# Salin persis dari repository.py lama. Isi tidak berubah.

import os


class AppRepository:
    def __init__(self, base_dir=None):
        base_path = base_dir or os.getcwd()
        self.drive_folder = os.path.join(base_path, "Drive_Local")
        if not os.path.exists(self.drive_folder):
            os.makedirs(self.drive_folder)

        self.gdrive_link = "https://drive.google.com/drive/folders/1gaDzV0LcwAUo8n-DmGdlNS9dyLRf-guE"

    def get_drive_folder(self):
        return self.drive_folder

    def get_gdrive_link(self):
        return self.gdrive_link
