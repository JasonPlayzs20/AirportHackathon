import tkinter as tk
import csv
import os
import sys
from pathlib import Path
from dashboard_analysis import (
    RISK_WARNING_THRESHOLD,
    calculate_risks,
    find_simple_paths,
    load_topology,
)

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
        self._last_rendered_risks = None
        self._last_rendered_paths = None
        self._last_rendered_transit = None
        self._canvas_render_size = None
        self.network_nodes, self.network_edges = load_topology()
        self.selected_start = None
        self.selected_destination = None
        self.node_visibility = {node_id: tk.BooleanVar(master=root, value=True)
                                for node_id in self.network_nodes}
        self.belts_visible = tk.BooleanVar(master=root, value=True)
        self._risk_cache = {}
        self._path_cache = {}

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
                 font=("TkDefaultFont", 16, "bold"), fg="#ffffff", bg="#0a0a0d").pack(anchor=tk.W)
        tk.Label(title_block, text="LIVE OPERATIONAL PLAYBACK  ·  NETWORK HEALTH",
                 font=("TkDefaultFont", 9, "bold"), fg="#8b909e", bg="#0a0a0d").pack(anchor=tk.W, pady=(2, 0))

        controls = tk.Frame(self.root, bg="#0a0a0d", height=86)
        controls.pack(fill=tk.X, side=tk.BOTTOM)

        btn_frame = tk.Frame(controls, bg="#0a0a0d")
        btn_frame.pack(side=tk.LEFT, padx=12)

        self.btn_play = tk.Button(btn_frame, text="▶ Play System", width=13, bg="#218c5a", fg="white",
                                  activebackground="#2ba66d", activeforeground="white",
                                  font=("TkDefaultFont", 10, "bold"), relief=tk.FLAT,
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
                               font=("TkFixedFont", 10), label="TIMELINE  ·  DRAG TO SEEK",
                               command=self._on_slider_scrub)
        self.slider.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=16, pady=4)

        self.lbl_tick_counter = tk.Label(controls, text="Tick: 0000 / 0000",
                                        font=("TkFixedFont", 12, "bold"), fg="#55d6be", bg="#0a0a0d")
        self.lbl_tick_counter.pack(side=tk.LEFT, padx=12)

        self.lbl_active_jams = tk.Label(controls, text="Active Blockages: 0",
                                        font=("TkDefaultFont", 11, "bold"), fg="#ff6577", bg="#0a0a0d")
        self.lbl_active_jams.pack(side=tk.RIGHT, padx=18)
        self.lbl_moving_bags = tk.Label(controls, text="Moving Packages: 0",
                                        font=("TkDefaultFont", 11, "bold"), fg="#73c7a2", bg="#0a0a0d")
        self.lbl_moving_bags.pack(side=tk.RIGHT, padx=12)

        content = tk.Frame(self.root, bg="#111115")
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        map_panel = tk.Frame(content, bg="#171a22")
        map_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        map_caption = tk.Frame(map_panel, bg="#171a22")
        map_caption.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(map_caption, text="CONVEYOR NETWORK", font=("TkDefaultFont", 11, "bold"),
                 fg="#e5e8ef", bg="#171a22").pack(side=tk.LEFT)
        tk.Label(map_caption, text="DIRECTED TRACK STATUS", font=("TkDefaultFont", 9),
                 fg="#818897", bg="#171a22").pack(side=tk.RIGHT)

        route_controls = tk.Frame(map_panel, bg="#171a22")
        route_controls.pack(fill=tk.X, padx=14, pady=(5, 6))
        self.lbl_route_selection = tk.Label(
            route_controls, text="Click two nodes to inspect paths in both directions",
            font=("TkDefaultFont", 10), fg="#b8c0ce", bg="#171a22", anchor=tk.W
        )
        self.lbl_route_selection.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.belt_visibility_button = tk.Checkbutton(
            route_controls, text="Show belts", variable=self.belts_visible,
            command=self._on_display_filters_changed,
            font=("TkDefaultFont", 9, "bold"), bg="#252a35", fg="#f0f2f6",
            activebackground="#343b4a", activeforeground="#ffffff",
            selectcolor="#171a22", relief=tk.FLAT, padx=7, pady=4
        )
        self.belt_visibility_button.pack(side=tk.RIGHT, padx=(4, 6))
        self.node_filter_menu = tk.Menu(self.root, tearoff=False, bg="#252a35", fg="#f0f2f6",
                                        activebackground="#3a4252", activeforeground="#ffffff")
        for node_id in self.network_nodes:
            self.node_filter_menu.add_checkbutton(
                label=f"Show {node_id}", variable=self.node_visibility[node_id],
                command=self._on_display_filters_changed
            )
        self.node_filter_button = tk.Menubutton(
            route_controls, text="Nodes ▾", menu=self.node_filter_menu,
            font=("TkDefaultFont", 9, "bold"), bg="#252a35", fg="#f0f2f6",
            activebackground="#343b4a", activeforeground="#ffffff",
            relief=tk.FLAT, padx=9, pady=4
        )
        self.node_filter_button.pack(side=tk.RIGHT, padx=4)
        self.btn_cancel_route = tk.Button(
            route_controls, text="Cancel route", command=self._cancel_route_selection,
            font=("TkDefaultFont", 9, "bold"), bg="#252a35", fg="#f0f2f6",
            activebackground="#343b4a", activeforeground="#ffffff", relief=tk.FLAT,
            padx=10, pady=4
        )
        self.btn_cancel_route.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(map_panel, bg="#14171e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 8))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        legend = tk.Frame(map_panel, bg="#171a22")
        legend.pack(fill=tk.X, padx=14, pady=(0, 12))
        self._add_legend_item(legend, "#ff6577", "JAMMED / ISSUE", bold=True)
        self._add_legend_item(legend, "#ff9f43", "HIGH RISK")
        self._add_legend_item(legend, "#c7d7e5", "SELECTED NODE")
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
        tk.Label(issue_header, text="ACTIVE ISSUES", font=("TkDefaultFont", 12, "bold"),
                 fg="#f0f2f6", bg="#191c25").pack(side=tk.LEFT)
        self.lbl_issue_count = tk.Label(issue_header, text="0", font=("TkFixedFont", 11, "bold"),
                                        fg="#ff6577", bg="#351e28", padx=8, pady=3)
        self.lbl_issue_count.pack(side=tk.RIGHT)
        tk.Label(issues_section, text="CURRENT SNAPSHOT  ·  JAMMED TRACKS", font=("TkDefaultFont", 9, "bold"),
                 fg="#818897", bg="#191c25", anchor=tk.W).pack(fill=tk.X, padx=16, pady=(0, 6))

        issue_body = tk.Frame(issue_panel, bg="#191c25")
        issue_body.pack(fill=tk.BOTH, expand=True, padx=(12, 8), pady=(0, 6))
        issue_body = tk.Frame(issues_section, bg="#191c25")
        issue_body.pack(fill=tk.BOTH, expand=True, padx=(12, 8), pady=(0, 8))
        issue_scrollbar = tk.Scrollbar(issue_body, orient=tk.VERTICAL)
        issue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.issue_text = tk.Text(issue_body, wrap=tk.WORD, state=tk.DISABLED,
                                  bg="#191c25", fg="#e5e8ef", insertbackground="#e5e8ef",
                                  relief=tk.FLAT, borderwidth=0, padx=5, pady=4,
                                  font=("TkDefaultFont", 10), height=8, yscrollcommand=issue_scrollbar.set)
        self.issue_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        issue_scrollbar.config(command=self.issue_text.yview)
        self.issue_text.tag_configure("issue_heading", foreground="#ff8190", font=("TkDefaultFont", 10, "bold"))
        self.issue_text.tag_configure("issue_reason", foreground="#c6cbd6")
        self.issue_text.tag_configure("issue_bags", foreground="#9da5b5", font=("TkFixedFont", 9))
        self.issue_text.tag_configure("empty_state", foreground="#73c7a2", font=("TkDefaultFont", 10))

        risk_header = tk.Frame(issue_panel, bg="#191c25")
        risk_header.pack(fill=tk.X, padx=16, pady=(8, 6))
        tk.Label(risk_header, text="PREDICTIVE PRIORITY", font=("TkDefaultFont", 11, "bold"),
                 fg="#f0f2f6", bg="#191c25").pack(side=tk.LEFT)
        self.lbl_risk_count = tk.Label(risk_header, text="0", font=("TkFixedFont", 10, "bold"),
                                       fg="#ffbf69", bg="#3a2a1c", padx=8, pady=3)
        self.lbl_risk_count.pack(side=tk.RIGHT)
        tk.Label(issue_panel, text="OPERATIONAL COMPONENTS  ·  HEURISTIC SCORES",
                 font=("TkDefaultFont", 9, "bold"), fg="#818897", bg="#191c25",
                 anchor=tk.W).pack(fill=tk.X, padx=16, pady=(0, 6))
        risk_body = tk.Frame(issue_panel, bg="#191c25")
        risk_body.pack(fill=tk.BOTH, expand=True, padx=(12, 8), pady=(0, 12))
        risk_scrollbar = tk.Scrollbar(risk_body, orient=tk.VERTICAL)
        risk_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.risk_text = tk.Text(risk_body, wrap=tk.WORD, state=tk.DISABLED,
                                 bg="#191c25", fg="#e5e8ef", relief=tk.FLAT,
                                 borderwidth=0, padx=5, pady=4,
                                 font=("TkDefaultFont", 10),
                                 yscrollcommand=risk_scrollbar.set)
        self.risk_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        risk_scrollbar.config(command=self.risk_text.yview)

        route_body = tk.Frame(map_panel, bg="#171a22")
        route_body.pack(fill=tk.X, padx=14, pady=(0, 10))
        tk.Label(route_body, text="PATHS & COMPONENT RISK  ·  HEURISTIC, NOT A PROBABILITY",
                 font=("TkDefaultFont", 9, "bold"), fg="#a9afbd", bg="#171a22",
                 anchor=tk.W).pack(fill=tk.X, pady=(0, 3))
        route_scrollbar = tk.Scrollbar(route_body, orient=tk.VERTICAL)
        route_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.route_text = tk.Text(route_body, height=6, wrap=tk.WORD, state=tk.DISABLED,
                                  bg="#14171e", fg="#e5e8ef", relief=tk.FLAT,
                                  borderwidth=0, padx=7, pady=5,
                                  font=("TkDefaultFont", 10),
                                  yscrollcommand=route_scrollbar.set)
        self.route_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        route_scrollbar.config(command=self.route_text.yview)

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
        tk.Label(item, text=label, font=("TkDefaultFont", 9, "bold" if bold else "normal"),
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

    def _on_canvas_click(self, event):
        """Use two direct map clicks to focus on all open routes between nodes."""
        scale, _, _ = self._canvas_transform()
        hit_radius = max(14, NODE_RADIUS * scale + 8)
        node_id = None
        nearest_distance = hit_radius
        for candidate, (x, y) in NODE_COORDINATES.items():
            mapped_x, mapped_y = self._map_point(x, y)
            distance = ((event.x - mapped_x) ** 2 + (event.y - mapped_y) ** 2) ** 0.5
            if distance <= nearest_distance:
                node_id = candidate
                nearest_distance = distance

        if node_id is None:
            return

        if self.selected_start is None or self.selected_destination is not None:
            self.selected_start = node_id
            self.selected_destination = None
        else:
            self.selected_destination = node_id

        self._update_route_selection_label()
        self._draw_static_network()
        self._update_display()

    def _cancel_route_selection(self):
        """Clear the selected pair and restore the complete network view."""
        self.selected_start = None
        self.selected_destination = None
        self._update_route_selection_label()
        self._draw_static_network()
        self._update_display()

    def _update_route_selection_label(self):
        if not hasattr(self, "lbl_route_selection"):
            return
        if self.selected_start is None:
            text = "Click two nodes to show open and blocked paths in both directions"
        elif self.selected_destination is None:
            text = f"From {self.selected_start} · click a destination node"
        else:
            text = (f"{self.selected_start} ↔ {self.selected_destination} · showing paths both ways; "
                    "open and blocked paths stay visible; "
                    "click another node to choose a new pair")
        self.lbl_route_selection.config(text=text)

    def _risks_for_tick(self):
        if self.current_tick not in self._risk_cache:
            self._risk_cache[self.current_tick] = calculate_risks(
                self.network_edges, self.history, self.current_tick
            )
            if len(self._risk_cache) > 64:
                self._risk_cache.pop(next(iter(self._risk_cache)))
        return self._risk_cache[self.current_tick]

    def _paths_for_tick(self, tick_data):
        if self.selected_start is None or self.selected_destination is None:
            return []
        cache_key = (self.current_tick, self.selected_start, self.selected_destination)
        if cache_key not in self._path_cache:
            directions = []
            for start, destination in (
                (self.selected_start, self.selected_destination),
                (self.selected_destination, self.selected_start),
            ):
                paths = find_simple_paths(
                    self.network_edges, start, destination, tick_data, include_jammed=True
                )
                directions.append((start, destination, paths))
            self._path_cache[cache_key] = directions
            if len(self._path_cache) > 128:
                self._path_cache.pop(next(iter(self._path_cache)))
        return self._path_cache[cache_key]

    def _node_is_visible(self, node_id):
        visibility = getattr(self, "node_visibility", {}).get(node_id)
        if visibility is None:
            return True
        return bool(visibility.get() if hasattr(visibility, "get") else visibility)

    def _belts_are_visible(self):
        visibility = getattr(self, "belts_visible", True)
        return bool(visibility.get() if hasattr(visibility, "get") else visibility)

    def _on_display_filters_changed(self):
        """Apply visual filters without changing telemetry or network alerts."""
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
            if not self._node_is_visible(node_id):
                color, label_color = "#555861", "#a4a8b0"

            cx, cy = self._map_point(x, y)
            r = NODE_RADIUS * scale
            outline = "#c7d7e5" if node_id in (self.selected_start, self.selected_destination) else "#d9deea"
            outline_width = max(2, scale * 3) if node_id in (self.selected_start, self.selected_destination) else max(1, scale * 1.5)
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline=outline,
                                    width=outline_width, tags="static_network")
            if outline != "#d9deea":
                self.canvas.create_oval(cx-r-4*scale, cy-r-4*scale, cx+r+4*scale, cy+r+4*scale,
                                        outline=outline, width=max(2, scale*2),
                                        tags="static_network")
            self.canvas.create_text(cx, cy, text=node_id,
                                    font=("TkFixedFont", max(8, round(10 * scale)), "bold"),
                                    fill=label_color, tags="static_network")

    def _update_display(self):
        """Redraw the selected network snapshot, routes, bags, and risk warnings."""
        self.canvas.delete("dynamic_overlay")

        tick_data = self.history.get(self.current_tick, {})
        edge_risks, node_risks = self._risks_for_tick()
        route_paths = self._paths_for_tick(tick_data)
        all_route_paths = [path for _, _, paths in route_paths for path in paths]
        route_selected = self.selected_start is not None and self.selected_destination is not None
        route_edge_ids = {edge_id for path in all_route_paths for edge_id in path["edges"]}
        route_node_ids = {node_id for path in all_route_paths for node_id in path["nodes"]}
        issue_details = []
        moving_bags_count = 0
        transit_details = []
        total_active_bags = 0
        progress = self.sub_tick / float(SUB_FRAMES_PER_TICK)
        scale, _, _ = self._canvas_transform()

        for edge_id, edge in tick_data.items():
            bags_count = max(0, int(edge.get("active_bags", 0)))
            bags_count = edge["active_bags"]
            total_active_bags += bags_count
            is_jammed = edge["status"] == "JAMMED"
            if is_jammed:
                reason = str(edge.get("fault_reason") or "Unspecified fault").strip()
                issue_details.append((str(edge_id), reason, bags_count))
            elif edge.get("status") == "OPERATIONAL":
                moving_bags_count += bags_count

            if not self._belts_are_visible():
                continue

            if route_selected and edge_id not in route_edge_ids:
                continue
            if bags_count > 0:
                transit_details.append((str(edge_id), bags_count, is_jammed))

            base_clean_id = edge_id.replace("_FWD", "").replace("_REV", "")
            parts = base_clean_id.split("_")
            if len(parts) != 3:
                continue
            _, u, v = parts 
            
            if edge_id.endswith("_REV"):
                u, v = v, u

            if u not in NODE_COORDINATES or v not in NODE_COORDINATES:
                continue

            x1, y1 = NODE_COORDINATES[u]
            x2, y2 = NODE_COORDINATES[v]
            x1, y1 = self._map_point(x1, y1)
            x2, y2 = self._map_point(x2, y2)

            # Vector projection geometry
            dx = x2 - x1
            dy = y2 - y1
            dist = (dx**2 + dy**2)**0.5
            if dist == 0:
                continue

            ux, uy = dx / dist, dy / dist  # Unit direction
            nx, ny = -uy, ux              # Normal perpendicular

            # Parallel split lane offset shifting logic
            line_offset = 0
            if edge_id.endswith("_FWD"):   line_offset = 6 * scale
            elif edge_id.endswith("_REV"): line_offset = 6 * scale

            # --- PRECISE EDGE CORNER TRIMMING ---
            # Trimming by NODE_RADIUS + 14 ensures that arrowheads terminate perfectly 
            # on the outer rim perimeter of the circles without covering node text labels.
            x1_s = x1 + ux * (NODE_RADIUS + 2) * scale + nx * line_offset
            y1_s = y1 + uy * (NODE_RADIUS + 2) * scale + ny * line_offset
            x2_s = x2 - ux * (NODE_RADIUS + 14) * scale + nx * line_offset
            y2_s = y2 - uy * (NODE_RADIUS + 14) * scale + ny * line_offset

            edge_risk = edge_risks.get(edge_id, {})
            is_warning = edge_risk.get("is_warning", False)
            dimmed = not self._node_is_visible(u) or not self._node_is_visible(v)
            if is_jammed:
                line_color = "#ff6577"  # Jammed: Crimson Red
                line_width = 3.5 * scale
            elif is_warning:
                line_color = "#ff9f43"
                line_width = 4 * scale
            elif bags_count > 0:
                line_color = "#ffbf69"  # Occupied: Safety Orange
                line_width = 2.5 * scale
            else:
                line_color = "#3a3f4b"  # Idle Track: Dark Grey
                line_width = 1.5 * scale
            if dimmed:
                line_color = "#292d36"
                line_width = max(1, 1.5 * scale)

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
                                        fill="#565b65" if dimmed else "#9f2637",
                                        outline="#9197a1" if dimmed else "#fff0f2",
                                        width=max(1, scale),
                                        tags="dynamic_overlay")
                self.canvas.create_text(marker_x, marker_y, text="!",
                                        font=("TkDefaultFont", max(9, round(12 * scale)), "bold"),
                                        fill="#c2c5cc" if dimmed else "white", tags="dynamic_overlay")
            elif is_warning:
                marker_x, marker_y = (x1_s + x2_s) / 2, (y1_s + y2_s) / 2
                self.canvas.create_text(marker_x, marker_y, text=str(edge_risk["score"]),
                                        font=("TkFixedFont", max(8, round(10 * scale)), "bold"),
                                        fill="#8b909e" if dimmed else "#ffd2a1",
                                        tags="dynamic_overlay")

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
                                                fill="#8b909e" if dimmed else "#ff6577",
                                                outline="#b5bac4" if dimmed else "white", width=0.5,
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
                                                    fill="#8b909e" if dimmed else "#ffbf69",
                                                    outline="#b5bac4" if dimmed else "white", width=0.5,
                                                    tags="dynamic_overlay")

        for node_id, score in node_risks.items():
            if score < RISK_WARNING_THRESHOLD or (route_selected and node_id not in route_node_ids):
                continue
            cx, cy = self._map_point(*NODE_COORDINATES[node_id])
            radius = NODE_RADIUS * scale + 5 * scale
            warning_color = "#666b75" if not self._node_is_visible(node_id) else "#ff9f43"
            self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                    outline=warning_color, width=max(2, 2 * scale),
                                    tags="dynamic_overlay")
            self.canvas.create_text(cx, cy-radius-8*scale, text=str(score),
                                    font=("TkFixedFont", max(8, round(9*scale)), "bold"),
                                    fill="#8b909e" if not self._node_is_visible(node_id) else "#ffd2a1",
                                    tags="dynamic_overlay")

        issue_details.sort(key=lambda issue: issue[0])
        transit_details.sort(key=lambda item: (-item[1], item[0]))
        self._render_issue_list(issue_details)
        self._render_risk_list(edge_risks, node_risks)
        self._render_route_summary(route_paths, edge_risks, node_risks)
        self._render_transit_list(transit_details, total_active_bags)

        # Sync readouts
        self.lbl_tick_counter.config(text=f"Tick: {self.current_tick:04d} / {self.max_ticks:04d}")
        self.lbl_active_bags.config(text=f"Active Bags: {total_active_bags}")
        self.lbl_active_jams.config(text=f"Active Blockages: {len(issue_details)}")
        self.lbl_moving_bags.config(text=f"Moving Packages: {moving_bags_count}")

        # Update timeline scrubber slider handle smoothly without firing bound callbacks
        self.updating_via_slider = True
        self.slider.set(self.current_tick)
        self.updating_via_slider = False

    def _render_risk_list(self, edge_risks, node_risks):
        """Show prioritized operational warnings separately from current jams."""
        warnings = []
        for edge_id, risk in edge_risks.items():
            if risk["is_warning"]:
                warnings.append((risk["priority_score"], "BELT", edge_id, risk))
        for node_id, score in node_risks.items():
            if score >= RISK_WARNING_THRESHOLD:
                warnings.append((score, "NODE", node_id, {"score": score}))
        warnings.sort(key=lambda item: (-item[0], item[1], item[2]))
        rendered = tuple((priority, kind, component, tuple(sorted(details.items())))
                         for priority, kind, component, details in warnings)
        if rendered == self._last_rendered_risks:
            return

        self._last_rendered_risks = rendered
        self.lbl_risk_count.config(text=str(len(warnings)))
        self.risk_text.configure(state=tk.NORMAL)
        self.risk_text.delete("1.0", tk.END)
        if not warnings:
            self.risk_text.insert(tk.END, "No components currently exceed the early-warning threshold.")
        else:
            for priority, kind, component, details in warnings:
                details = dict(details)
                if kind == "BELT":
                    self.risk_text.insert(
                        tk.END,
                        f"BELT {component} · {details['score']}/100 risk\n",
                        "risk_heading",
                    )
                    estimated_ticks = details["estimated_ticks_to_wear"]
                    if estimated_ticks is None:
                        wear_forecast = "wear threshold: no recent positive usage trend"
                    else:
                        wear_forecast = (
                            f"wear threshold in about {estimated_ticks} tick(s) "
                            f"at {details['wear_rate_per_tick']}/tick"
                        )
                    self.risk_text.insert(
                        tk.END,
                        f"  Priority {priority}/100 · wear {details['wear_score']} · "
                        f"wear projection {details['wear_projection_score']} · "
                        f"congestion {details['congestion_score']} "
                        f"(occupancy {details['occupancy_score']}, growth {details['growth_score']})\n"
                        f"  {wear_forecast} · {details['active_bags']} active bag(s)\n\n",
                    )
                else:
                    self.risk_text.insert(tk.END, f"NODE {component} · {details['score']}/100 risk\n\n",
                                          "risk_heading")
        self.risk_text.configure(state=tk.DISABLED)

    def _render_route_summary(self, paths, edge_risks, node_risks):
        if self.selected_start is None:
            summary = ("Click two nodes to isolate directed paths in both directions; "
                       "blocked routes stay visible in their status colors.")
        elif self.selected_destination is None:
            summary = f"Start node: {self.selected_start}. Click a destination node to complete the route view."
        elif not any(direction_paths for _, _, direction_paths in paths):
            summary = (f"No directed paths between {self.selected_start} and {self.selected_destination} "
                       f"at tick {self.current_tick}. Click another node to start a new pair, or cancel.")
        else:
            summary_lines = [
                f"Directed paths in both directions between {self.selected_start} and "
                f"{self.selected_destination}.",
                "Bag counts are per belt; telemetry cannot identify an individual package.",
            ]
            path_number = 0
            for start, destination, direction_paths in paths:
                if not direction_paths:
                    summary_lines.append(f"{start} → {destination}: no directed path.")
                    continue

                blocked_count = sum(path["is_blocked"] for path in direction_paths)
                open_count = len(direction_paths) - blocked_count
                summary_lines.append(
                    f"{start} → {destination}: {len(direction_paths)} directed path(s) "
                    f"({open_count} open, {blocked_count} blocked)."
                )
                for path in direction_paths:
                    path_number += 1
                    path_status = "BLOCKED" if path["is_blocked"] else "OPEN"
                    summary_lines.append(f"{path_number}. [{path_status}] {' → '.join(path['nodes'])}")
                    for edge_id in path["edges"]:
                        risk = edge_risks.get(edge_id, {})
                        edge_status = "BLOCKED" if edge_id in path["blocked_edges"] else "OPEN"
                        estimated_ticks = risk.get("estimated_ticks_to_wear")
                        eta = f"ETA {estimated_ticks} ticks" if estimated_ticks is not None else "ETA unknown"
                        summary_lines.append(
                            f"   BELT {edge_id} · {edge_status}: {risk.get('score', 0)}/100 risk "
                            f"(wear {risk.get('wear_score', 0)}, wear forecast {risk.get('wear_projection_score', 0)}, "
                            f"congestion {risk.get('congestion_score', 0)}, {eta}); "
                            f"{risk.get('active_bags', 0)} active bag(s)"
                        )
                    node_scores = [f"{node} {node_risks.get(node, 0)}/100" for node in path["nodes"]]
                    summary_lines.append(f"   Node risk: {' · '.join(node_scores)}")
            summary = "\n".join(summary_lines)

        if summary == self._last_rendered_paths:
            return
        self._last_rendered_paths = summary
        self.route_text.configure(state=tk.NORMAL)
        self.route_text.delete("1.0", tk.END)
        self.route_text.insert(tk.END, summary)
        self.route_text.configure(state=tk.DISABLED)

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
