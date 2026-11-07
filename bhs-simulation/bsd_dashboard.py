import tkinter as tk
from tkinter import ttk
import csv
import os
import sys
from pathlib import Path

# 2D Canvas Coordinate Map for the 28 Airport Nodes
NODE_COORDINATES = {
    # Terminal A (Top Half)
    "IA1": (80, 160),  "IA2": (80, 280),
    "JA1": (240, 160), "JA2": (420, 160), "JA3": (600, 160), "JA4": (780, 160), "JA5": (510, 60),
    "GA1": (240, 40),  "GA2": (420, 40),  "GA3": (600, 40),  "GA4": (780, 40),

    # Main Center Spine Corridors
    "S1": (240, 400),  "S2": (420, 400),  "S3": (600, 400),
    "S4": (780, 400),  "S5": (960, 400),  "S6": (600, 520),

    # Terminal B (Bottom Half)
    "IB1": (80, 640),  "IB2": (80, 520),
    "JB1": (240, 640), "JB2": (420, 640), "JB3": (600, 640), "JB4": (780, 640), "JB5": (510, 700),
    "GB1": (960, 160), "GB2": (960, 280), "GB3": (960, 520), "GB4": (960, 640)
}

NODE_RADIUS = 18
SUB_FRAMES_PER_TICK = 10  # Animation subdivisions per tick
REFRESH_RATE_MS = 16      # Locked to ~60 FPS smoothness
BASE_DIR = Path(__file__).resolve().parent

