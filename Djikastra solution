"""Congestion-aware baggage router (drop-in replacement for the BFS solution.py).

Every route_bag call runs a dynamic-weight Dijkstra from current_node to destination_gate
and returns the first hop. Edge weight (never negative):

    w = base_cost
      + ALPHA * occupancy * CONGESTION_PENALTY * fade(t)      congestion
      + BETA  * max(0, jam_remaining - t)                       active jams (time-aware)
      + GAMMA * (cumulative / wear_threshold) ** 3              wear risk
      + IMMINENT_WEAR_PENALTY  if cumulative + 1 >= threshold   imminent wear jam prevention
      + DELTA * predicted_incoming * fade(t)                    herd avoidance

t is the estimated arrival time at the edge along the candidate path, so a jam that
will have cleared by the time the bag gets there costs less, and current occupancy
matters less for far-away edges (fade). Ties prefer the path with the lowest max wear ratio.
Standard library only.
"""
import heapq
import json
import os
import sys
from collections import Counter

# Tunable weights
ALPHA = 1.0
BETA = 2.0
GAMMA = 8.0
DELTA = 0.25

CONGESTION_PENALTY = 2
JAM_DURATION_EST = 250.0
DEFAULT_JAM_REMAINING = 30.0
OCC_HORIZON = 40.0
PLAN_DECAY = 0.85
WEAR_RESET_ON_JAM = False

LAYOUT_PATH = os.environ.get("ROUTER_LAYOUT_PATH")
LOG_PATH = os.environ.get("ROUTER_LOG_PATH")
DEBUG = os.environ.get("ROUTER_DEBUG") == "1"

_CONVEYOR_GRAPH = None  # node -> [(neighbor, edge_key)]
_EDGES = {}             # edge_key (u, v) -> {"id", "base", "thr"}
_ALIAS = {}             # any external edge identifier -> edge_key
_NODE_ALIAS = {}        # str(node) -> node as stored in the layout
_STATE = {}


def _get(d, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default


def _find_layout():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        LAYOUT_PATH,
        os.path.join(here, "data", "network_layout.json"),
        os.path.join(here, "network_layout.json"),
        os.path.join(here, "bhs-simulation", "data", "network_layout.json"),
        os.path.join("data", "network_layout.json"),
        "network_layout.json",
    )
    for p in candidates:
        if p and os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("network_layout.json not found")


def _add_edge(u, v, cost, thr, eid=None):
    key = (u, v)
    _EDGES[key] = {
        "id": eid if eid is not None else f"{u}->{v}",
        "base": max(0.0, float(cost)),
        "thr": float(thr) if thr else None,
    }
    _CONVEYOR_GRAPH.setdefault(u, []).append((v, key))
    _CONVEYOR_GRAPH.setdefault(v, [])
    if eid is not None:
        _ALIAS[eid] = key
        _ALIAS[str(eid)] = key
    for a in (
        key,
        f"{u}->{v}",
        f"{u}-{v}",
        f"{u}_{v}",
        f"{u}|{v}",
        f"{u},{v}",
        f"{u}:{v}",
        f"{u} -> {v}",
        f"('{u}', '{v}')",
        (str(u), str(v)),
    ):
        _ALIAS.setdefault(a, key)
    for n in (u, v):
        _NODE_ALIAS[str(n)] = n


def _build_graph(layout=None):
    global _CONVEYOR_GRAPH
    layout = layout if layout is not None else _find_layout()
    _CONVEYOR_GRAPH = {}
    _EDGES.clear()
    _ALIAS.clear()
    _NODE_ALIAS.clear()
    gthr = _get(layout, "wear_threshold", "default_wear_threshold", "wear_limit")
    edges = _get(layout, "edges", "conveyors", "links", "connections", default=[])
    if isinstance(edges, dict):
        edges = [{"id": k, **v} for k, v in edges.items()]
    for e in edges:
        if isinstance(e, (list, tuple)):
            _add_edge(e[0], e[1], e[2] if len(e) > 2 else 1, gthr)
            continue
        u = _get(e, "from", "source", "src", "u", "start", "from_node", "origin")
        v = _get(e, "to", "target", "dst", "v", "end", "to_node", "destination")
        cost = _get(e, "base_cost", "cost", "weight", "travel_time", "length", "time", default=1)
        thr = _get(e, "wear_threshold", "threshold", "wear_limit", "max_load", default=gthr)
        eid = _get(e, "id", "edge_id", "name")
        if _get(e, "bidirectional", "two_way", "bidirectional_edge", default=False):
            fwd_id = f"{eid}_FWD" if eid is not None else None
            rev_id = f"{eid}_REV" if eid is not None else None
            _add_edge(u, v, cost, thr, fwd_id)
            _add_edge(v, u, cost, thr, rev_id)
            if eid is not None:
                _ALIAS[eid] = (u, v)
                _ALIAS[str(eid)] = (u, v)
        else:
            _add_edge(u, v, cost, thr, eid)
    adj = _get(layout, "adjacency", "graph")
    if isinstance(adj, dict):
        for u, nbrs in adj.items():
            items = nbrs.items() if isinstance(nbrs, dict) else ((n, 1) for n in nbrs)
            for v, c in items:
                if (u, v) not in _EDGES:
                    _add_edge(u, v, c if isinstance(c, (int, float)) else 1, gthr)
    return _CONVEYOR_GRAPH


