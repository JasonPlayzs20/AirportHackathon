import tkinter as tk
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
        self.root.geometry("1440x900")
        self.root.minsize(1000, 700)
        self.root.configure(bg="#111115")

        self.telemetry_path = telemetry_path
        self.current_tick = 1
        self.sub_tick = 0  
        self.max_ticks = 1
        self.is_playing = False
        self.updating_via_slider = False # Prevents recursive slider loop updates
        self.history = {}
        self._last_rendered_issues = None
        self._last_rendered_transit = None
        self._canvas_render_size = None

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
        """Constructs the network view, issue queue, and playback controls."""
        header = tk.Frame(self.root, bg="#0a0a0d", height=68)
        header.pack(fill=tk.X, side=tk.TOP)

        title_block = tk.Frame(header, bg="#0a0a0d")
        title_block.pack(side=tk.LEFT, padx=22, pady=10)
        tk.Label(title_block, text="SmartSort™  /  BAG STATUS DISPLAY",
                 font=("Segoe UI", 15, "bold"), fg="#ffffff", bg="#0a0a0d").pack(anchor=tk.W)
        tk.Label(title_block, text="LIVE OPERATIONAL PLAYBACK  ·  NETWORK HEALTH",
                 font=("Segoe UI", 8, "bold"), fg="#8b909e", bg="#0a0a0d").pack(anchor=tk.W, pady=(2, 0))

        controls = tk.Frame(self.root, bg="#0a0a0d", height=86)
        controls.pack(fill=tk.X, side=tk.BOTTOM)

        btn_frame = tk.Frame(controls, bg="#0a0a0d")
        btn_frame.pack(side=tk.LEFT, padx=12)

        self.btn_play = tk.Button(btn_frame, text="▶ Play System", width=13, bg="#218c5a", fg="white",
                                  activebackground="#2ba66d", activeforeground="white",
                                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                                  command=self._toggle_playback)
        self.btn_play.pack(side=tk.LEFT, padx=4, pady=15)

        btn_prev = tk.Button(btn_frame, text="⏮ Back", bg="#222733", fg="white",
                             activebackground="#343b4a", activeforeground="white", relief=tk.FLAT,
                             command=self._prev_tick)
        btn_prev.pack(side=tk.LEFT, padx=3, pady=15)
        btn_next = tk.Button(btn_frame, text="Next ⏭", bg="#222733", fg="white",
                             activebackground="#343b4a", activeforeground="white", relief=tk.FLAT,
                             command=self._next_tick)
        btn_next.pack(side=tk.LEFT, padx=3, pady=15)

        self.slider = tk.Scale(controls, from_=1, to=self.max_ticks, orient=tk.HORIZONTAL,
                               bg="#0a0a0d", fg="#a9afbd", highlightthickness=0,
                               troughcolor="#292e3a", activebackground="#55d6be",
                               font=("Consolas", 9), label="TIMELINE  ·  DRAG TO SEEK",
                               command=self._on_slider_scrub)
        self.slider.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=16, pady=4)

        self.lbl_tick_counter = tk.Label(controls, text="Tick: 0000 / 0000",
                                        font=("Consolas", 11, "bold"), fg="#55d6be", bg="#0a0a0d")
        self.lbl_tick_counter.pack(side=tk.LEFT, padx=12)

        self.lbl_active_jams = tk.Label(controls, text="Active Blockages: 0",
                                        font=("Segoe UI", 10, "bold"), fg="#ff6577", bg="#0a0a0d")
        self.lbl_active_jams.pack(side=tk.RIGHT, padx=(8, 18))

        self.lbl_active_bags = tk.Label(controls, text="Active Bags: 0",
                                        font=("Segoe UI", 10, "bold"), fg="#ffbf69", bg="#0a0a0d")
        self.lbl_active_bags.pack(side=tk.RIGHT, padx=(12, 8))

        content = tk.Frame(self.root, bg="#111115")
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        map_panel = tk.Frame(content, bg="#171a22")
        map_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        map_caption = tk.Frame(map_panel, bg="#171a22")
        map_caption.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(map_caption, text="CONVEYOR NETWORK", font=("Segoe UI", 10, "bold"),
                 fg="#e5e8ef", bg="#171a22").pack(side=tk.LEFT)
        tk.Label(map_caption, text="DIRECTED TRACK STATUS", font=("Segoe UI", 8),
                 fg="#818897", bg="#171a22").pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(map_panel, bg="#14171e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 8))
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        legend = tk.Frame(map_panel, bg="#171a22")
        legend.pack(fill=tk.X, padx=14, pady=(0, 12))
        self._add_legend_item(legend, "#ff6577", "JAMMED / ISSUE", bold=True)
        self._add_legend_item(legend, "#ffbf69", "BAGS IN TRANSIT")
        self._add_legend_item(legend, "#3a3f4b", "IDLE TRACK")

        issue_panel = tk.Frame(content, bg="#191c25", width=320)
        issue_panel.pack(side=tk.RIGHT, fill=tk.Y)
        issue_panel.pack_propagate(False)

        # --- Top Section: Active Issues (Jammed Tracks) ---
        issues_section = tk.Frame(issue_panel, bg="#191c25")
        issues_section.pack(fill=tk.BOTH, expand=True)

        issue_header = tk.Frame(issues_section, bg="#191c25")
        issue_header.pack(fill=tk.X, padx=16, pady=(16, 6))
        tk.Label(issue_header, text="ACTIVE ISSUES", font=("Segoe UI", 11, "bold"),
                 fg="#f0f2f6", bg="#191c25").pack(side=tk.LEFT)
        self.lbl_issue_count = tk.Label(issue_header, text="0", font=("Consolas", 10, "bold"),
                                        fg="#ff6577", bg="#351e28", padx=8, pady=3)
        self.lbl_issue_count.pack(side=tk.RIGHT)
        tk.Label(issues_section, text="CURRENT SNAPSHOT  ·  JAMMED TRACKS", font=("Segoe UI", 8, "bold"),
                 fg="#818897", bg="#191c25", anchor=tk.W).pack(fill=tk.X, padx=16, pady=(0, 6))

        issue_body = tk.Frame(issues_section, bg="#191c25")
        issue_body.pack(fill=tk.BOTH, expand=True, padx=(12, 8), pady=(0, 8))
        issue_scrollbar = tk.Scrollbar(issue_body, orient=tk.VERTICAL)
        issue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.issue_text = tk.Text(issue_body, wrap=tk.WORD, state=tk.DISABLED,
                                  bg="#191c25", fg="#e5e8ef", insertbackground="#e5e8ef",
                                  relief=tk.FLAT, borderwidth=0, padx=5, pady=4,
                                  font=("Segoe UI", 9), height=8, yscrollcommand=issue_scrollbar.set)
        self.issue_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        issue_scrollbar.config(command=self.issue_text.yview)
        self.issue_text.tag_configure("issue_heading", foreground="#ff8190", font=("Segoe UI", 9, "bold"))
        self.issue_text.tag_configure("issue_reason", foreground="#c6cbd6")
        self.issue_text.tag_configure("issue_bags", foreground="#9da5b5", font=("Consolas", 8))
        self.issue_text.tag_configure("empty_state", foreground="#73c7a2", font=("Segoe UI", 9))

        # Divider between Active Issues and Bags in Transit
        tk.Frame(issue_panel, bg="#262b38", height=1).pack(fill=tk.X, padx=14, pady=4)

        # --- Bottom Section: Active Bags in Transit ---
        transit_section = tk.Frame(issue_panel, bg="#191c25")
        transit_section.pack(fill=tk.BOTH, expand=True)

        transit_header = tk.Frame(transit_section, bg="#191c25")
        transit_header.pack(fill=tk.X, padx=16, pady=(10, 6))
        tk.Label(transit_header, text="BAGS IN TRANSIT", font=("Segoe UI", 11, "bold"),
                 fg="#f0f2f6", bg="#191c25").pack(side=tk.LEFT)
        self.lbl_transit_count = tk.Label(transit_header, text="0", font=("Consolas", 10, "bold"),
                                          fg="#ffbf69", bg="#332a1e", padx=8, pady=3)
        self.lbl_transit_count.pack(side=tk.RIGHT)
        tk.Label(transit_section, text="CURRENT SNAPSHOT  ·  OCCUPIED TRACKS", font=("Segoe UI", 8, "bold"),
                 fg="#818897", bg="#191c25", anchor=tk.W).pack(fill=tk.X, padx=16, pady=(0, 6))

        transit_body = tk.Frame(transit_section, bg="#191c25")
        transit_body.pack(fill=tk.BOTH, expand=True, padx=(12, 8), pady=(0, 12))
        transit_scrollbar = tk.Scrollbar(transit_body, orient=tk.VERTICAL)
        transit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.transit_text = tk.Text(transit_body, wrap=tk.WORD, state=tk.DISABLED,
                                    bg="#191c25", fg="#e5e8ef", insertbackground="#e5e8ef",
                                    relief=tk.FLAT, borderwidth=0, padx=5, pady=4,
                                    font=("Segoe UI", 9), height=8, yscrollcommand=transit_scrollbar.set)
        self.transit_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        transit_scrollbar.config(command=self.transit_text.yview)
        self.transit_text.tag_configure("transit_heading", foreground="#ffbf69", font=("Segoe UI", 9, "bold"))
        self.transit_text.tag_configure("transit_jammed_heading", foreground="#ff8190", font=("Segoe UI", 9, "bold"))
        self.transit_text.tag_configure("transit_bags", foreground="#c6cbd6", font=("Consolas", 8))
        self.transit_text.tag_configure("empty_state", foreground="#818897", font=("Segoe UI", 9))

    @staticmethod
    def _add_legend_item(parent, color, label, bold=False):
        item = tk.Frame(parent, bg="#171a22")
        item.pack(side=tk.LEFT, padx=(2, 18))
        tk.Canvas(item, width=12, height=12, bg="#171a22", highlightthickness=0).pack(side=tk.LEFT, padx=(0, 6))
        swatch = item.winfo_children()[0]
        swatch.create_oval(2, 2, 10, 10, fill=color, outline=color)
        tk.Label(item, text=label, font=("Segoe UI", 8, "bold" if bold else "normal"),
                 fg="#c4c9d3", bg="#171a22").pack(side=tk.LEFT)

    def _canvas_transform(self):
        """Returns a centered, uniform transform from network to canvas coordinates."""
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        scale = min(max(width - 32, 1) / 1040.0, max(height - 32, 1) / 740.0)
        return scale, (width - 1040 * scale) / 2, (height - 740 * scale) / 2

    def _map_point(self, x, y):
        scale, offset_x, offset_y = self._canvas_transform()
        return offset_x + x * scale, offset_y + y * scale

    def _on_canvas_resize(self, event):
        size = (event.width, event.height)
        if size == self._canvas_render_size or event.width <= 1 or event.height <= 1:
            return
        self._canvas_render_size = size
        self._draw_static_network()
        self._update_display()

    def _draw_static_network(self):
        """Renders static geographical system markers onto the coordinate plane."""
        self.canvas.delete("static_network")
        scale, _, _ = self._canvas_transform()
        for node_id, (x, y) in NODE_COORDINATES.items():
            if node_id.startswith("I"):   color, label_color = "#0056b3", "#ffffff"
            elif node_id.startswith("G"): color, label_color = "#1e7e34", "#ffffff"
            elif node_id.startswith("S"): color, label_color = "#bd93f9", "#000000"
            else:                         color, label_color = "#44444f", "#ffffff"

            cx, cy = self._map_point(x, y)
            r = NODE_RADIUS * scale
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline="#d9deea",
                                    width=max(1, scale * 1.5), tags="static_network")
            self.canvas.create_text(cx, cy, text=node_id,
                                    font=("Consolas", max(7, round(9 * scale)), "bold"),
                                    fill=label_color, tags="static_network")

    def _update_display(self):
        """Clears old artifacts and redraws straight, trimmed lines and one-shot bag streams."""
        self.canvas.delete("dynamic_overlay")

        tick_data = self.history.get(self.current_tick, {})
        issue_details = []
        transit_details = []
        total_active_bags = 0
        progress = self.sub_tick / float(SUB_FRAMES_PER_TICK)
        scale, _, _ = self._canvas_transform()

        for edge_id, edge in tick_data.items():
            bags_count = edge["active_bags"]
            total_active_bags += bags_count
            is_jammed = edge["status"] == "JAMMED"
            if is_jammed:
                reason = str(edge.get("fault_reason") or "Unspecified fault").strip()
                issue_details.append((str(edge_id), reason, bags_count))
            if bags_count > 0:
                transit_details.append((str(edge_id), bags_count, is_jammed))

            base_clean_id = edge_id.replace("_FWD", "").replace("_REV", "")
            parts = base_clean_id.split("_")
            if len(parts) != 3: continue
            _, u, v = parts 
            
            if edge_id.endswith("_REV"):
                u, v = v, u

            if u not in NODE_COORDINATES or v not in NODE_COORDINATES: continue

            x1, y1 = NODE_COORDINATES[u]
            x2, y2 = NODE_COORDINATES[v]
            x1, y1 = self._map_point(x1, y1)
            x2, y2 = self._map_point(x2, y2)

            # Vector projection geometry
            dx = x2 - x1
            dy = y2 - y1
            dist = (dx**2 + dy**2)**0.5
            if dist == 0: continue

            ux, uy = dx / dist, dy / dist  # Unit direction
            nx, ny = -uy, ux              # Normal perpendicular

            # Parallel split lane offset shifting logic
            line_offset = 0
            if edge_id.endswith("_FWD"):   line_offset = 6 * scale
            elif edge_id.endswith("_REV"): line_offset = -6 * scale

            # --- PRECISE EDGE CORNER TRIMMING ---
            # Trimming by NODE_RADIUS + 14 ensures that arrowheads terminate perfectly 
            # on the outer rim perimeter of the circles without covering node text labels.
            x1_s = x1 + ux * (NODE_RADIUS + 2) * scale + nx * line_offset
            y1_s = y1 + uy * (NODE_RADIUS + 2) * scale + ny * line_offset
            x2_s = x2 - ux * (NODE_RADIUS + 14) * scale + nx * line_offset
            y2_s = y2 - uy * (NODE_RADIUS + 14) * scale + ny * line_offset

            if is_jammed:
                line_color = "#ff6577"  # Jammed: Crimson Red
                line_width = 3.5 * scale
            elif bags_count > 0:
                line_color = "#ffbf69"  # Occupied: Safety Orange
                line_width = 2.5 * scale
            else:
                line_color = "#3a3f4b"  # Idle Track: Dark Grey
                line_width = 1.5 * scale

            # Render straight conveyor belt line segment
            self.canvas.create_line(x1_s, y1_s, x2_s, y2_s, fill=line_color, width=line_width, 
                                    arrow=tk.LAST,
                                    arrowshape=(max(7, round(10 * scale)), max(8, round(11 * scale)),
                                                max(3, round(4 * scale))), tags="dynamic_overlay")

            if is_jammed:
                marker_x, marker_y = (x1_s + x2_s) / 2, (y1_s + y2_s) / 2
                marker_radius = max(7, 9 * scale)
                self.canvas.create_oval(marker_x-marker_radius, marker_y-marker_radius,
                                        marker_x+marker_radius, marker_y+marker_radius,
                                        fill="#9f2637", outline="#fff0f2", width=max(1, scale),
                                        tags="dynamic_overlay")
                self.canvas.create_text(marker_x, marker_y, text="!",
                                        font=("Segoe UI", max(8, round(11 * scale)), "bold"),
                                        fill="white", tags="dynamic_overlay")

            # --- TRUE ONE-SHOT STREAM ANIMATION (NO LOOPING) ---
            if bags_count > 0:
                if is_jammed:
                    # If Jammed: Bags instantly halt. Space them statically down the belt
                    for i in range(bags_count):
                        pos = 0.25 + (i * 0.12)
                        if pos > 0.85: pos = 0.85
                        px = x1_s + pos * (x2_s - x1_s)
                        py = y1_s + pos * (y2_s - y1_s)
                        bag_radius = max(2.5, 4 * scale)
                        self.canvas.create_oval(px-bag_radius, py-bag_radius, px+bag_radius, py+bag_radius,
                                                fill="#ff6577", outline="white", width=0.5,
                                                tags="dynamic_overlay")
                else:
                    # If Running: March down the conveyor track exactly once per tick without wrapping
                    for i in range(bags_count):
                        pos = progress - (i * 0.14)  # Stagger entry spacing
                        if 0.0 <= pos <= 1.0:
                            px = x1_s + pos * (x2_s - x1_s)
                            py = y1_s + pos * (y2_s - y1_s)
                            bag_radius = max(2.5, 4 * scale)
                            self.canvas.create_oval(px-bag_radius, py-bag_radius, px+bag_radius, py+bag_radius,
                                                    fill="#ffbf69", outline="white", width=0.5,
                                                    tags="dynamic_overlay")

        issue_details.sort(key=lambda issue: issue[0])
        transit_details.sort(key=lambda item: (-item[1], item[0]))
        self._render_issue_list(issue_details)
        self._render_transit_list(transit_details, total_active_bags)

        # Sync readouts
        self.lbl_tick_counter.config(text=f"Tick: {self.current_tick:04d} / {self.max_ticks:04d}")
        self.lbl_active_bags.config(text=f"Active Bags: {total_active_bags}")
        self.lbl_active_jams.config(text=f"Active Blockages: {len(issue_details)}")

        # Update timeline scrubber slider handle smoothly without firing bound callbacks
        self.updating_via_slider = True
        self.slider.set(self.current_tick)
        self.updating_via_slider = False

    def _render_issue_list(self, issue_details):
        """Refreshes the issue queue only when the current snapshot has changed."""
        issue_details = tuple(issue_details)
        if issue_details == self._last_rendered_issues:
            return

        self._last_rendered_issues = issue_details
        self.lbl_issue_count.config(text=str(len(issue_details)))
        self.issue_text.configure(state=tk.NORMAL)
        self.issue_text.delete("1.0", tk.END)

        if not issue_details:
            self.issue_text.insert(tk.END, "No active issues in this snapshot.\n\nAll displayed tracks are clear.",
                                   "empty_state")
        else:
            for edge_id, reason, bags_count in issue_details:
                if edge_id.endswith("_FWD"):
                    direction = "FORWARD"
                elif edge_id.endswith("_REV"):
                    direction = "REVERSE"
                else:
                    direction = "TRACK"
                self.issue_text.insert(tk.END, f"!  {edge_id}  ·  {direction}\n", "issue_heading")
                self.issue_text.insert(tk.END, f"   {reason}\n", "issue_reason")
                self.issue_text.insert(tk.END, f"   {bags_count} bag(s) stuck on this track\n\n", "issue_bags")

        self.issue_text.configure(state=tk.DISABLED)

    def _render_transit_list(self, transit_details, total_active_bags):
        """Refreshes the active bags in transit queue when the current snapshot changes."""
        snapshot_key = (tuple(transit_details), total_active_bags)
        if snapshot_key == self._last_rendered_transit:
            return

        self._last_rendered_transit = snapshot_key
        self.lbl_transit_count.config(text=str(total_active_bags))
        self.transit_text.configure(state=tk.NORMAL)
        self.transit_text.delete("1.0", tk.END)

        if not transit_details:
            self.transit_text.insert(tk.END, "No bags currently in transit on any track.",
                                     "empty_state")
        else:
            for edge_id, bags_count, is_jammed in transit_details:
                if edge_id.endswith("_FWD"):
                    direction = "FORWARD"
                elif edge_id.endswith("_REV"):
                    direction = "REVERSE"
                else:
                    direction = "TRACK"
                heading_tag = "transit_jammed_heading" if is_jammed else "transit_heading"
                prefix = "!" if is_jammed else "•"
                state_label = "stuck on jammed track" if is_jammed else "in transit"
                self.transit_text.insert(tk.END, f"{prefix}  {edge_id}  ·  {direction}\n", heading_tag)
                self.transit_text.insert(tk.END, f"   {bags_count} bag(s) {state_label}\n\n", "transit_bags")

        self.transit_text.configure(state=tk.DISABLED)

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
