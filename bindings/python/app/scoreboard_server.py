#!/usr/bin/env python3
"""
Fixed scoreboard server: FastAPI WebSocket + rpi-rgb-led-matrix.
Usage: sudo -E python3 scoreboard.py --led-cols=64 --led-gpio-mapping=adafruit-hat
"""

import json
import asyncio
import threading
import time
import os
import sys
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

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


# === Scoreboard State ===
# Shared between FastAPI (Web) and Matrix (LED)
state = {
    "home_name": "HOME",
    "away_name": "AWAY", 
    "home_score": 0,
    "away_score": 0,
    "home_bg_color": "0,80,30",
    "away_bg_color": "80,0,30",
    "bg_color": "0,0,0",
    "clock_running": False,
    "clock_seconds": 720  # 12:00
}


# === LED Display Logic ===
class ScoreboardDisplay(SampleBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Setup Fonts
        self.score_font = graphics.Font()
        self.clock_font = graphics.Font()
        self._load_fonts()

        # 2. Layout Constants
        self.score_y = 29
        self.score_text_color = graphics.Color(255, 255, 255)
        
        # Positions
        self.x_home = 6   # Left score position
        self.x_away = 38  # Right score position
        
        # Canvas Buffer (Initialized in run)
        self.offscreen_canvas = None

    def _load_fonts(self):
        """Try to load fonts from multiple possible locations"""
        font_names = [("10x20.bdf", self.score_font), ("7x13B.bdf", self.clock_font)]
        
        # Search paths: relative to script, system fonts, or standard repo path
        search_paths = [
            os.path.join(current_dir, "../../../fonts"),
            os.path.join(current_dir, "fonts"),
            "/usr/share/fonts/X11/misc", 
            current_dir
        ]

        for font_file, font_obj in font_names:
            loaded = False
            for path in search_paths:
                full_path = os.path.join(path, font_file)
                if os.path.exists(full_path):
                    try:
                        font_obj.LoadFont(full_path)
                        loaded = True
                        break
                    except Exception:
                        continue
            if not loaded:
                print(f"⚠️ Warning: Could not load font {font_file}. Text may be missing.")

    def draw_frame(self, canvas):
        """Render the current state to the canvas"""
        if not canvas: return

        # Clear background
        bg = color(state["bg_color"])
        canvas.Fill(bg.red, bg.green, bg.blue)

        # -- Draw Team Backgrounds --
        # Home (Left half: 0-31)
        h_bg = color(state["home_bg_color"])
        for y in range(13, 32):
            for x in range(0, 32):
                canvas.SetPixel(x, y, h_bg.red, h_bg.green, h_bg.blue)

        # Away (Right half: 32-64)
        a_bg = color(state["away_bg_color"])
        for y in range(13, 32):
            for x in range(32, 64):
                canvas.SetPixel(x, y, a_bg.red, a_bg.green, a_bg.blue)

        # -- Draw Text --
        # Names (Small offset to center above score)
        graphics.DrawText(canvas, self.score_font, self.x_home - 4, self.score_y - 18, 
                          self.score_text_color, state["home_name"][:5])
        graphics.DrawText(canvas, self.score_font, self.x_away - 4, self.score_y - 18, 
                          self.score_text_color, state["away_name"][:5])

        # Scores
        graphics.DrawText(canvas, self.score_font, self.x_home, self.score_y, 
                          self.score_text_color, str(state["home_score"]))
        graphics.DrawText(canvas, self.score_font, self.x_away, self.score_y, 
                          self.score_text_color, str(state["away_score"]))

        # Divider Line
        graphics.DrawLine(canvas, 0, 12, 63, 12, graphics.Color(100, 100, 100))

        # -- Draw Clock --
        # Gray background for clock
        for y in range(0, 12):
            for x in range(0, 64):
                canvas.SetPixel(x, y, 20, 20, 20)

        mins, secs = divmod(state["clock_seconds"], 60)
        time_str = f"{mins:02d}:{secs:02d}"
        
        # Center clock roughly
        graphics.DrawText(canvas, self.clock_font, 15, 10, 
                          self.score_text_color, time_str)

    def run(self):
        """The main rendering loop"""
        print("📺 Display Loop Started")
        
        # Create canvas ONCE
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()

        while True:
            # 1. Draw to offscreen buffer
            self.draw_frame(self.offscreen_canvas)
            
            # 2. Swap buffers and get the fresh one back
            # This handles the timing/VSync automatically
            self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)