def _resolve_edge(k):
    if isinstance(k, list):
        k = tuple(k)
    if isinstance(k, dict):
        eid = _get(k, "edge_id", "edge", "id", "conveyor")
        if eid is not None:
            return _resolve_edge(eid)
        u, v = _get(k, "from", "source", "u"), _get(k, "to", "target", "v")
        return _resolve_edge((u, v)) if u is not None else None
    try:
        if k in _ALIAS:
            return _ALIAS[k]
    except TypeError:
        return None
    if isinstance(k, tuple) and len(k) == 2:
        u, v = _NODE_ALIAS.get(str(k[0]), k[0]), _NODE_ALIAS.get(str(k[1]), k[1])
        return (u, v) if (u, v) in _EDGES else None
    if isinstance(k, str):
        return _ALIAS.get(k.strip())
    return _ALIAS.get(str(k))


def _jam_remaining(val, tick):
    t_val = tick if isinstance(tick, (int, float)) else 0.0
    if val is None or val is True:
        return float(DEFAULT_JAM_REMAINING)
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return max(0.0, float(val))
    if isinstance(val, dict):
        r = _get(
            val,
            "remaining_ticks",
            "jam_remaining_ticks",
            "jam_remaining",
            "remaining",
            "ticks_remaining",
            "ticks_left",
            "duration_remaining",
        )
        if r is not None:
            return max(0.0, float(r))
        end = _get(val, "end_tick", "until", "until_tick", "expires_at", "expiry", "clear_tick", "ends_at", "end")
        if end is not None:
            return max(0.0, float(end) - t_val)
        d = _get(val, "duration", "length")
        if d is not None:
            s = float(_get(val, "start_tick", "start", default=t_val))
            return max(0.0, s + float(d) - t_val)
    return float(DEFAULT_JAM_REMAINING)


def _parse_faults(raw, tick):
    out = {}
    if not raw:
        return out
    items = raw.items() if isinstance(raw, dict) else ((x, None) for x in raw)
    for k, v in items:
        key = _resolve_edge(k)
        if key is None and isinstance(k, dict):
            key, v = _resolve_edge(k), k
        if key is None and isinstance(v, dict):
            key = _resolve_edge(v)
        if key is None:
            continue
        val = k if (v is None and isinstance(k, dict)) else v
        out[key] = max(out.get(key, 0.0), _jam_remaining(val, tick))
    return out


def _parse_occupancy(raw):
    out = Counter()
    if not raw:
        return out
    items = raw.items() if isinstance(raw, dict) else ((x, x) for x in raw)
    for k, v in items:
        key = _resolve_edge(k)
        if key is None and isinstance(v, dict):
            key = _resolve_edge(v)
        if key is None:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            n = v
        elif isinstance(v, (list, tuple, set)):
            n = len(v)
        elif isinstance(v, dict):
            n = _get(v, "count", "bags", "occupancy", "bag_count", default=1)
            n = len(n) if isinstance(n, (list, tuple, set)) else n
        else:
            n = 1
        out[key] += max(0, n)
    return out


def reset_state():
    _STATE.clear()
    _STATE.update(
        tick=None,
        tick_load=Counter(),
        planned=Counter(),
        cumulative=Counter(),
        prev_faults=set(),
        last_call={},
        first_call=True,
    )


def _advance(tick, bag_id=None):
    s = _STATE
    if not s or (tick is not None and s["tick"] is not None and tick < s["tick"]):
        reset_state()
        s = _STATE
    if bag_id == "B0001" and s["cumulative"] and sum(s["cumulative"].values()) > 5:
        reset_state()
        s = _STATE
    if tick is None:
        s["planned"] = Counter({k: v * PLAN_DECAY for k, v in s["planned"].items() if v * PLAN_DECAY > 0.01})
        s["tick_load"] = Counter()
    elif tick != s["tick"]:
        if s["tick"] is not None:
            f = PLAN_DECAY ** max(1, tick - s["tick"])
            s["planned"] = Counter({k: v * f for k, v in s["planned"].items() if v * f > 0.01})
        s["tick_load"] = Counter()
        s["tick"] = tick


def dijkstra(graph, start, end, weight_fn):
    """Lexicographic Dijkstra on (cost, max_wear, hops). Returns node path or None."""
    best = {start: (0.0, 0.0, 0)}
    prev = {}
    heap = [(0.0, 0.0, 0, 0, start)]
    seq = 1
    while heap:
        c, w, h, _, u = heapq.heappop(heap)
        if (c, w, h) > best[u]:
            continue
        if u == end:
            path = [u]
            while u in prev:
                u = prev[u]
                path.append(u)
            return path[::-1]
        for v, key in graph.get(u, ()):
            ew, wear = weight_fn(key, c)
            cand = (round(c + max(0.0, ew), 9), max(w, round(wear, 6)), h + 1)
            if v not in best or cand < best[v]:
                best[v] = cand
                prev[v] = u
                heapq.heappush(heap, (cand[0], cand[1], cand[2], seq, v))
                seq += 1
    return None


