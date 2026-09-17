import sys
from PySide6.QtWidgets import QApplication
import config
from lib.logger import setup_logging
from gui.main_window import MainWindow
from gui.controller import Controller

def _prepare_windows():
    """让 Windows 任务栏把本程序当成独立应用（否则源码运行时显示 Python 图标、无法固定）。"""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("sangokvip.javscraper")
    except Exception:
        pass


def main():
    setup_logging()
    config.migrate_legacy_configs()
    _prepare_windows()
    app = QApplication(sys.argv)
    window = MainWindow()
    controller = Controller(window)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
