"""Keyboard listener for real-time panel toggle."""

import sys
import threading
import select
from typing import Optional, Callable


class KeyboardListener:
    """Non-blocking keyboard input listener."""
    
    def __init__(self, on_key_press: Optional[Callable[[str], None]] = None):
        """Initialize keyboard listener.
        
        Args:
            on_key_press: Callback function called when a key is pressed
        """
        self.on_key_press = on_key_press
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._original_terminal_settings = None
    
    def start(self):
        """Start listening for keyboard input."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop listening for keyboard input."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.1)
    
    def _listen(self):
        """Listen for keyboard input in background thread."""
        # Use select for non-blocking input check
        # Note: This works best when stdin is available and not redirected
        while self.running:
            try:
                # Check if stdin has data (non-blocking, 0.1s timeout)
                # This won't interfere with Rich Live display
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                
                if ready:
                    try:
                        # Read single character (non-blocking)
                        char = sys.stdin.read(1)
                        if char and self.on_key_press:
                            # Filter out control characters and newlines
                            if char.isprintable() or char in ['\n', '\r']:
                                self.on_key_press(char)
                    except (EOFError, OSError, UnicodeDecodeError):
                        # End of input or error, stop listening
                        break
            except (ValueError, OSError):
                # stdin not available or not a terminal, stop listening
                break
            except KeyboardInterrupt:
                # User interrupted, stop listening
                break