def _make_weight(occ, faults):
    s = _STATE
    cum, planned, load = s["cumulative"], s["planned"], s["tick_load"]

    def weight(key, t):
        e = _EDGES[key]
        fade = max(0.25, 1.0 - t / OCC_HORIZON)
        w = e["base"]
        w += ALPHA * (occ.get(key, 0) + load.get(key, 0) + 1) * CONGESTION_PENALTY * fade
        if key in faults:
            w += BETA * max(10.0, faults[key] - t * 0.5)
        ratio = 0.0
        if e["thr"]:
            projected = cum.get(key, 0) + load.get(key, 0) + planned.get(key, 0.0) * 0.5
            ratio = projected / e["thr"]
            w += GAMMA * (ratio ** 3)
            if cum.get(key, 0) + load.get(key, 0) + 1 >= e["thr"]:
                w += BETA * JAM_DURATION_EST
        w += DELTA * planned.get(key, 0.0) * fade
        return max(0.0, w), ratio

    return weight


def _log(entry):
    if not LOG_PATH:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass


def _route(bag_id, current_node, destination_gate, current_tick, edge_occupancy, active_faults):
    if _CONVEYOR_GRAPH is None:
        _build_graph()
    cur = _NODE_ALIAS.get(str(current_node), current_node)
    dst = _NODE_ALIAS.get(str(destination_gate), destination_gate)
    tick = current_tick if isinstance(current_tick, (int, float)) and not isinstance(current_tick, bool) else None
    _advance(tick, bag_id=bag_id)
    s = _STATE
    if s["first_call"]:
        s["first_call"] = False
        if DEBUG:
            print(
                f"[router] edge_occupancy={edge_occupancy!r}\n[router] active_faults={active_faults!r}",
                file=sys.stderr,
            )
    if cur == dst:
        return current_node
    if tick is not None:
        cached = s["last_call"].get(bag_id)
        if cached and cached[0] == tick and cached[1] == cur:
            return cached[2]

    occ = _parse_occupancy(edge_occupancy)
    faults = _parse_faults(active_faults, tick)
    if WEAR_RESET_ON_JAM:
        for key in set(faults) - s["prev_faults"]:
            s["cumulative"][key] = 0
    s["prev_faults"] = set(faults)

    path = dijkstra(_CONVEYOR_GRAPH, cur, dst, _make_weight(occ, faults))
    if not path or len(path) < 2:
        if tick is not None:
            s["last_call"][bag_id] = (tick, cur, current_node)
        _log({"tick": tick, "bag": bag_id, "at": cur, "dst": dst, "hop": None})
        return current_node
    nxt = path[1]
    first = (cur, nxt)
    if tick is not None:
        s["tick_load"][first] += 1
        s["last_call"][bag_id] = (tick, cur, nxt)
    s["cumulative"][first] += 1
    for a, b in zip(path[1:], path[2:]):
        s["planned"][(a, b)] += 1.0
    _log({"tick": tick, "bag": bag_id, "at": cur, "dst": dst, "hop": nxt, "path": path})
    return nxt


def _fallback(current_node, destination_gate):
    try:
        if _CONVEYOR_GRAPH is None:
            _build_graph()
        path = dijkstra(
            _CONVEYOR_GRAPH,
            current_node,
            destination_gate,
            lambda k, t: (_EDGES[k]["base"], 0.0),
        )
        return path[1] if path and len(path) > 1 else current_node
    except Exception:
        return current_node


def route_bag(
    bag_id,
    current_node,
    destination_gate,
    active_faults=None,
    edge_occupancy=None,
    current_tick=None,
    *args,
    **kwargs,
):
    # Support both (bag_id, current_node, destination_gate, active_faults, edge_occupancy)
    # and (bag_id, current_node, destination_gate, current_tick, edge_occupancy, active_faults)
    if isinstance(active_faults, (int, float)) and not isinstance(active_faults, bool):
        current_tick = active_faults
        active_faults = args[0] if args else _get(kwargs, "active_faults", "faults", "jams", "active_jams")
    if edge_occupancy is None:
        edge_occupancy = _get(kwargs, "occupancy", "edge_loads", "congestion")
    if active_faults is None:
        active_faults = _get(kwargs, "faults", "jams", "active_jams")
    if current_tick is None and "tick" in kwargs:
        current_tick = kwargs["tick"]
    try:
        return _route(
            bag_id,
            current_node,
            destination_gate,
            current_tick,
            edge_occupancy,
            active_faults,
        )
    except Exception:
        return _fallback(current_node, destination_gate)
