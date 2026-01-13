#!/usr/bin/env python3
"""
Modularized Scoreboard Server.
Usage: sudo -E python3 main.py
"""

import threading
import uvicorn
from display import ScoreboardDisplay
from web import app

if __name__ == "__main__":
    print("🚀 Starting Scoreboard Server...")
    
    # 1. Initialize Display Wrapper
    display = ScoreboardDisplay()
    
    # 2. Launch Matrix Logic in Background Thread
    # We use display.process() because it parses sys.argv and initializes the matrix
    # BEFORE calling run(). This allows flags like --led-cols=64 to work.
    matrix_thread = threading.Thread(target=display.process, daemon=True)
    matrix_thread.start()
    
    # 3. Start Web Server (Main Thread)
    # The Matrix thread handles the drawing loop independently.
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
