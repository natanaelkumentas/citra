# main.py — Entry point aplikasi (menggantikan Start.py)
# Jalankan: python main.py

from ui.windows.main_window import CameraApp


def main():
    app = CameraApp()
    app.run()


if __name__ == "__main__":
    main()