# === WebSocket Manager ===
class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except:
                self.disconnect(connection)

manager = ConnectionManager()


# === FastAPI Application ===
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Start the clock background task
    asyncio.create_task(clock_tick_task())

@app.get("/", response_class=HTMLResponse)
async def get():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Scoreboard Controller</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; background: #111; color: #eee; text-align: center; padding: 20px; }
        button { font-size: 1.2rem; padding: 10px 20px; margin: 5px; cursor: pointer; border: none; border-radius: 5px; }
        .home { background: #00501e; color: white; }
        .away { background: #50001e; color: white; }
        .neutral { background: #444; color: white; }
        input { font-size: 1rem; padding: 5px; margin: 5px; width: 100px; text-align: center; }
    </style>
</head>
<body>
    <h2>🎮 LED Scoreboard</h2>
    
    <div>
        <button class="home" onclick="updateScore('home', 1)">Home +1</button>
        <button class="home" onclick="updateScore('home', -1)">Home -1</button>
        <br>
        <button class="away" onclick="updateScore('away', 1)">Away +1</button>
        <button class="away" onclick="updateScore('away', -1)">Away -1</button>
    </div>
    <br>
    <div>
        <input id="hName" placeholder="Home Name" onchange="updateNames()">
        <input id="aName" placeholder="Away Name" onchange="updateNames()">
    </div>
    <br>
    <div>
        <button class="neutral" onclick="send({type:'clock', action:'start'})">▶ Start</button>
        <button class="neutral" onclick="send({type:'clock', action:'stop'})">⏸ Stop</button>
        <button class="neutral" onclick="send({type:'clock', action:'set', seconds:720})">↺ Reset (12:00)</button>
    </div>

    <script>
        const ws = new WebSocket(`ws://${location.host}/ws`);
        
        function send(msg) { ws.send(JSON.stringify(msg)); }
        
        function updateScore(team, delta) {
            send({type: 'score_delta', team: team, delta: delta});
        }
        
        function updateNames() {
            send({
                type: 'set_names', 
                home: document.getElementById('hName').value, 
                away: document.getElementById('aName').value
            });
        }
    </script>
</body>
</html>
    """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Send current state immediately
    await websocket.send_text(json.dumps({"type": "state", "data": state}))
    
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            await handle_message(msg)
    except (WebSocketDisconnect, json.JSONDecodeError):
        manager.disconnect(websocket)

async def handle_message(msg: dict):
    mtype = msg.get("type")
    
    if mtype == "score_delta":
        team = msg.get("team")
        delta = int(msg.get("delta", 0))
        key = f"{team}_score"
        if key in state:
            state[key] = max(0, state[key] + delta)
            
    elif mtype == "set_names":
        if msg.get("home"): state["home_name"] = msg["home"][:8]
        if msg.get("away"): state["away_name"] = msg["away"][:8]

    # --- ADD THIS NEW HANDLER ---
    elif mtype == "set_color":
        team = msg.get("team")       # "home" or "away"
        color_val = msg.get("color") # "255,100,0"
        
        # Security check: ensure team is valid and color is a string
        if team in ["home", "away"] and isinstance(color_val, str):
            state[f"{team}_bg_color"] = color_val
    # ----------------------------

    elif mtype == "clock":
        action = msg.get("action")
        if action == "start": state["clock_running"] = True
        elif action == "stop": state["clock_running"] = False
        elif action == "set": state["clock_seconds"] = int(msg.get("seconds", 0))

    # Broadcast state to all clients (optional for color, but good for consistency)
    await manager.broadcast({"type": "state", "data": state})

async def clock_tick_task():
    """Async task to decrement clock every second"""
    while True:
        await asyncio.sleep(1)
        if state["clock_running"] and state["clock_seconds"] > 0:
            state["clock_seconds"] -= 1
            # Optional: Broadcast every second (can be bandwidth heavy)
            # await manager.broadcast({"type": "state", "data": state})


# === MAIN EXECUTION ===
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
