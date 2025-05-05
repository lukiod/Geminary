# core/screenshot.py
import mss
import mss.tools
from PIL import Image
import io # To handle image data in memory
import platform

# Store the mss instance globally within the module to potentially reuse it?
# Or create it each time for simplicity and thread safety if called from multiple places.
# Creating each time is safer unless performance is critical.

def capture_fullscreen():
    """
    Captures the primary screen and returns the image data as PNG bytes.
    Returns None if capture fails.
    """
    try:
        with mss.mss() as sct:
            # Monitor 1 is typically the primary monitor in mss.
            # sct.monitors[0] is the virtual screen covering all monitors.
            primary_monitor = sct.monitors[1]
            sct_img = sct.grab(primary_monitor)

            # Convert to bytes (PNG format) directly using mss.tools
            img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            print(f"Fullscreen captured ({sct_img.width}x{sct_img.height})")
            return img_bytes
    except (IndexError, mss.ScreenShotError) as e:
        # Handle cases where monitor index is wrong or mss fails
        print(f"Error capturing primary monitor: {e}. Trying virtual screen.")
        try:
             # Fallback to grabbing the entire virtual screen
             with mss.mss() as sct:
                 virtual_monitor = sct.monitors[0]
                 sct_img = sct.grab(virtual_monitor)
                 img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
                 print(f"Virtual screen captured ({sct_img.width}x{sct_img.height})")
                 return img_bytes
        except Exception as fallback_e:
             print(f"Error capturing virtual screen: {fallback_e}")
             return None # Return None if both attempts fail
    except Exception as e:
        print(f"Unexpected error during fullscreen capture: {e}")
        return None


# --- Area Selection (Placeholder - Requires GUI Integration) ---
# This function would need to be triggered by the GUI, which would then
# likely create an overlay, handle mouse events, and call a capture function
# with the selected coordinates.

def capture_area(x, y, width, height):
    """Captures a specific area of the screen."""
    monitor = {"top": y, "left": x, "width": width, "height": height}
    try:
        with mss.mss() as sct:
            sct_img = sct.grab(monitor)
            img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            print(f"Area captured ({width}x{height}) at ({x},{y})")
            return img_bytes
    except Exception as e:
        print(f"Error capturing screen area: {e}")
        return None

# Note: Interactive area selection needs a GUI component (like a transparent overlay)
# to get the coordinates (x, y, width, height) before calling capture_area.

# Example usage (for testing this module directly)
if __name__ == "__main__":
    print("Testing fullscreen capture...")
    img_data = capture_fullscreen()
    if img_data:
        print(f"Capture successful, received {len(img_data)} bytes.")
        # Save to file for verification
        try:
            with open("fullscreen_test.png", "wb") as f:
                f.write(img_data)
            print("Saved test capture to fullscreen_test.png")
        except IOError as e:
            print(f"Error saving test file: {e}")
    else:
        print("Capture failed.")

    # print("\nTesting area capture (requires coordinates)...")
    # Example: Capture a 100x100 box at top-left corner
    # area_data = capture_area(0, 0, 100, 100)
    # if area_data:
    #     print(f"Area capture successful, received {len(area_data)} bytes.")
    # else:
    #     print("Area capture failed.")

