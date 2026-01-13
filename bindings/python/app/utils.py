import os
import sys

# === Import Matrix Libraries ===
# Ensure we can find samplebase.py if running from 'app' or 'samples'
current_dir = os.path.dirname(os.path.abspath(__file__))
possible_base_dirs = [
    os.path.join(current_dir, '..', 'samples'),  # Standard binding location
    os.path.join(current_dir, 'samples'),        # Local samples folder
    current_dir                                  # Same folder
]

for d in possible_base_dirs:
    if os.path.exists(os.path.join(d, 'samplebase.py')):
        sys.path.append(d)
        break

try:
    from samplebase import SampleBase
    from rgbmatrix import graphics
except ImportError:
    print("❌ Error: Could not find 'samplebase.py' or 'rgbmatrix' library.")
    print("   Make sure you are running this from the rpi-rgb-led-matrix/bindings/python folder")
    print("   or have installed the library correctly.")
    sys.exit(1)

# === Color Helper ===
def color(value: str) -> graphics.Color:
    try:
        parts = [int(v) for v in value.split(",")]
        return graphics.Color(*parts)
    except:
        return graphics.Color(255, 255, 255)