class BSDDashboard:
    def __init__(self, root, telemetry_path="live_telemetry.csv"):
        self.root = root
        self.root.title("Brock Solutions - SmartSuite: Bag Status Display (BSD)")
        self.root.geometry("1200x860")
        self.root.configure(bg="#111115")

        self.telemetry_path = telemetry_path
        self.current_tick = 1
        self.sub_tick = 0  
        self.max_ticks = 1
        self.is_playing = False
        self.updating_via_slider = False # Prevents recursive slider loop updates
        self.history = {}

        self._load_telemetry_data()
        self._build_ui_layout()
        self._draw_static_network()
        self._update_display()

    def _load_telemetry_data(self):
        """Parses the telemetry CSV file and structures rows by simulation tick."""
        path = self.telemetry_path if os.path.exists(self.telemetry_path) else "live_telemetry.csv"
        if not os.path.exists(path):
            print(f"Error: Telemetry file '{path}' not found. Run evaluator first.")
            sys.exit(1)

        print("Parsing simulation telemetry dataset...")
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = int(row["tick"])
                edge_id = row["edge_id"]
                
                if t not in self.history:
                    self.history[t] = {}
                    
                self.history[t][edge_id] = {
                    "status": row["status"],
                    "fault_reason": row["fault_reason"],
                    "active_bags": int(row["active_bags"]),
                    "volume": int(row["cumulative_volume"])
                }
                self.max_ticks = max(self.max_ticks, t)

    def _build_ui_layout(self):
        """Constructs widgets, media player toolbars, and timeline navigation elements."""
        header = tk.Frame(self.root, bg="#0a0a0d", height=60)
        header.pack(fill=tk.X, side=tk.TOP)
        
        lbl_title = tk.Label(header, text="SmartSort™ Live Operational Playback Diagnostic Center", 
                             font=("Segoe UI", 12, "bold"), fg="#ffffff", bg="#0a0a0d")
        lbl_title.pack(side=tk.LEFT, padx=20, pady=15)

        controls = tk.Frame(self.root, bg="#0a0a0d", height=80)
        controls.pack(fill=tk.X, side=tk.BOTTOM)

        btn_frame = tk.Frame(controls, bg="#0a0a0d")
        btn_frame.pack(side=tk.LEFT, padx=10)

        self.btn_play = tk.Button(btn_frame, text="▶ Play System", width=12, bg="#28a745", fg="white", 
                                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT, command=self._toggle_playback)
        self.btn_play.pack(side=tk.LEFT, padx=5, pady=15)

        btn_prev = tk.Button(btn_frame, text="⏮ Back", bg="#22222b", fg="white", relief=tk.FLAT, command=self._prev_tick)
        btn_prev.pack(side=tk.LEFT, padx=3, pady=15)
        btn_next = tk.Button(btn_frame, text="Next ⏭", bg="#22222b", fg="white", relief=tk.FLAT, command=self._next_tick)
        btn_next.pack(side=tk.LEFT, padx=3, pady=15)

        # Interactive Snapshot Timeline Scrubber Slider
        self.slider = tk.Scale(controls, from_=1, to=self.max_ticks, orient=tk.HORIZONTAL,
                               bg="#0a0a0d", fg="#88888c", highlightthickness=0,
                               troughcolor="#1c1c24", activebackground="#00ffcc",
                               font=("Consolas", 9), label="Timeline Snapshot Scrubber (Jump to Time Ticks)",
                               command=self._on_slider_scrub)
        self.slider.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=20, pady=5)

        self.lbl_tick_counter = tk.Label(controls, text="Tick: 0000 / 3600", font=("Consolas", 11, "bold"), 
                                         fg="#00ffcc", bg="#0a0a0d")
        self.lbl_tick_counter.pack(side=tk.LEFT, padx=15)

        self.lbl_active_jams = tk.Label(controls, text="Active Blockages: 0", font=("Segoe UI", 11, "bold"), 
                                        fg="#ff3344", bg="#0a0a0d")
        self.lbl_active_jams.pack(side=tk.RIGHT, padx=20)

        self.canvas = tk.Canvas(self.root, bg="#141419", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

    def _draw_static_network(self):
        """Renders static geographical system markers onto the coordinate plane."""
        for node_id, (x, y) in NODE_COORDINATES.items():
            if node_id.startswith("I"):   color, label_color = "#0056b3", "#ffffff"
            elif node_id.startswith("G"): color, label_color = "#1e7e34", "#ffffff"
            elif node_id.startswith("S"): color, label_color = "#bd93f9", "#000000"
            else:                         color, label_color = "#44444f", "#ffffff"

            r = NODE_RADIUS
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="#ffffff", width=1.5)
            self.canvas.create_text(x, y, text=node_id, font=("Consolas", 9, "bold"), fill=label_color)

    def _update_display(self):
        """Clears old artifacts and redraws straight, trimmed lines and one-shot bag streams."""
        self.canvas.delete("dynamic_overlay")
        
        tick_data = self.history.get(self.current_tick, {})
        active_jams_count = 0
        progress = self.sub_tick / float(SUB_FRAMES_PER_TICK)

        for edge_id, edge in tick_data.items():
            base_clean_id = edge_id.replace("_FWD", "").replace("_REV", "")
            parts = base_clean_id.split("_")
            if len(parts) != 3: continue
            _, u, v = parts 
            
            if edge_id.endswith("_REV"):
                u, v = v, u

            if u not in NODE_COORDINATES or v not in NODE_COORDINATES: continue

            x1, y1 = NODE_COORDINATES[u]
            x2, y2 = NODE_COORDINATES[v]

            # Vector projection geometry
            dx = x2 - x1
            dy = y2 - y1
            dist = (dx**2 + dy**2)**0.5
            if dist == 0: continue

            ux, uy = dx / dist, dy / dist  # Unit direction
            nx, ny = -uy, ux              # Normal perpendicular

            # Parallel split lane offset shifting logic
            line_offset = 0
            if edge_id.endswith("_FWD"):   line_offset = 6
            elif edge_id.endswith("_REV"): line_offset = -6

            # --- PRECISE EDGE CORNER TRIMMING ---
            # Trimming by NODE_RADIUS + 14 ensures that arrowheads terminate perfectly 
            # on the outer rim perimeter of the circles without covering node text labels.
            x1_s = x1 + ux * (NODE_RADIUS + 2) + nx * line_offset
            y1_s = y1 + uy * (NODE_RADIUS + 2) + ny * line_offset
            x2_s = x2 - ux * (NODE_RADIUS + 14) + nx * line_offset
            y2_s = y2 - uy * (NODE_RADIUS + 14) + ny * line_offset

            bags_count = edge["active_bags"]
            is_jammed = edge["status"] == "JAMMED"
            
            if is_jammed:
                line_color = "#ff3344"  # Jammed: Crimson Red
                line_width = 3.5
                active_jams_count += 1
            elif bags_count > 0:
                line_color = "#ffb86c"  # Occupied: Safety Orange
                line_width = 2.5
            else:
                line_color = "#252530"  # Idle Track: Dark Grey
                line_width = 1.5

            # Render straight conveyor belt line segment
            self.canvas.create_line(x1_s, y1_s, x2_s, y2_s, fill=line_color, width=line_width, 
                                    arrow=tk.LAST, arrowshape=(10, 11, 4), tags="dynamic_overlay")

            # --- TRUE ONE-SHOT STREAM ANIMATION (NO LOOPING) ---
            if bags_count > 0:
                if is_jammed:
                    # If Jammed: Bags instantly halt. Space them statically down the belt
                    for i in range(bags_count):
                        pos = 0.25 + (i * 0.12)
                        if pos > 0.85: pos = 0.85
                        px = x1_s + pos * (x2_s - x1_s)
                        py = y1_s + pos * (y2_s - y1_s)
                        self.canvas.create_oval(px-4, py-4, px+4, py+4, fill="#ff3344", outline="white", width=0.5, tags="dynamic_overlay")
                else:
                    # If Running: March down the conveyor track exactly once per tick without wrapping
                    for i in range(bags_count):
                        pos = progress - (i * 0.14)  # Stagger entry spacing
                        if 0.0 <= pos <= 1.0:
                            px = x1_s + pos * (x2_s - x1_s)
                            py = y1_s + pos * (y2_s - y1_s)
                            self.canvas.create_oval(px-4, py-4, px+4, py+4, fill="#ffb86c", outline="white", width=0.5, tags="dynamic_overlay")

        # Sync readouts
        self.lbl_tick_counter.config(text=f"Tick: {self.current_tick:04d} / {self.max_ticks:04d}")
        self.lbl_active_jams.config(text=f"Active Blockages: {active_jams_count}")

        # Update timeline scrubber slider handle smoothly without firing bound callbacks
        self.updating_via_slider = True
        self.slider.set(self.current_tick)
        self.updating_via_slider = False

    def _on_slider_scrub(self, val):
        """Handles instant seek scrubbing along the time axis."""
        if self.updating_via_slider: return
        self.current_tick = int(val)
        self.sub_tick = 0
        self._update_display()

    def _toggle_playback(self):
        if self.is_playing:
            self.is_playing = False
            self.btn_play.config(text="▶ Play System", bg="#28a745")
        else:
            self.is_playing = True
            self.btn_play.config(text="⏸ Pause Loop", bg="#ffb86c")
            self._playback_loop()

    def _playback_loop(self):
        if not self.is_playing: return
        
        self.sub_tick += 1
        if self.sub_tick >= SUB_FRAMES_PER_TICK:
            self.sub_tick = 0
            if self.current_tick < self.max_ticks:
                self.current_tick += 1
            else:
                self._toggle_playback()
                return

        self._update_display()
        self.root.after(REFRESH_RATE_MS, self._playback_loop)

    def _next_tick(self):
        if self.current_tick < self.max_ticks:
            self.sub_tick = 0
            self.current_tick += 1
            self._update_display()

    def _prev_tick(self):
        if self.current_tick > 1:
            self.sub_tick = 0
            self.current_tick -= 1
            self._update_display()

if __name__ == "__main__":
    root = tk.Tk()
    csv_file = BASE_DIR / "live_telemetry.csv"
    app = BSDDashboard(root, telemetry_path=csv_file)
    root.mainloop()