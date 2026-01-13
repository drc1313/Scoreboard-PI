import os
from utils import SampleBase, graphics, color
from state import state

current_dir = os.path.dirname(os.path.abspath(__file__))

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
