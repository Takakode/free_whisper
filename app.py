"""
Free Whisper — macOS menu bar speech-to-text
Press Cmd+Shift+Space (or click the menu bar icon) to start/stop recording.
Transcribed text is pasted into whatever field is currently focused.
"""
import logging
import subprocess
import threading
import time

import rumps
from AppKit import NSPasteboard, NSStringPboardType
from pynput import keyboard

from recorder import Recorder
from transcriber import Transcriber

logging.basicConfig(level=logging.INFO, format="[FreeWhisper] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HOTKEY = "<cmd>+<shift>+<space>"


class FreeWhisperApp(rumps.App):
    IDLE = "🎤"
    RECORDING = "🔴"
    PROCESSING = "⏳"

    def __init__(self):
        super().__init__(self.IDLE, quit_button="Quit")
        self.menu = ["Toggle Recording"]
        self.recorder = Recorder()
        self.transcriber = Transcriber(language="en")
        self.is_recording = False
        self._lock = threading.Lock()
        self._start_hotkey_listener()

    # ── Hotkey ──────────────────────────────────────────────────────────────────

    def _start_hotkey_listener(self):
        self._hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(HOTKEY),
            lambda: threading.Thread(target=self.toggle, daemon=True).start(),
        )

        def safe(fn, key):
            try:
                fn(key)
            except (ValueError, AttributeError):
                pass  # pynput raises these on unknown key events — safe to ignore

        def on_press(k):
            safe(self._hotkey.press, self._listener.canonical(k))

        def on_release(k):
            safe(self._hotkey.release, self._listener.canonical(k))

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    # ── Menu item ────────────────────────────────────────────────────────────────

    @rumps.clicked("Toggle Recording")
    def menu_toggle(self, _):
        threading.Thread(target=self.toggle, daemon=True).start()

    # ── Recording logic ──────────────────────────────────────────────────────────

    def toggle(self):
        with self._lock:
            if self.is_recording:
                self._stop()
            else:
                self._start()

    def _start(self):
        self.is_recording = True
        self.title = self.RECORDING
        self.recorder.start()

    def _stop(self):
        self.title = self.PROCESSING
        audio = self.recorder.stop()
        self.is_recording = False

        text = self.transcriber.transcribe(audio)
        if text:
            self._paste(text)
            rumps.notification("Free Whisper", "", text, sound=False)

        self.title = self.IDLE

    # ── Text insertion ───────────────────────────────────────────────────────────

    def _paste(self, text: str):
        """Write text to the NSPasteboard directly (no subprocess), paste, then restore."""
        pb = NSPasteboard.generalPasteboard()

        # Save previous clipboard contents
        prev = pb.stringForType_(NSStringPboardType)

        try:
            # Write transcribed text via native AppKit API — no shell involved
            pb.declareTypes_owner_([NSStringPboardType], None)
            pb.setString_forType_(text, NSStringPboardType)

            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to keystroke "v" using command down',
                ],
                check=True,
                capture_output=True,
                timeout=3,
            )
            if result.returncode != 0:
                log.error("osascript paste failed: %s", result.stderr.decode())
        except subprocess.CalledProcessError as e:
            log.error("Paste failed: %s", e.stderr.decode() if e.stderr else e)
        except subprocess.TimeoutExpired:
            log.error("Paste timed out — Accessibility permission may be missing")
        finally:
            # Wait for the target app to actually read the clipboard before restoring
            time.sleep(0.3)
            pb.declareTypes_owner_([NSStringPboardType], None)
            pb.setString_forType_(prev or "", NSStringPboardType)


if __name__ == "__main__":
    FreeWhisperApp().run()
