# core/hotkey_listener.py
import threading
import time
import platform
from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

class HotkeyListener(QObject, threading.Thread):
    toggle_visibility_triggered = pyqtSignal()
    screenshot_full_triggered = pyqtSignal()

    def __init__(self, hotkeys_config):
        super().__init__()
        threading.Thread.__init__(self)
        self.daemon = True
        self.hotkeys_config = hotkeys_config
        self._running = True
        self.listener = None
        self.current_keys = set()

        self.toggle_hotkey_comb = self._parse_hotkey(hotkeys_config.get('toggle_visibility'))
        self.screenshot_hotkey_comb = self._parse_hotkey(hotkeys_config.get('screenshot_full'))

        print(f"Hotkey Listener: Toggle Visibility = {self._set_to_string(self.toggle_hotkey_comb)}")
        print(f"Hotkey Listener: Screenshot Full = {self._set_to_string(self.screenshot_hotkey_comb)}")

        self._pressed_map = {} # To track which combination activated

    def _set_to_string(self, key_set):
         """ Helper to print the parsed key set legibly """
         if not key_set:
             return "None"
         return '+'.join(sorted([self._get_key_name(k) for k in key_set]))

    def _get_key_name(self, key):
        """ Get a printable name for a pynput key object """
        if isinstance(key, keyboard.KeyCode):
            return key.char
        # Use key.name for special keys (e.g., 'ctrl_l', 'alt', 'f1')
        return key.name if hasattr(key, 'name') else str(key)


    def _parse_hotkey(self, sequence_str):
        """Parses pynput compatible hotkey combination from string like 'Ctrl+Alt+G'"""
        if not sequence_str:
            return None
        # Normalize the string for parsing
        sequence_str = sequence_str.lower().replace(' ', '')
        parts = sequence_str.split('+')
        combination = set()

        # Map common names to pynput Key objects
        key_map = {
            'ctrl': keyboard.Key.ctrl,
            'alt': keyboard.Key.alt,
            'shift': keyboard.Key.shift,
            'cmd': keyboard.Key.cmd, # Use generic cmd
            'win': keyboard.Key.cmd, # Alias for Windows key
            'command': keyboard.Key.cmd, # Alias for Mac key
            'esc': keyboard.Key.esc,
            'space': keyboard.Key.space,
            'enter': keyboard.Key.enter,
            'tab': keyboard.Key.tab,
            'backspace': keyboard.Key.backspace,
            'delete': keyboard.Key.delete,
            'ins': keyboard.Key.insert,
            'home': keyboard.Key.home,
            'end': keyboard.Key.end,
            'pageup': keyboard.Key.page_up,
            'pagedown': keyboard.Key.page_down,
            'up': keyboard.Key.up,
            'down': keyboard.Key.down,
            'left': keyboard.Key.left,
            'right': keyboard.Key.right,
            # Add F keys F1-F12 (or more if needed)
            **{f'f{i}': getattr(keyboard.Key, f'f{i}') for i in range(1, 13)}
        }


        try:
            for part in parts:
                if part in key_map:
                    combination.add(key_map[part])
                elif len(part) == 1: # Regular character key
                     # Use from_char for consistency, handles case
                     combination.add(keyboard.KeyCode.from_char(part))
                else:
                     # Try to map other special keys by name if not in common map
                     key_attr = getattr(keyboard.Key, part, None)
                     if key_attr:
                         combination.add(key_attr)
                     else:
                        print(f"Warning: Unknown key name '{part}' in hotkey sequence '{sequence_str}'. Skipping.")
                        return None # Invalidate sequence if unknown key found
            return combination if combination else None
        except Exception as e:
            print(f"Error parsing hotkey sequence '{sequence_str}': {e}")
            return None

    def _check_hotkeys(self):
        """ Checks if any configured hotkey combination is currently pressed """
        # Check toggle visibility hotkey
        if self.toggle_hotkey_comb and self.toggle_hotkey_comb.issubset(self.current_keys):
             if 'toggle' not in self._pressed_map: # Fire only once per press
                 print("Toggle Visibility Hotkey Matched!")
                 self.toggle_visibility_triggered.emit()
                 self._pressed_map['toggle'] = True

        # Check screenshot hotkey
        if self.screenshot_hotkey_comb and self.screenshot_hotkey_comb.issubset(self.current_keys):
             if 'screenshot' not in self._pressed_map: # Fire only once per press
                 print("Screenshot Full Hotkey Matched!")
                 self.screenshot_full_triggered.emit()
                 self._pressed_map['screenshot'] = True


    def on_press(self, key):
        try:
             # Normalize modifiers (treat left/right versions the same)
             norm_key = key
             if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r): norm_key = keyboard.Key.ctrl
             elif key in (keyboard.Key.alt_l, keyboard.Key.alt_gr, keyboard.Key.alt_r): norm_key = keyboard.Key.alt
             elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r): norm_key = keyboard.Key.shift
             elif key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r): norm_key = keyboard.Key.cmd

             # Add the normalized key to the set of currently pressed keys
             # print(f"Press Raw: {key} | Norm: {norm_key} ({self._get_key_name(norm_key)})") # Debug
             self.current_keys.add(norm_key)
             self._check_hotkeys() # Check if a combination is met
        except Exception as e:
            print(f"Error in on_press: {e}") # Catch potential errors within the handler


    def on_release(self, key):
         try:
             # Normalize modifiers on release as well
             norm_key = key
             if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r): norm_key = keyboard.Key.ctrl
             elif key in (keyboard.Key.alt_l, keyboard.Key.alt_gr, keyboard.Key.alt_r): norm_key = keyboard.Key.alt
             elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r): norm_key = keyboard.Key.shift
             elif key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r): norm_key = keyboard.Key.cmd

             # print(f"Release Raw: {key} | Norm: {norm_key} ({self._get_key_name(norm_key)})") # Debug
             # Remove the key from the set
             if norm_key in self.current_keys:
                 self.current_keys.remove(norm_key)

             # Reset pressed state for combinations that included the released key
             if self.toggle_hotkey_comb and norm_key in self.toggle_hotkey_comb:
                 self._pressed_map.pop('toggle', None)
             if self.screenshot_hotkey_comb and norm_key in self.screenshot_hotkey_comb:
                 self._pressed_map.pop('screenshot', None)

         except Exception as e:
             # Catch errors like removing a key not present (shouldn't happen often)
             # or errors during normalization/checking
             print(f"Error in on_release: {e}")

    def run(self):
        print("Starting hotkey listener...")
        if not self.toggle_hotkey_comb and not self.screenshot_hotkey_comb:
             print("No valid hotkeys configured. Listener thread exiting.")
             self._running = False
             return

        # Determine platform specific listener args if needed
        backend_args = {}
        # Example: If issues arise on X11, you might need:
        # if platform.system() == "Linux" and os.environ.get("XDG_SESSION_TYPE") == "x11":
        #     backend_args['xorg_intercept_WM_KEYBINDINGS'] = True

        try:
            # Suppress event passing to other applications? Can be risky.
            # suppress=True
            self.listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release,
                suppress=False, # Set to True if you want to block the hotkey from other apps
                **backend_args
            )
            self.listener.start() # Start the listener
            print("Hotkey listener started successfully.")
            # Keep the thread alive while the listener is running
            while self._running and self.listener.is_alive():
                time.sleep(0.2) # Check periodically
            print("Hotkey listener run loop finished.")

        except ImportError as e:
             print(f"Import Error starting listener (likely missing backend dependency): {e}")
             if platform.system() == "Linux":
                 print("On Linux, you might need to install system packages like 'python3-tk', 'python3-dev', 'xorg-dev', or specific backend libraries.")
             self._running = False
        except Exception as e:
            # Catch other errors like no display server (e.g., SSH without X forwarding)
            print(f"CRITICAL: Failed to start pynput hotkey listener: {e}")
            print("Global hotkeys will NOT function.")
            self._running = False # Ensure thread terminates if listener fails hard

        finally:
             if self.listener and self.listener.is_alive():
                 self.listener.stop()
             print("Hotkey listener stopped.")


    def stop(self):
        print("Stopping hotkey listener request...")
        self._running = False
        if self.listener:
            # Stop the listener thread itself
            self.listener.stop()
        # Wait for the run() method loop to exit
        self.join(timeout=1.0)
        if self.is_alive():
            print("Warning: Hotkey listener thread did not stop gracefully.")

