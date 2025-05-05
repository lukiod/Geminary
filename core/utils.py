# core/utils.py
from PyQt6.QtWidgets import QMessageBox

def show_error_message(parent, title, message):
    """Displays a standard critical error message box."""
    # Ensure parent is passed correctly, defaults to None if not provided
    msgBox = QMessageBox(parent)
    msgBox.setIcon(QMessageBox.Icon.Critical)
    msgBox.setWindowTitle(title)
    msgBox.setText(message)
    msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
    msgBox.exec()


def show_info_message(parent, title, message):
     """Displays a standard information message box."""
     msgBox = QMessageBox(parent)
     msgBox.setIcon(QMessageBox.Icon.Information)
     msgBox.setWindowTitle(title)
     msgBox.setText(message)
     msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
     msgBox.exec()

def show_warning_message(parent, title, message):
     """Displays a standard warning message box."""
     msgBox = QMessageBox(parent)
     msgBox.setIcon(QMessageBox.Icon.Warning)
     msgBox.setWindowTitle(title)
     msgBox.setText(message)
     msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
     msgBox.exec()

# Add other common utility functions as needed, e.g., text formatting, file operations etc.

