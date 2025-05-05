# main.py
import sys
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer # For graceful exit on Ctrl+C

from ui.main_window import MainWindow
from core import db_manager # Ensure DB is initialized

def main():
    # Allow Ctrl+C to kill application
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("GeminiChatApp")
    app.setOrganizationName("YourAppName") # Used for settings path

    # Ensure config/db directories exist (db_manager initializes itself)
    db_manager.initialize_db() # Redundant if already done in db_manager, but safe

    main_window = MainWindow()
    # Decide initial state (e.g., start minimized/hidden based on a setting)
    # if config_manager.get_setting('UI', 'start_minimized') == 'True':
    #     main_window.hide() # Start hidden in tray
    # else:
    main_window.show()

    # Set up a timer to allow Python interpreter to handle signals like Ctrl+C
    timer = QTimer()
    timer.start(500)  # Check every 500 ms
    timer.timeout.connect(lambda: None) # Does nothing, just keeps event loop running

    # Connect cleanup function to application's aboutToQuit signal
    app.aboutToQuit.connect(main_window.cleanup)

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
