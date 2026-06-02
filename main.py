import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.controller import Controller

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    controller = Controller(window)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
