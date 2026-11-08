import unittest
from types import SimpleNamespace

from bsd_dashboard import BSDDashboard, NODE_COORDINATES, SUB_FRAMES_PER_TICK
from dashboard_analysis import load_topology


class FakeCanvas:
    def __init__(self, width=1000, height=700):
        self.width = width
        self.height = height
        self.items = []

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def delete(self, tag):
        self.items = [item for item in self.items if item[2].get("tags") != tag]

    def create_line(self, *coordinates, **options):
        self.items.append(("line", coordinates, options))

    def create_oval(self, *coordinates, **options):
        self.items.append(("oval", coordinates, options))

    def create_text(self, *coordinates, **options):
        self.items.append(("text", coordinates, options))


class FakeLabel:
    def __init__(self):
        self.options = {}

    def config(self, **options):
        self.options.update(options)


class FakeSlider:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class FakeText:
    def __init__(self):
        self.content = ""
        self.state = None
        self.delete_count = 0

    def configure(self, **options):
        self.state = options.get("state", self.state)

    def delete(self, start, end):
        self.content = ""
        self.delete_count += 1

    def insert(self, position, content, tag=None):
        self.content += content


class FakeButton:
    def __init__(self):
        self.options = {}

    def config(self, **options):
        self.options.update(options)


class FakeVariable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def make_dashboard(history=None, max_ticks=3):
    dashboard = BSDDashboard.__new__(BSDDashboard)
    dashboard.canvas = FakeCanvas()
    dashboard.network_nodes, dashboard.network_edges = load_topology()
    dashboard.history = history or {}
    dashboard.current_tick = 1
    dashboard.sub_tick = 0
    dashboard.max_ticks = max_ticks
    dashboard.is_playing = False
    dashboard.updating_via_slider = False
    dashboard._last_rendered_issues = None
    dashboard._last_rendered_risks = None
    dashboard._last_rendered_paths = None
    dashboard._canvas_render_size = None
    dashboard._risk_cache = {}
    dashboard._path_cache = {}
    dashboard.selected_start = None
    dashboard.selected_destination = None
    dashboard.node_visibility = {node_id: FakeVariable(True) for node_id in NODE_COORDINATES}
    dashboard.belts_visible = FakeVariable(True)
    dashboard.lbl_tick_counter = FakeLabel()
    dashboard.lbl_active_jams = FakeLabel()
    dashboard.lbl_moving_bags = FakeLabel()
    dashboard.lbl_issue_count = FakeLabel()
    dashboard.lbl_risk_count = FakeLabel()
    dashboard.issue_text = FakeText()
    dashboard.risk_text = FakeText()
    dashboard.route_text = FakeText()
    dashboard.slider = FakeSlider()
    dashboard.btn_play = FakeButton()
    return dashboard


def click_node(dashboard, node_id):
    x, y = dashboard._map_point(*NODE_COORDINATES[node_id])
    dashboard._on_canvas_click(SimpleNamespace(x=x, y=y))


