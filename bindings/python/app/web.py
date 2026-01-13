import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from state import state

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

async def clock_tick_task():
    """Async task to decrement clock every second"""
    while True:
        await asyncio.sleep(1)
        if state["clock_running"] and state["clock_seconds"] > 0:
            state["clock_seconds"] -= 1
            # Optional: Broadcast every second (can be bandwidth heavy)
            # await manager.broadcast({"type": "state", "data": state})

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
