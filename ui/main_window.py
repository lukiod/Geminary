# ui/main_window.py
import sys
import datetime
import platform # For OS specific adjustments
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QLineEdit,
    QPushButton, QComboBox, QMenuBar, QMenu, QMessageBox, QFileDialog,
    QSystemTrayIcon, QApplication, QLabel, QSplitter, QListWidget, QListWidgetItem,
    QStatusBar, QSizePolicy, QProgressBar
)
from PyQt6.QtGui import (
    QAction, QIcon, QTextCursor, QColor, QPixmap, QKeySequence, QDesktopServices,
    QFont, QPalette # For text color
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QThread, QSettings, QTimer, QUrl, QSize, QEvent, QObject,
    QMetaObject, Q_ARG # For invokeMethod
)

from core import config_manager, db_manager, gemini_api, screenshot, utils
from core.hotkey_listener import HotkeyListener
from .settings_dialog import SettingsDialog

# --- Globals ---
# Try to find icon relative to script location, robust for packaging
try:
    import os
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ICON_PATH = os.path.join(BASE_DIR, "icons", "app_icon.png")
    if not os.path.exists(ICON_PATH):
         # Fallback if structure is different during development/packaging
         ICON_PATH = os.path.join(os.path.dirname(BASE_DIR), "ui", "icons", "app_icon.png")
    if not os.path.exists(ICON_PATH):
        print(f"Warning: Icon file not found at expected paths: {ICON_PATH}")
        ICON_PATH = "" # Set to empty if not found
except Exception as e:
    print(f"Warning: Could not determine icon path: {e}")
    ICON_PATH = ""


# --- Worker Thread for API Calls ---
class Worker(QThread):
    """ Worker thread for long-running tasks like API calls """
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt, model_name):
        super().__init__()
        self.prompt = prompt
        self.model_name = model_name
        self._is_running = True

    def run(self):
        if not self._is_running: return # Check before starting
        try:
            response = gemini_api.send_query(self.prompt, self.model_name)
            if self._is_running: # Check again before emitting
                self.response_ready.emit(response)
        except Exception as e:
            if self._is_running:
                # Be more specific about the error type if possible
                error_msg = f"Worker thread error: {type(e).__name__}: {e}"
                print(error_msg) # Log it too
                self.error_occurred.emit(error_msg)

    def stop(self):
        print("API Worker stop requested.")
        self._is_running = False