class BSDDashboardTests(unittest.TestCase):
    def test_jammed_edge_shows_map_badge_and_issue_details(self):
        dashboard = make_dashboard({1: {
            "e_JA1_JA2_FWD": {
                "status": "JAMMED",
                "fault_reason": "Motor overload",
                "active_bags": 2,
            }
        }})

        dashboard._update_display()

        self.assertEqual(dashboard.lbl_active_jams.options["text"], "Active Blockages: 1")
        self.assertEqual(dashboard.lbl_issue_count.options["text"], "1")
        self.assertIn("e_JA1_JA2_FWD  ·  FORWARD", dashboard.issue_text.content)
        self.assertIn("Motor overload", dashboard.issue_text.content)
        self.assertIn("2 active bag(s)", dashboard.issue_text.content)
        self.assertIn("#ff6577", [item[2].get("fill") for item in dashboard.canvas.items
                                  if item[0] == "line"])
        self.assertEqual(len([item for item in dashboard.canvas.items
                              if item[0] == "text" and item[2].get("text") == "!"]), 1)
        self.assertEqual(dashboard.issue_text.state, "disabled")

        issue_refresh_count = dashboard.issue_text.delete_count
        dashboard._update_display()
        self.assertEqual(dashboard.issue_text.delete_count, issue_refresh_count)

    def test_unmapped_jam_and_missing_reason_remain_in_issue_queue(self):
        dashboard = make_dashboard({1: {
            "e_UNKNOWN_EDGE_REV": {
                "status": "JAMMED",
                "fault_reason": "",
                "active_bags": 0,
            }
        }})

        dashboard._update_display()

        self.assertIn("e_UNKNOWN_EDGE_REV  ·  REVERSE", dashboard.issue_text.content)
        self.assertIn("Unspecified fault", dashboard.issue_text.content)
        self.assertIn("0 active bag(s)", dashboard.issue_text.content)
        self.assertEqual(dashboard.lbl_active_jams.options["text"], "Active Blockages: 1")
        self.assertFalse(any(item[0] == "text" and item[2].get("text") == "!"
                             for item in dashboard.canvas.items))

    def test_operational_tracks_keep_occupied_and_idle_statuses(self):
        dashboard = make_dashboard({1: {
            "e_JA1_JA2_FWD": {
                "status": "OPERATIONAL",
                "fault_reason": "",
                "active_bags": 2,
            },
            "e_JA2_JA3": {
                "status": "OPERATIONAL",
                "fault_reason": "",
                "active_bags": 0,
            },
        }})
        dashboard.sub_tick = SUB_FRAMES_PER_TICK // 2

        dashboard._update_display()

        line_colors = [item[2].get("fill") for item in dashboard.canvas.items if item[0] == "line"]
        self.assertIn("#ffbf69", line_colors)
        self.assertIn("#3a3f4b", line_colors)
        self.assertEqual(len([item for item in dashboard.canvas.items
                              if item[0] == "oval" and item[2].get("fill") == "#ffbf69"]), 2)
        self.assertEqual(dashboard.lbl_active_jams.options["text"], "Active Blockages: 0")
        self.assertIn("No active issues", dashboard.issue_text.content)

    def test_resized_network_nodes_fit_inside_the_canvas(self):
        dashboard = make_dashboard()
        dashboard.canvas.width = 500
        dashboard.canvas.height = 400

        dashboard._on_canvas_resize(SimpleNamespace(width=500, height=400))

        node_items = [item for item in dashboard.canvas.items
                      if item[0] == "oval" and item[2].get("tags") == "static_network"]
        self.assertEqual(len(node_items), len(NODE_COORDINATES))
        for _, coordinates, _ in node_items:
            self.assertGreaterEqual(coordinates[0], 0)
            self.assertGreaterEqual(coordinates[1], 0)
            self.assertLessEqual(coordinates[2], dashboard.canvas.width)
            self.assertLessEqual(coordinates[3], dashboard.canvas.height)

    def test_scrub_and_step_navigation_update_the_snapshot(self):
        dashboard = make_dashboard(max_ticks=3)
        dashboard._on_slider_scrub("2")
        self.assertEqual(dashboard.current_tick, 2)
        self.assertEqual(dashboard.sub_tick, 0)
        self.assertEqual(dashboard.slider.value, 2)

        dashboard._next_tick()
        self.assertEqual(dashboard.current_tick, 3)
        dashboard._prev_tick()
        self.assertEqual(dashboard.current_tick, 2)
        self.assertEqual(dashboard.lbl_tick_counter.options["text"], "Tick: 0002 / 0003")

    def test_selected_nodes_show_all_open_routes_and_component_risks(self):
        dashboard = make_dashboard({1: {
            "e_IA1_JA1": {"status": "OPERATIONAL", "active_bags": 1, "volume": 20},
            "e_JA1_S1": {"status": "OPERATIONAL", "active_bags": 0, "volume": 5},
            "e_S1_GA1": {"status": "OPERATIONAL", "active_bags": 0, "volume": 3},
            "e_IA1_JA2": {"status": "OPERATIONAL", "active_bags": 0, "volume": 4},
            "e_JA1_JA2": {"status": "OPERATIONAL", "active_bags": 0, "volume": 6},
            "e_JA2_S2": {"status": "OPERATIONAL", "active_bags": 0, "volume": 4},
            "e_S2_GA2": {"status": "OPERATIONAL", "active_bags": 0, "volume": 3},
        }})
        dashboard._update_display()
        click_node(dashboard, "IA1")
        click_node(dashboard, "GA2")

        self.assertIn("directed path(s)", dashboard.route_text.content)
        self.assertIn("IA1 → JA2 → S2 → GA2", dashboard.route_text.content)
        self.assertIn("Node risk:", dashboard.route_text.content)
        self.assertIn("wear", dashboard.route_text.content)
        self.assertFalse(any(item[0] == "line" and item[2].get("fill") == "#55d6be"
                             for item in dashboard.canvas.items))
        self.assertTrue(any(item[0] == "line" and item[2].get("fill") == "#ffbf69"
                            for item in dashboard.canvas.items))

    def test_route_selection_keeps_blocked_path_and_updates_when_unjammed(self):
        dashboard = make_dashboard({
            1: {"e_IA1_JA1": {"status": "JAMMED", "active_bags": 1, "volume": 20}},
            2: {"e_IA1_JA1": {"status": "OPERATIONAL", "active_bags": 1, "volume": 21}},
        }, max_ticks=2)
        click_node(dashboard, "IA1")
        click_node(dashboard, "JA1")

        self.assertIn("BLOCKED", dashboard.route_text.content)
        self.assertIn("IA1 → JA1", dashboard.route_text.content)
        self.assertIn("e_IA1_JA1", dashboard.issue_text.content)
        self.assertIn("#ff6577", [item[2].get("fill") for item in dashboard.canvas.items
                                  if item[0] == "line"])
        self.assertFalse(any(item[0] == "line" and item[2].get("fill") == "#55d6be"
                             for item in dashboard.canvas.items))

        dashboard._next_tick()
        self.assertIn("OPEN", dashboard.route_text.content)
        self.assertIn("No active issues", dashboard.issue_text.content)

        click_node(dashboard, "JA2")
        self.assertEqual(dashboard.selected_start, "JA2")
        self.assertIsNone(dashboard.selected_destination)
        self.assertNotIn("No directed path", dashboard.route_text.content)

    def test_selected_pair_shows_both_directions_and_keeps_lanes_separate(self):
        dashboard = make_dashboard({1: {
            "e_JA1_JB1_FWD": {"status": "OPERATIONAL", "active_bags": 2, "volume": 10},
            "e_JA1_JB1_REV": {"status": "JAMMED", "active_bags": 1, "volume": 8},
        }})
        dashboard.network_edges = [
            edge for edge in dashboard.network_edges
            if edge["id"] in ("e_JA1_JB1_FWD", "e_JA1_JB1_REV")
        ]

        click_node(dashboard, "JA1")
        click_node(dashboard, "JB1")

        self.assertIn("JA1 → JB1: 1 directed path(s)", dashboard.route_text.content)
        self.assertIn("JB1 → JA1: 1 directed path(s)", dashboard.route_text.content)
        self.assertIn("[OPEN] JA1 → JB1", dashboard.route_text.content)
        self.assertIn("[BLOCKED] JB1 → JA1", dashboard.route_text.content)
        self.assertIn("e_JA1_JB1_FWD", dashboard.route_text.content)
        self.assertIn("e_JA1_JB1_REV", dashboard.route_text.content)

        lines = [item for item in dashboard.canvas.items
                 if item[0] == "line" and item[2].get("tags") == "dynamic_overlay"]
        self.assertEqual(len(lines), 2)
        self.assertNotEqual(lines[0][1], lines[1][1])
        first_midpoint = ((lines[0][1][0] + lines[0][1][2]) / 2,
                          (lines[0][1][1] + lines[0][1][3]) / 2)
        second_midpoint = ((lines[1][1][0] + lines[1][1][2]) / 2,
                           (lines[1][1][1] + lines[1][1][3]) / 2)
        self.assertGreater(abs(first_midpoint[0] - second_midpoint[0]), 5)

    def test_route_inspection_reports_asymmetric_paths_in_either_click_order(self):
        dashboard = make_dashboard({1: {
            "e_S1_GA1": {"status": "OPERATIONAL", "active_bags": 1, "volume": 1},
        }})

        click_node(dashboard, "GA1")
        click_node(dashboard, "S1")
        self.assertIn("GA1 → S1: no directed path", dashboard.route_text.content)
        self.assertIn("S1 → GA1: 1 directed path(s)", dashboard.route_text.content)
        self.assertIn("e_S1_GA1", dashboard.route_text.content)

        click_node(dashboard, "S1")
        click_node(dashboard, "GA1")
        self.assertIn("S1 → GA1: 1 directed path(s)", dashboard.route_text.content)
        self.assertIn("GA1 → S1: no directed path", dashboard.route_text.content)

        click_node(dashboard, "GA1")
        click_node(dashboard, "GB4")
        self.assertIn("No directed paths between GA1 and GB4", dashboard.route_text.content)

    def test_route_mode_hides_unrelated_belts_and_bags_until_cancelled(self):
        dashboard = make_dashboard({1: {
            "e_IA1_JA1": {"status": "OPERATIONAL", "active_bags": 1, "volume": 1},
            "e_JA1_S1": {"status": "OPERATIONAL", "active_bags": 1, "volume": 1},
            "e_S1_GA1": {"status": "OPERATIONAL", "active_bags": 1, "volume": 1},
            "e_IB2_JB4": {"status": "OPERATIONAL", "active_bags": 4, "volume": 1},
        }})
        dashboard.sub_tick = SUB_FRAMES_PER_TICK // 2
        click_node(dashboard, "IA1")
        self.assertIsNone(dashboard.selected_destination)
        click_node(dashboard, "GA1")

        lines = [item for item in dashboard.canvas.items
                 if item[0] == "line" and item[2].get("tags") == "dynamic_overlay"]
        bags = [item for item in dashboard.canvas.items
                if item[0] == "oval" and item[2].get("tags") == "dynamic_overlay"
                and item[2].get("fill") == "#ffbf69"]
        self.assertEqual(len(lines), 3)  # Route isolation draws status-colored belts once.
        self.assertEqual(len(bags), 3)

        dashboard._cancel_route_selection()
        restored_lines = [item for item in dashboard.canvas.items
                          if item[0] == "line" and item[2].get("tags") == "dynamic_overlay"]
        self.assertEqual(len(restored_lines), 4)
        self.assertIsNone(dashboard.selected_start)

    def test_moving_package_count_ignores_route_and_display_filters(self):
        dashboard = make_dashboard({1: {
            "e_IA1_JA1": {"status": "OPERATIONAL", "active_bags": 2, "volume": 1},
            "e_JA1_S1": {"status": "JAMMED", "active_bags": 3, "volume": 1},
            "e_IB2_JB4": {"status": "OPERATIONAL", "active_bags": 4, "volume": 1},
        }})
        dashboard._update_display()
        self.assertEqual(dashboard.lbl_moving_bags.options["text"], "Moving Packages: 6")

        click_node(dashboard, "IA1")
        click_node(dashboard, "JA1")
        dashboard.node_visibility["IA1"].set(False)
        dashboard.belts_visible.set(False)
        dashboard._on_display_filters_changed()

        self.assertEqual(dashboard.lbl_moving_bags.options["text"], "Moving Packages: 6")
        self.assertFalse(any(item[0] == "line" and item[2].get("tags") == "dynamic_overlay"
                             for item in dashboard.canvas.items))
        self.assertIn("e_JA1_S1", dashboard.issue_text.content)

        dashboard.belts_visible.set(True)
        dashboard._on_display_filters_changed()
        self.assertTrue(any(item[0] == "line" and item[2].get("tags") == "dynamic_overlay"
                            for item in dashboard.canvas.items))

    def test_hidden_nodes_and_connected_belts_are_dimmed(self):
        dashboard = make_dashboard({1: {
            "e_IA1_JA1": {"status": "OPERATIONAL", "active_bags": 1, "volume": 1},
        }})
        dashboard.node_visibility["IA1"].set(False)
        dashboard._draw_static_network()
        dashboard._update_display()

        ia1_x, ia1_y = dashboard._map_point(*NODE_COORDINATES["IA1"])
        node = next(item for item in dashboard.canvas.items if item[0] == "oval"
                    and item[2].get("tags") == "static_network"
                    and item[1][0] < ia1_x < item[1][2]
                    and item[1][1] < ia1_y < item[1][3])
        self.assertEqual(node[2]["fill"], "#555861")
        self.assertIn("#292d36", [item[2].get("fill") for item in dashboard.canvas.items
                                  if item[0] == "line"])
        self.assertIn("#8b909e", [item[2].get("fill") for item in dashboard.canvas.items
                                  if item[0] == "oval" and item[2].get("tags") == "dynamic_overlay"])

    def test_early_risk_is_prioritized_separately_from_observed_jams(self):
        dashboard = make_dashboard({1: {
            "e_JA1_JA2": {
                "status": "OPERATIONAL",
                "active_bags": 4,
                "volume": 130,
            }
        }})

        dashboard._update_display()

        self.assertIn("BELT e_JA1_JA2", dashboard.risk_text.content)
        self.assertIn("/100 risk", dashboard.risk_text.content)
        self.assertIn("wear threshold", dashboard.risk_text.content)
        self.assertIn("congestion", dashboard.risk_text.content)
        self.assertIn("#ff9f43", [item[2].get("fill") for item in dashboard.canvas.items
                                  if item[0] == "line"])
        self.assertEqual(dashboard.lbl_active_jams.options["text"], "Active Blockages: 0")

    def test_playback_stops_at_the_last_tick(self):
        dashboard = make_dashboard(max_ticks=2)
        dashboard.current_tick = 2
        dashboard.sub_tick = SUB_FRAMES_PER_TICK - 1
        dashboard.is_playing = True

        dashboard._playback_loop()

        self.assertFalse(dashboard.is_playing)
        self.assertEqual(dashboard.btn_play.options["text"], "▶ Play System")


if __name__ == "__main__":
    unittest.main()