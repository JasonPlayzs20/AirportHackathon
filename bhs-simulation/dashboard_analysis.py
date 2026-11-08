"""Causal route and equipment-risk analysis for the BSD dashboard."""

import json
from bisect import bisect_right
from pathlib import Path


LAYOUT_PATH = Path(__file__).resolve().parent / "data" / "network_layout.json"
RISK_WARNING_THRESHOLD = 65
WEAR_FORECAST_HORIZON_TICKS = 60


def _telemetry_for_edge(snapshot, edge_id):
    telemetry = snapshot.get(edge_id)
    if telemetry is None and not edge_id.endswith(("_FWD", "_REV")):
        telemetry = snapshot.get(edge_id + "_FWD")
    return telemetry or {}


def load_topology(layout_path=LAYOUT_PATH):
    """Load layout nodes and expand bidirectional lines into directed belts."""
    with open(layout_path, "r") as layout_file:
        layout = json.load(layout_file)

    nodes = [node["id"] for node in layout["nodes"]]
    edges = []
    for edge in layout["edges"]:
        if edge["bidirectional"]:
            edges.append(dict(edge, id=edge["id"] + "_FWD"))
            edges.append(dict(edge, id=edge["id"] + "_REV", **{
                "from": edge["to"], "to": edge["from"]
            }))
        else:
            edges.append(dict(edge))
    return nodes, edges


def find_simple_paths(edges, start, destination, tick_data=None, include_jammed=False):
    """Return directed simple paths, optionally retaining paths blocked by jams."""
    if start == destination:
        return []

    adjacency = {}
    tick_data = tick_data or {}
    for edge in edges:
        telemetry = _telemetry_for_edge(tick_data, edge["id"])
        if telemetry.get("status") == "JAMMED" and not include_jammed:
            continue
        adjacency.setdefault(edge["from"], []).append(edge)

    for outgoing in adjacency.values():
        outgoing.sort(key=lambda edge: edge["id"])

    paths = []

    def visit(node, seen_nodes, path_nodes, path_edges):
        if node == destination:
            blocked_edges = tuple(
                edge_id for edge_id in path_edges
                if _telemetry_for_edge(tick_data, edge_id).get("status") == "JAMMED"
            )
            paths.append({
                "nodes": tuple(path_nodes),
                "edges": tuple(path_edges),
                "blocked_edges": blocked_edges,
                "is_blocked": bool(blocked_edges),
            })
            return
        for edge in adjacency.get(node, ()):
            next_node = edge["to"]
            if next_node in seen_nodes:
                continue
            visit(next_node, seen_nodes | {next_node}, path_nodes + [next_node],
                  path_edges + [edge["id"]])

    visit(start, {start}, [start], [])
    paths.sort(key=lambda path: (len(path["edges"]), path["edges"]))
    return paths


def calculate_risks(edges, history, tick):
    """Score directed belts and nodes from data available no later than tick.

    Scores are heuristic indices, not probabilities. Risk is the strongest of
    wear proximity, projected wear within a fixed horizon, and congestion. Rates
    compare the current sample with the latest known sample at least three ticks
    earlier (or the latest prior sample when history is shorter).
    """
    edge_risks = {}
    earlier_ticks = sorted(sample_tick for sample_tick in history if sample_tick < tick)
    baseline_index = bisect_right(earlier_ticks, tick - 3) - 1
    if baseline_index < 0:
        baseline_index = len(earlier_ticks) - 1

    for edge in edges:
        edge_id = edge["id"]
        current = _telemetry_for_edge(history.get(tick, {}), edge_id)
        has_current_sample = bool(current)
        active_bags = max(0, int(current.get("active_bags", 0)))
        volume = max(0, int(current.get("volume", 0)))
        wear_threshold = max(1, int(edge.get("wear_threshold", 1)))

        sample_index = baseline_index
        while (sample_index >= 0 and not _telemetry_for_edge(
                history[earlier_ticks[sample_index]], edge_id)):
            sample_index -= 1
        previous = (_telemetry_for_edge(history[earlier_ticks[sample_index]], edge_id)
                    if sample_index >= 0 else {})
        previous_bags = max(0, int(previous.get("active_bags", 0))) if previous else active_bags
        previous_volume = max(0, int(previous.get("volume", 0))) if previous else volume
        elapsed_ticks = tick - earlier_ticks[sample_index] if previous else 0

        wear_score = min(100.0, volume * 100.0 / wear_threshold)
        occupancy_score = min(100.0, active_bags * 25.0)
        growth_score = min(100.0, max(0, active_bags - previous_bags) * 50.0)
        volume_delta = max(0, volume - previous_volume)
        wear_rate = volume_delta / elapsed_ticks if has_current_sample and elapsed_ticks > 0 else 0.0
        if has_current_sample and volume >= wear_threshold:
            exact_ticks_to_wear = 0.0
        elif wear_rate > 0:
            exact_ticks_to_wear = (wear_threshold - volume) / wear_rate
        else:
            exact_ticks_to_wear = None
        if exact_ticks_to_wear is None:
            wear_projection_score = 0
            estimated_ticks_to_wear = None
        else:
            estimated_ticks_to_wear = max(0, round(exact_ticks_to_wear))
            wear_projection_score = round(
                max(0.0, 100.0 * (1.0 - exact_ticks_to_wear / WEAR_FORECAST_HORIZON_TICKS))
            )
        congestion_score = max(occupancy_score, growth_score)
        risk_score = max(round(wear_score), wear_projection_score, congestion_score)
        is_jammed = current.get("status") == "JAMMED"
        edge_risks[edge_id] = {
            "score": 100 if is_jammed else risk_score,
            "priority_score": 100 if is_jammed else risk_score,
            "wear_score": round(wear_score),
            "wear_projection_score": wear_projection_score,
            "estimated_ticks_to_wear": estimated_ticks_to_wear,
            "wear_rate_per_tick": round(wear_rate, 2),
            "occupancy_score": round(occupancy_score),
            "growth_score": round(growth_score),
            "congestion_score": congestion_score,
            "active_bags": active_bags,
            "volume": volume,
            "is_jammed": is_jammed,
            "is_warning": not is_jammed and risk_score >= RISK_WARNING_THRESHOLD,
        }

    adjacent_scores = {}
    for edge in edges:
        edge_risk = edge_risks[edge["id"]]
        if edge_risk["is_jammed"]:
            continue
        score = edge_risk["score"]
        adjacent_scores.setdefault(edge["from"], []).append(score)
        adjacent_scores.setdefault(edge["to"], []).append(score)

    node_risks = {}
    for node, scores in adjacent_scores.items():
        average_score = sum(scores) / len(scores)
        node_risks[node] = round(0.6 * max(scores) + 0.4 * average_score)
    return edge_risks, node_risks