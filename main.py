import sys
from PySide6.QtWidgets import QApplication
import config
from lib.logger import setup_logging
from gui.main_window import MainWindow
from gui.controller import Controller

def main():
    setup_logging()
    config.migrate_legacy_configs()
    app = QApplication(sys.argv)
    window = MainWindow()
    controller = Controller(window)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
