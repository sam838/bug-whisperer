import os

# Tests never start the sample app or a real Chrome camera.
os.environ.setdefault("WHISPERER_NO_BOOT", "1")
os.environ.setdefault("WHISPERER_NO_CAMERA", "1")
