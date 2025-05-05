# ui/settings_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QGroupBox, QMessageBox, QKeySequenceEdit,
    QDialogButtonBox, QCheckBox
)
from PyQt6.QtGui import QKeySequence, QDesktopServices # For opening URL
from PyQt6.QtCore import Qt, QUrl,pyqtSignal
from core import config_manager, gemini_api # Needed to test API key
import google.generativeai as genai
class SettingsDialog(QDialog):
    # Signal to indicate hotkeys might have changed, requiring listener restart
    hotkeys_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450) # Set a minimum width
        self.setModal(True) # Block interaction with main window

        # Layouts
        main_layout = QVBoxLayout(self)

        # --- API Key Section ---
        api_group = QGroupBox("Gemini API Configuration")
        api_layout = QFormLayout(api_group)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter your Google AI Studio API Key")

        # Add a button/link to get API key
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(self.api_key_input)
        get_api_key_button = QPushButton("Get API Key")
        get_api_key_button.setToolTip("Open Google AI Studio in your browser (requires Google account)")
        get_api_key_button.clicked.connect(self.open_ai_studio)
        api_key_layout.addWidget(get_api_key_button)

        api_layout.addRow("API Key:", api_key_layout)

        # Optional: Add a button to test the API key
        self.test_api_button = QPushButton("Test API Key")
        self.test_api_button.clicked.connect(self.test_api_key)
        api_layout.addRow("", self.test_api_button) # Add button without label

        main_layout.addWidget(api_group)


        # --- Hotkeys Section ---
        hotkey_group = QGroupBox("Global Hotkeys")
        hotkey_layout = QFormLayout(hotkey_group)
        self.toggle_visibility_input = QKeySequenceEdit()
        self.screenshot_full_input = QKeySequenceEdit()
        hotkey_layout.addRow("Toggle App Visibility:", self.toggle_visibility_input)
        hotkey_layout.addRow("Capture Fullscreen:", self.screenshot_full_input)
        main_layout.addWidget(hotkey_group)

        # --- UI Settings (Example) ---
        ui_group = QGroupBox("Interface")
        ui_layout = QFormLayout(ui_group)
        self.always_on_top_checkbox = QCheckBox("Keep window always on top")
        ui_layout.addRow(self.always_on_top_checkbox)
        main_layout.addWidget(ui_group)


        # --- Standard Buttons ---
        # Using QDialogButtonBox for standard OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept) # Triggers save_settings via accept() override
        button_box.rejected.connect(self.reject) # Closes dialog

        main_layout.addWidget(button_box)

        # Store initial hotkey values to check for changes
        self._initial_toggle_hotkey = ""
        self._initial_screenshot_hotkey = ""

        # --- Load initial values ---
        self.load_settings()


    def load_settings(self):
        """ Load settings from config manager """
        self.api_key_input.setText(config_manager.get_setting('API', 'api_key'))
        self.always_on_top_checkbox.setChecked(config_manager.get_setting('UI', 'always_on_top') == 'True')

        # Load hotkeys and store initial values
        toggle_seq_str = config_manager.get_setting('Hotkeys', 'toggle_visibility')
        ss_seq_str = config_manager.get_setting('Hotkeys', 'screenshot_full')

        self._initial_toggle_hotkey = toggle_seq_str
        self._initial_screenshot_hotkey = ss_seq_str

        # Set QKeySequenceEdit widgets
        toggle_sequence = QKeySequence.fromString(toggle_seq_str, QKeySequence.SequenceFormat.PortableText)
        ss_sequence = QKeySequence.fromString(ss_seq_str, QKeySequence.SequenceFormat.PortableText)

        self.toggle_visibility_input.setKeySequence(toggle_sequence)
        self.screenshot_full_input.setKeySequence(ss_sequence)


    def save_settings(self):
        """ Save settings back to config manager """
        # Save API Key
        api_key = self.api_key_input.text()
        # Don't require API key here, allow saving empty key
        config_manager.set_setting('API', 'api_key', api_key)

        # Save UI Settings
        config_manager.set_setting('UI', 'always_on_top', str(self.always_on_top_checkbox.isChecked()))

        # Save Hotkeys
        toggle_seq = self.toggle_visibility_input.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        ss_seq = self.screenshot_full_input.keySequence().toString(QKeySequence.SequenceFormat.PortableText)

        # Allow empty hotkeys to disable them
        config_manager.set_setting('Hotkeys', 'toggle_visibility', toggle_seq)
        config_manager.set_setting('Hotkeys', 'screenshot_full', ss_seq)

        # Check if hotkeys actually changed
        hotkeys_changed = (toggle_seq != self._initial_toggle_hotkey or
                           ss_seq != self._initial_screenshot_hotkey)

        print("Settings saved.")
        return hotkeys_changed # Return whether hotkeys were modified


    def accept(self):
        """ Overrides QDialog.accept() to save before closing """
        hotkeys_changed = self.save_settings()
        if hotkeys_changed:
             print("Hotkeys updated, emitting signal.")
             self.hotkeys_updated.emit()
        super().accept() # Call the original accept to close the dialog with QDialog.Accepted


    def open_ai_studio(self):
        """ Opens the Google AI Studio URL in the default browser """
        url = QUrl("https://aistudio.google.com/app/apikey")
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "Could Not Open URL",
                                f"Could not open the Gemini API key page.\n"
                                f"Please manually visit: {url.toString()}")

    def test_api_key(self):
        """ Attempts to list models using the entered API key """
        temp_key = self.api_key_input.text()
        if not temp_key:
            QMessageBox.warning(self, "Test API Key", "Please enter an API key to test.")
            return

        # Temporarily configure genai with the key from the input field
        original_configured_state = gemini_api._genai_configured
        original_key = config_manager.get_setting('API', 'api_key')
        try:
             # Configure with the key from the input field
             print(f"Testing with key: ...{temp_key[-4:]}") # Show only last 4 chars
             temp_config_success = False
             try:
                 genai.configure(api_key=temp_key)
                 temp_config_success = True
             except Exception as config_e:
                 QMessageBox.critical(self, "API Key Test Failed", f"Failed to configure API client: {config_e}")
                 return # Exit if configuration itself fails

             if temp_config_success:
                 # Try listing models as a simple validation check
                 models = gemini_api.list_models() # This uses the temporary configuration
                 if models and not models[0].startswith("Error:"):
                     QMessageBox.information(self, "API Key Test Successful",
                                             f"Successfully connected and found models (e.g., {models[0]}).\n"
                                             "Remember to save the settings.")
                 else:
                     error_msg = models[0] if models else "Unknown error listing models"
                     QMessageBox.warning(self, "API Key Test Failed",
                                         f"Could not list models using this key.\nError: {error_msg}")

        except Exception as e:
            QMessageBox.critical(self, "API Key Test Error", f"An unexpected error occurred during testing: {e}")
        finally:
             # IMPORTANT: Restore original genai configuration state
             if original_key:
                 print("Restoring original API key configuration.")
                 try:
                      genai.configure(api_key=original_key)
                      gemini_api._genai_configured = original_configured_state # Restore flag too
                 except Exception as restore_e:
                      print(f"Warning: Could not restore original API config: {restore_e}")
                      gemini_api._genai_configured = False # Mark as unconfigured if restore failed
             else:
                  # If there was no original key, ensure it's marked as unconfigured
                  print("No original key to restore, marking GenAI as unconfigured.")
                  gemini_api._genai_configured = False
                  # Clear any potentially lingering client state if the library allows
                  # (google-genai might not have an explicit deconfigure/reset)