# --- Main Application Window ---
class MainWindow(QMainWindow):
    # Signal to safely update GUI from other threads (like hotkey listener)
    safe_toggle_visibility = pyqtSignal()
    safe_take_screenshot = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini Chat")
        if ICON_PATH:
            self.setWindowIcon(QIcon(ICON_PATH))
        self.setGeometry(150, 150, 750, 550) # x, y, width, height

        # Initial config load
        self.config = config_manager.load_config()
        self.current_model = config_manager.get_setting('Models', 'selected_model')
        self.api_worker = None
        self.hotkey_listener = None
        self._is_visible_state = True # Track desired visibility state

        # --- Main Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5) # Reduce margins
        main_layout.setSpacing(5) # Reduce spacing


        # --- Top Bar (Model Selection & Refresh) ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Select the Gemini model to use")
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_bar_layout.addWidget(self.model_combo)

        refresh_models_button = QPushButton()
        refresh_models_button.setIcon(QIcon.fromTheme("view-refresh", QIcon(":/qt-project.org/styles/commonstyle/images/refresh-32.png"))) # Use themed icon with fallback
        refresh_models_button.setToolTip("Refresh model list from API (requires valid API key)")
        refresh_models_button.clicked.connect(self.refresh_models_action)
        refresh_models_button.setFixedSize(QSize(28, 28)) # Make button small
        top_bar_layout.addWidget(refresh_models_button)

        main_layout.addLayout(top_bar_layout)


        # --- Chat Display Area ---
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        # Use system default colors for better theme integration initially
        # self.chat_display.setStyleSheet("background-color: #f0f0f0;")
        main_layout.addWidget(self.chat_display, 1) # Give stretch factor


        # --- Input Area ---
        input_layout = QHBoxLayout()
        self.input_area = QLineEdit()
        self.input_area.setPlaceholderText("Type your message, press Enter to send...")
        self.input_area.setToolTip("Enter your query for the Gemini model here")
        input_layout.addWidget(self.input_area)

        self.send_button = QPushButton("Send")
        self.send_button.setToolTip("Send the message to the selected Gemini model")
        self.send_button.setMinimumWidth(60)
        input_layout.addWidget(self.send_button)

        main_layout.addLayout(input_layout)


        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready") # Permanent label on the left
        self.status_bar.addWidget(self.status_label, 1) # Add label with stretch
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumSize(150, 15) # Small progress bar
        self.progress_bar.setVisible(False) # Hide initially
        self.status_bar.addPermanentWidget(self.progress_bar) # Add to the right
        self.set_status("Ready", 3000)


        # --- System Tray Icon ---
        self.create_tray_icon()

        # --- Menu Bar ---
        self.create_menus()

        # --- Initial Setup ---
        self.populate_models() # Populate initially
        self.load_chat_history()
        self.apply_settings() # Apply UI settings like always-on-top


        # --- Connections ---
        self.send_button.clicked.connect(self.send_message)
        self.input_area.returnPressed.connect(self.send_message)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)

        # Connect safe signals for cross-thread GUI updates
        self.safe_toggle_visibility.connect(self.toggle_visibility)
        self.safe_take_screenshot.connect(self.take_screenshot_full)


        # --- Start Hotkey Listener ---
        # Needs to start after main window setup is complete
        QTimer.singleShot(100, self.setup_hotkey_listener)

        # --- Initial API Key Check ---
        if not config_manager.get_setting('API', 'api_key'):
             # Don't show popup immediately, let user settle
             QTimer.singleShot(1500, self.show_api_key_warning_once)
             # Optionally open settings automatically on first ever run
             # self.check_first_run_and_open_settings()


    def create_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("Warning: System tray not available on this system.")
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(self)
        if ICON_PATH:
            self.tray_icon.setIcon(QIcon(ICON_PATH))
        else:
            # Fallback if icon missing
            self.tray_icon.setIcon(QIcon.fromTheme("applications-internet"))
        self.tray_icon.setToolTip("Gemini Chat")

        tray_menu = QMenu()
        show_action = QAction("Show/Hide Window", self)
        settings_action_tray = QAction("Settings...", self)
        quit_action_tray = QAction("Quit", self)

        show_action.triggered.connect(self.toggle_visibility)
        settings_action_tray.triggered.connect(self.open_settings)
        # Ensure quit actually quits the application
        quit_action_tray.triggered.connect(self.quit_application)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(settings_action_tray)
        tray_menu.addAction(quit_action_tray)

        self.tray_icon.setContextMenu(tray_menu)
        # Handle click events (single click toggles visibility)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        print("System tray icon created.")


    def create_menus(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        settings_action = QAction(QIcon.fromTheme("preferences-system"), "&Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,") if platform.system() != "Darwin" else QKeySequence("Cmd+,"))
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()

        export_action = QAction(QIcon.fromTheme("document-save"), "&Export History...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_history)
        file_menu.addAction(export_action)

        clear_action = QAction(QIcon.fromTheme("edit-clear"), "Clear &History", self)
        clear_action.setShortcut(QKeySequence("Ctrl+Shift+Del"))
        clear_action.triggered.connect(self.clear_history)
        file_menu.addAction(clear_action)

        file_menu.addSeparator()
        # Use a dedicated quit action connected to the proper exit handler
        quit_action = QAction(QIcon.fromTheme("application-exit"), "&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q") if platform.system() != "Darwin" else QKeySequence("Cmd+Q"))
        quit_action.triggered.connect(self.quit_application)
        file_menu.addAction(quit_action)

        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        ss_full_action = QAction("Take &Fullscreen Screenshot", self)
        # Set shortcut based on config (will be updated if changed in settings)
        self.ss_full_action = ss_full_action # Store reference to update shortcut later
        self.update_screenshot_shortcut()
        ss_full_action.triggered.connect(self.safe_take_screenshot) # Use safe signal if called from menu
        tools_menu.addAction(ss_full_action)

        refresh_models_menu_action = QAction(QIcon.fromTheme("view-refresh"), "&Refresh Model List", self)
        refresh_models_menu_action.triggered.connect(self.refresh_models_action)
        tools_menu.addAction(refresh_models_menu_action)


        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About Gemini Chat", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def update_screenshot_shortcut(self):
         """ Updates the menu item shortcut display based on config """
         if hasattr(self, 'ss_full_action'):
             ss_hotkey_str = config_manager.get_setting('Hotkeys', 'screenshot_full')
             if ss_hotkey_str:
                 qt_sequence = QKeySequence.fromString(ss_hotkey_str, QKeySequence.SequenceFormat.PortableText)
                 self.ss_full_action.setShortcut(qt_sequence)
                 print(f"Screenshot menu shortcut updated to: {qt_sequence.toString()}")
             else:
                 self.ss_full_action.setShortcut(QKeySequence()) # Clear shortcut if empty
                 print("Screenshot menu shortcut cleared.")


    def setup_hotkey_listener(self):
        """ Stops existing listener (if any) and starts a new one based on current config. """
        if self.hotkey_listener and self.hotkey_listener.is_alive():
            print("Stopping existing hotkey listener...")
            self.hotkey_listener.stop()
            self.hotkey_listener = None # Clear reference

        hotkey_config = {
            'toggle_visibility': config_manager.get_setting('Hotkeys', 'toggle_visibility'),
            'screenshot_full': config_manager.get_setting('Hotkeys', 'screenshot_full')
        }
        # Only start if at least one hotkey is configured
        if hotkey_config['toggle_visibility'] or hotkey_config['screenshot_full']:
            try:
                self.hotkey_listener = HotkeyListener(hotkey_config)
                # Connect signals from listener thread to GUI thread using safe signals/invokeMethod
                # Using invokeMethod for thread safety is generally robust
                self.hotkey_listener.toggle_visibility_triggered.connect(
                    lambda: QMetaObject.invokeMethod(self, "toggle_visibility", Qt.ConnectionType.QueuedConnection)
                )
                self.hotkey_listener.screenshot_full_triggered.connect(
                    lambda: QMetaObject.invokeMethod(self, "take_screenshot_full", Qt.ConnectionType.QueuedConnection)
                )

                # # Alternative using custom safe signals:
                # self.hotkey_listener.toggle_visibility_triggered.connect(self.safe_toggle_visibility.emit)
                # self.hotkey_listener.screenshot_full_triggered.connect(self.safe_take_screenshot.emit)

                self.hotkey_listener.start()
            except Exception as e:
                 print(f"Error starting hotkey listener thread: {e}")
                 utils.show_error_message(self, "Hotkey Error", f"Could not start the global hotkey listener.\nError: {e}\n\nHotkeys will be disabled.")
                 self.hotkey_listener = None # Ensure it's None if start failed
        else:
             print("Hotkey listener not started: No hotkeys configured.")
             # self.set_status("Global hotkeys are disabled.", 5000)


    def refresh_models_action(self):
         """ Slot for the refresh models button/menu item. """
         if not gemini_api._genai_configured:
             if not gemini_api.configure_genai():
                 utils.show_warning_message(self, "API Key Needed", "Cannot refresh models. Please configure a valid Gemini API key in Settings first.")
                 return
         # Proceed with populating models
         self.populate_models()

    def populate_models(self):
        """Fetches and populates the model dropdown. Shows progress."""
        self.set_status("Fetching models...", 0) # Persistent status
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate progress
        self.model_combo.setEnabled(False)
        QApplication.processEvents() # Update UI immediately

        # --- Use a simple QTimer to simulate async fetch ---
        # A dedicated thread would be better for true non-blocking fetch
        def fetch_and_update():
            available_models = gemini_api.list_models()
            self.progress_bar.setVisible(False)
            self.model_combo.setEnabled(True)

            self.model_combo.blockSignals(True)
            self.model_combo.clear()

            if available_models and not available_models[0].startswith("Error:"):
                self.model_combo.addItems(available_models)
                self.set_status(f"{len(available_models)} models loaded.", 3000)
                # Update config with newly fetched models
                config_manager.set_setting('Models', 'available_models', ",".join(available_models))

                # Try to restore previous selection
                saved_model = config_manager.get_setting('Models', 'selected_model')
                if saved_model in available_models:
                     self.model_combo.setCurrentText(saved_model)
                     self.current_model = saved_model # Ensure state matches
                elif available_models:
                    self.model_combo.setCurrentIndex(0)
                    self.current_model = self.model_combo.currentText()
                    config_manager.set_setting('Models', 'selected_model', self.current_model) # Save the fallback selection
                else: # Should not happen if list isn't empty, but defensively:
                     self.current_model = None

            else:
                # Handle error case
                error_msg = available_models[0] if available_models else "Error: No models found or API error."
                self.set_status(f"Model loading failed: {error_msg}", 5000)
                utils.show_warning_message(self, "Model Loading Error", f"Could not load models.\n{error_msg}")
                # Fallback to config if API failed
                config_models_str = config_manager.get_setting('Models', 'available_models')
                fallback_models = config_models_str.split(',') if config_models_str else ["gemini-1.5-flash-latest"]
                self.model_combo.addItems(fallback_models)
                if fallback_models:
                     saved_model = config_manager.get_setting('Models', 'selected_model')
                     if saved_model in fallback_models:
                         self.model_combo.setCurrentText(saved_model)
                         self.current_model = saved_model
                     else:
                         self.model_combo.setCurrentIndex(0)
                         self.current_model = self.model_combo.currentText()
                         # Don't save fallback model from config back to config unless user selects it
                else:
                    self.current_model = None # No models available

            self.model_combo.blockSignals(False)
            # Ensure current model state is correct after population
            if self.model_combo.count() > 0:
                 self.on_model_changed(self.model_combo.currentText()) # Sync state


        # Use a short delay to allow UI to update before potentially blocking API call
        QTimer.singleShot(50, fetch_and_update)


    def on_model_changed(self, model_name):
        """Stores the selected model in config if valid."""
        if model_name and not model_name.startswith("Error:") and self.current_model != model_name:
            print(f"Model selection changed to: {model_name}")
            self.current_model = model_name
            config_manager.set_setting('Models', 'selected_model', model_name)
            self.set_status(f"Model set to: {model_name}", 3000)


    def show_api_key_warning_once(self):
        """ Shows API key warning only if key is still missing. """
        if not config_manager.get_setting('API', 'api_key'):
             utils.show_warning_message(self, "API Key Missing",
                                    "Your Gemini API Key is not configured.\n"
                                    "Please go to File -> Settings to add your key.\n\n"
                                    "The application may not function correctly without it.")


    def add_message_to_display(self, role, text, model_used=None):
        """Appends a message to the chat display with role-based formatting."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)

        now = datetime.datetime.now().strftime("%H:%M:%S") # Shorter timestamp

        # Define colors (consider making these configurable)
        user_color = "#0000AA" # Dark Blue
        model_color = "#006400" # Dark Green
        error_color = "#CC0000" # Red
        system_color = "#555555" # Grey

        # Use HTML for formatting
        if role == "user":
            prefix = f'<b style="color:{user_color};">You ({now}):</b>'
            content_html = text.replace('\n', '<br/>') # Basic newline handling
        elif role == "model":
             model_name = model_used or "Gemini"
             prefix = f'<b style="color:{model_color};">{model_name} ({now}):</b>'
             # Basic markdown interpretation could go here (e.g., **bold**, *italic*)
             # For now, just escape HTML and handle newlines
             content_html = text.replace('&', '&').replace('<', '<').replace('>', '>').replace('\n', '<br/>')
        elif role == "error":
             prefix = f'<b style="color:{error_color};">Error ({now}):</b>'
             content_html = text.replace('\n', '<br/>')
        else: # System messages
             content_html = f'<i>{text.replace("<", "<").replace(">", ">").replace("/n", "<br/>")}</i>'
             prefix = f'<b style="color:{error_color};">Error ({now}):</b>'

        formatted_message = f'<p style="margin-bottom: 5px;">{prefix}<br/>{content_html}</p>'

        self.chat_display.insertHtml(formatted_message)
        # Ensure the view scrolls to the bottom
        self.chat_display.ensureCursorVisible()


    def load_chat_history(self):
        """Loads history from DB and displays it."""
        self.chat_display.clear()
        history = db_manager.get_history(limit=100) # Get recent history
        self.set_status("Loading history...", 1000)
        QApplication.processEvents()

        for timestamp, role, content, model_used in history:
            # Convert timestamp if needed (assuming it's stored correctly)
            # ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if isinstance(timestamp, datetime.datetime) else str(timestamp).split('.')[0]
            # Simplified add_message call for history
            self.add_message_to_display(role, content, model_used)

        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
        self.set_status("History loaded.", 2000)


    def send_message(self):
        """Validates input and starts the API call process."""
        user_input = self.input_area.text().strip()
        if not user_input:
            return

        if not self.current_model or self.current_model.startswith("Error:"):
            utils.show_warning_message(self, "Model Not Selected", "Please select a valid Gemini model from the dropdown.")
            return

        if not gemini_api._genai_configured:
             if not gemini_api.configure_genai(): # Try to configure on the fly
                self.show_api_key_warning_once()
                utils.show_error_message(self, "API Key Error", "Cannot send message. API key is missing or invalid. Please check Settings.")
                return

        # Display user message and add to DB
        self.add_message_to_display("user", user_input)
        db_manager.add_message(role="user", content=user_input)
        self.input_area.clear()

        # Disable input, show progress
        self.set_input_enabled(False)
        self.set_status(f"Sending to {self.current_model}...", 0)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate

        # Stop previous worker if it exists and is running
        if self.api_worker and self.api_worker.isRunning():
            self.api_worker.stop()
            # Don't wait here, let finished signal handle cleanup

        # Start new worker thread
        print(f"Starting API worker for model {self.current_model}")
        self.api_worker = Worker(user_input, self.current_model)
        self.api_worker.response_ready.connect(self.handle_response)
        self.api_worker.error_occurred.connect(self.handle_api_error)
        # Connect finished signal regardless of success/error for cleanup
        self.api_worker.finished.connect(self.on_worker_finished)
        self.api_worker.start()


    def set_input_enabled(self, enabled: bool):
        """ Helper to enable/disable input elements """
        self.input_area.setEnabled(enabled)
        self.send_button.setEnabled(enabled)


    def handle_response(self, response_text):
        """Handles the successful response received from the API worker."""
        print("API worker returned response.")
        # Check if the response indicates an API-level error/block
        if response_text.startswith("Error:") or response_text.startswith("Blocked:"):
            self.handle_api_error(response_text) # Treat as error
        else:
            self.add_message_to_display("model", response_text, model_used=self.current_model)
            db_manager.add_message(role="model", content=response_text, model_used=self.current_model)
            self.set_status("Response received.", 3000)


    def handle_api_error(self, error_message):
        """Handles errors reported by the API worker or detected in response."""
        print(f"API worker reported error: {error_message}")
        self.add_message_to_display("error", error_message)
        # Log error to DB? Maybe only for specific types? For now, just display.
        # db_manager.add_message(role="system", content=f"API Error: {error_message}")
        self.set_status("API Error occurred.", 5000)


    def on_worker_finished(self):
        """Called when the API worker thread finishes (success, error, or stopped)."""
        print("API worker finished.")
        self.set_input_enabled(True)
        self.progress_bar.setVisible(False)
        # Clear status only if it wasn't showing a recent error
        if "Error" not in self.status_label.text():
             self.set_status("Ready", 3000)
        # Ensure reference is cleared
        # self.api_worker = None # Careful: might be problematic if accessed right after finish signal

    def take_screenshot_full(self):
        """Captures fullscreen and copies to clipboard using Qt."""
        self.set_status("Capturing screenshot...", 0)
        QApplication.processEvents()

        img_bytes = screenshot.capture_fullscreen()
        if img_bytes:
            try:
                pixmap = QPixmap()
                # Explicitly specify format hint for reliability
                if pixmap.loadFromData(img_bytes, "PNG"):
                    QApplication.clipboard().setPixmap(pixmap)
                    self.set_status("Screenshot copied to clipboard.", 3000)
                    # Briefly flash tray icon?
                    if self.tray_icon:
                         self.tray_icon.showMessage("Screenshot", "Copied to clipboard", QSystemTrayIcon.MessageIcon.Information, 1500)
                else:
                     raise ValueError("Failed to load screenshot PNG data into QPixmap")
            except Exception as e:
                error_msg = f"Could not copy screenshot to clipboard.\nError: {e}"
                print(f"Screenshot Error: {error_msg}")
                self.set_status("Error copying screenshot.", 5000)
                utils.show_error_message(self, "Screenshot Error", error_msg)
        else:
            error_msg = "Failed to capture the screen. Check logs for details."
            print(f"Screenshot Error: {error_msg}")
            self.set_status("Screenshot capture failed.", 5000)
            utils.show_error_message(self, "Screenshot Error", error_msg)

    # --- Window Visibility and Tray Interaction ---

    def toggle_visibility(self):
        """Shows or hides the main window safely."""
        print(f"Toggle visibility called. Current state: {'Visible' if self.isVisible() else 'Hidden'}")
        if self.isVisible():
             self.hide()
             self._is_visible_state = False
             print("Window hidden.")
        else:
             self.showNormal() # Restore from minimized or hidden state
             self.activateWindow() # Bring to front
             self.raise_()       # Ensure it's raised on systems like macOS
             self._is_visible_state = True
             print("Window shown and activated.")
             self.input_area.setFocus() # Set focus to input when shown


    def on_tray_icon_activated(self, reason):
        """Handle clicks on the tray icon."""
        # Show/Hide on left-click (Trigger) or double-click
        if reason == QSystemTrayIcon.ActivationReason.Trigger or reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_visibility()
        # Context menu (right-click) is handled by Qt automatically

    def changeEvent(self, event):
         """ Handle window state changes like minimize. """
         if event.type() == QEvent.Type.WindowStateChange:
             if self.windowState() & Qt.WindowState.WindowMinimized:
                 # Option 1: Minimize to taskbar (default behavior)
                 # print("Window minimized to taskbar.")
                 # Option 2: Hide to tray when minimized
                 # self.hide()
                 # self._is_visible_state = False
                 # if self.tray_icon:
                 #      self.tray_icon.showMessage("Minimized", "App hidden to tray.", QSystemTrayIcon.MessageIcon.Information, 1500)
                 pass # Let Qt handle normal minimize for now
             elif event.oldState() & Qt.WindowState.WindowMinimized:
                  # print("Window restored from minimize.")
                  self._is_visible_state = True # Assume visible when restored

         super().changeEvent(event)


    def closeEvent(self, event):
        """Override close event ('X' button) to hide to tray instead of quitting."""
        print("Close event triggered (X button). Hiding window.")
        event.ignore() # Prevent the window from actually closing
        self.hide()
        self._is_visible_state = False
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Gemini Chat Hidden",
                "Application is running in the system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                2000 # Show message for 2 seconds
            )

    # --- Dialogs and Actions ---

    def apply_settings(self):
         """ Apply settings that affect the UI directly """
         # Always on Top
         always_on_top = config_manager.get_setting('UI', 'always_on_top') == 'True'
         if always_on_top:
             self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
         else:
             self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
         # Re-show the window to apply flag changes if it's visible
         if self.isVisible():
             self.show()
         print(f"Always on top setting applied: {always_on_top}")

         # Update shortcuts displayed in menus
         self.update_screenshot_shortcut()


    def open_settings(self):
        dialog = SettingsDialog(self)
        # Connect signal from dialog to restart listener if needed
        dialog.hotkeys_updated.connect(self.setup_hotkey_listener)

        if dialog.exec(): # exec() returns True if accepted (Save clicked)
            print("Settings dialog accepted (saved).")
            # Reload config and apply relevant changes immediately
            self.config = config_manager.load_config()
            self.apply_settings() # Apply UI changes like always-on-top

            # API key might have changed, try reconfiguring genai silently
            # Don't show error here, let next API call handle it if invalid
            QTimer.singleShot(50, gemini_api.configure_genai) # Configure shortly after

            # Update model dropdown if necessary (though less critical here)
            new_selected_model = config_manager.get_setting('Models', 'selected_model')
            if self.model_combo.currentText() != new_selected_model:
                 # Just set the text, full populate not usually needed unless models changed
                 idx = self.model_combo.findText(new_selected_model)
                 if idx >= 0:
                     self.model_combo.setCurrentIndex(idx)
                 else:
                     # If the saved model isn't in the list, refresh the list
                     self.populate_models()

            self.set_status("Settings saved.", 3000)
        else:
             print("Settings dialog cancelled.")


    def export_history(self):
        """Exports chat history to a user-selected text file."""
        default_filename = f"gemini_chat_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Chat History",
            default_filename,
            "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            self.set_status(f"Exporting history to {os.path.basename(file_path)}...", 0)
            QApplication.processEvents()
            try:
                # Export all history (or a large number)
                history = db_manager.get_history(limit=99999)
                count = 0
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Gemini Chat History Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=====================================================\n\n")
                    for timestamp, role, content, model_used in history:
                        ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if isinstance(timestamp, datetime.datetime) else str(timestamp).split('.')[0]
                        model_info = f" (Model: {model_used})" if model_used else ""
                        f.write(f"[{ts_str}] {role.upper()}{model_info}:\n")
                        # Basic indentation for content
                        f.write(f"  {content}\n\n")
                        count += 1
                self.set_status(f"Exported {count} messages to {os.path.basename(file_path)}", 5000)
                utils.show_info_message(self, "Export Successful", f"Successfully exported {count} messages to:\n{file_path}")
            except Exception as e:
                error_msg = f"Failed to export history: {e}"
                print(f"Export Error: {error_msg}")
                self.set_status("Export failed.", 5000)
                utils.show_error_message(self, "Export Error", error_msg)


    def clear_history(self):
        """Clears the chat history from the database and display after confirmation."""
        reply = QMessageBox.question(self, "Confirm Clear History",
                                     "Are you sure you want to permanently delete all chat history?\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel) # Default to Cancel

        if reply == QMessageBox.StandardButton.Yes:
            self.set_status("Clearing history...", 0)
            QApplication.processEvents()
            if db_manager.clear_history():
                self.chat_display.clear() # Clear the display
                self.set_status("Chat history cleared.", 3000)
                print("Chat history cleared successfully.")
            else:
                 # db_manager already prints error, just notify user
                 self.set_status("Failed to clear history.", 5000)
                 utils.show_error_message(self, "Database Error", "Could not clear chat history from the database. Check logs.")


    def show_about(self):
        QMessageBox.about(self, "About Gemini Chat",
                          "<b>Gemini Chat Desktop</b>\n\n"
                          "Version: 0.1.0 (Example)\n\n"
                          "A simple desktop interface for interacting with Google's Gemini models via API.\n\n"
                          "Features:\n"
                          "- Chat history storage (SQLite)\n"
                          "- Model selection\n"
                          "- Fullscreen screenshot capture\n"
                          "- System tray integration\n"
                          "- Global hotkeys (configurable)\n\n"
                           "Built with Python and PyQt6.\n"
                          "(Replace with your actual version/details)"
                          )


    def set_status(self, message, timeout=0):
         """ Updates the status bar message """
         self.status_label.setText(message)
         if timeout > 0:
             # Use QTimer to clear the message after timeout, doesn't block status updates
             QTimer.singleShot(timeout, lambda: self.clear_status_if_matches(message))
         # print(f"Status: {message}") # Optional console log

    def clear_status_if_matches(self, original_message):
         """ Clears the status bar only if the message hasn't changed """
         if self.status_label.text() == original_message:
             self.status_label.setText("Ready")


    # --- Application Exit ---
    def quit_application(self):
         """ Ensures cleanup and proper application exit """
         print("Quit requested.")
         self.cleanup()
         QApplication.instance().quit()


    def cleanup(self):
         """ Perform cleanup before application exits """
         print("Performing cleanup...")
         # Stop hotkey listener
         if self.hotkey_listener and self.hotkey_listener.is_alive():
             print("Stopping hotkey listener...")
             self.hotkey_listener.stop()
         # Stop any running API worker
         if self.api_worker and self.api_worker.isRunning():
            print("Stopping active API worker...")
            self.api_worker.stop()
            self.api_worker.wait(500) # Wait briefly for it to finish
         # Hide tray icon (optional, OS usually handles this)
         if self.tray_icon:
             self.tray_icon.hide()
         print("Cleanup finished.")


# Needed if using invokeMethod by name string
# QMetaObject.invokeMethod(MainWindow, "toggle_visibility", Qt.ConnectionType.QueuedConnection)
# QMetaObject.invokeMethod(MainWindow, "take_screenshot_full", Qt.ConnectionType.QueuedConnection)

