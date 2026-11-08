import unittest

from dashboard_analysis import calculate_risks, find_simple_paths, load_topology


class DashboardAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.edges = [
            {"id": "e_AB_FWD", "from": "A", "to": "B", "wear_threshold": 100},
            {"id": "e_AB_REV", "from": "B", "to": "A", "wear_threshold": 100},
            {"id": "e_BD", "from": "B", "to": "D", "wear_threshold": 100},
            {"id": "e_AC", "from": "A", "to": "C", "wear_threshold": 100},
            {"id": "e_CD", "from": "C", "to": "D", "wear_threshold": 100},
        ]

    def test_layout_expands_bidirectional_belts_independently(self):
        nodes, edges = load_topology()
        belt_by_id = {edge["id"]: edge for edge in edges}

        self.assertIn("e_JA1_JB1_FWD", belt_by_id)
        self.assertIn("e_JA1_JB1_REV", belt_by_id)
        self.assertEqual(belt_by_id["e_JA1_JB1_FWD"]["from"], "JA1")
        self.assertEqual(belt_by_id["e_JA1_JB1_REV"]["from"], "JB1")
        self.assertEqual(len(nodes), 28)

    def test_paths_are_directed_simple_and_skip_only_jammed_belts(self):
        paths = find_simple_paths(self.edges, "A", "D")
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(len(path["nodes"]) == len(set(path["nodes"])) for path in paths))
        self.assertEqual(find_simple_paths(self.edges, "A", "A"), [])
        self.assertEqual(find_simple_paths(self.edges, "D", "A"), [])

        unblocked = find_simple_paths(self.edges, "A", "D", {
            "e_AB_FWD": {"status": "JAMMED"}
        })
        self.assertEqual(len(unblocked), 1)
        self.assertEqual(unblocked[0]["edges"], ("e_AC", "e_CD"))

    def test_route_inspection_includes_and_marks_blocked_paths(self):
        paths = find_simple_paths(self.edges, "A", "D", {
            "e_AB_FWD": {"status": "JAMMED"}
        }, include_jammed=True)

        blocked_path = next(path for path in paths if path["edges"] == ("e_AB_FWD", "e_BD"))
        open_path = next(path for path in paths if path["edges"] == ("e_AC", "e_CD"))
        self.assertEqual(blocked_path["blocked_edges"], ("e_AB_FWD",))
        self.assertTrue(blocked_path["is_blocked"])
        self.assertEqual(open_path["blocked_edges"], ())
        self.assertFalse(open_path["is_blocked"])

    def test_risk_is_causal_component_based_and_direction_specific(self):
        history = {
            1: {
                "e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 0, "volume": 10},
                "e_AB_REV": {"status": "OPERATIONAL", "active_bags": 0, "volume": 5},
            },
            4: {
                "e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 3, "volume": 50},
                "e_AB_REV": {"status": "JAMMED", "active_bags": 0, "volume": 6},
            },
            5: {
                "e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 4, "volume": 100},
            },
        }

        edge_risks, node_risks = calculate_risks(self.edges, history, 4)
        future_independent, _ = calculate_risks(self.edges, {
            **history,
            6: {"e_AB_FWD": {"status": "JAMMED", "active_bags": 10, "volume": 100}},
        }, 4)

        self.assertEqual(edge_risks["e_AB_FWD"]["score"], 100)
        self.assertTrue(edge_risks["e_AB_FWD"]["is_warning"])
        self.assertEqual(edge_risks["e_AB_FWD"]["growth_score"], 100)
        self.assertEqual(edge_risks["e_AB_FWD"]["estimated_ticks_to_wear"], 4)
        self.assertEqual(edge_risks["e_AB_FWD"]["congestion_score"], 100)
        self.assertEqual(edge_risks["e_AB_FWD"], future_independent["e_AB_FWD"])
        self.assertFalse(edge_risks["e_AB_REV"]["is_warning"])
        self.assertEqual(edge_risks["e_AB_REV"]["score"], 100)
        self.assertEqual(node_risks["A"], 80)

    def test_wear_alone_can_raise_an_early_warning_without_a_jam(self):
        edge_risks, _ = calculate_risks(
            self.edges,
            {1: {"e_AB_FWD": {
                "status": "OPERATIONAL", "active_bags": 0, "volume": 70,
            }}},
            1,
        )

        risk = edge_risks["e_AB_FWD"]
        self.assertEqual(risk["score"], 70)
        self.assertEqual(risk["priority_score"], 70)
        self.assertTrue(risk["is_warning"])
        self.assertFalse(risk["is_jammed"])

    def test_wear_forecast_uses_sparse_prior_samples_and_has_safe_edges(self):
        edge_risks, _ = calculate_risks(self.edges, {
            1: {"e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 0, "volume": 10}},
            4: {"e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 0, "volume": 40}},
            8: {"e_AB_FWD": {"status": "JAMMED", "active_bags": 0, "volume": 100}},
        }, 4)
        risk = edge_risks["e_AB_FWD"]
        self.assertEqual(risk["wear_rate_per_tick"], 10.0)
        self.assertEqual(risk["estimated_ticks_to_wear"], 6)
        self.assertEqual(risk["wear_projection_score"], 90)

        no_growth, _ = calculate_risks(self.edges, {
            1: {"e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 0, "volume": 40}},
            4: {"e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 0, "volume": 40}},
        }, 4)
        self.assertIsNone(no_growth["e_AB_FWD"]["estimated_ticks_to_wear"])
        self.assertEqual(no_growth["e_AB_FWD"]["wear_projection_score"], 0)

        reached_threshold, _ = calculate_risks(self.edges, {
            4: {"e_AB_FWD": {"status": "OPERATIONAL", "active_bags": 0, "volume": 100}},
        }, 4)
        self.assertEqual(reached_threshold["e_AB_FWD"]["estimated_ticks_to_wear"], 0)
        self.assertEqual(reached_threshold["e_AB_FWD"]["wear_projection_score"], 100)


if __name__ == "__main__":
    unittest.main()