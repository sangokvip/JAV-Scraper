import sys
from PySide6.QtWidgets import QApplication
import config
from gui.main_window import MainWindow
from gui.controller import Controller

def main():
    config.migrate_legacy_configs()
    app = QApplication(sys.argv)
    window = MainWindow()
    controller = Controller(window)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
