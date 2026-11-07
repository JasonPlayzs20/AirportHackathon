import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def generate_3600_tick_scenario():
    # Set seed for reproducible randomness across student evaluations
    random.seed(67)

    # Valid node IDs directly derived from network_layout.json
    intake_nodes = ["IA1", "IA2", "IB1", "IB2"]
    a_gates = ["GA1", "GA2", "GA3", "GA4"]
    b_gates = ["GB1", "GB2", "GB3", "GB4"]
    all_gates = a_gates + b_gates

    # Pools of valid edge IDs from network_layout.json to target for disruptions
    spine_trunks = ["e_S1_S2", "e_S2_S3", "e_S3_S4", "e_S4_S5"]
    detour_lanes = ["e_S1_S6", "e_S6_S5"]
    terminal_a_exits = ["e_JA1_S1", "e_JA2_S2", "e_JA3_S3", "e_JA5_S2"]
    terminal_b_exits = ["e_JB1_S4", "e_JB2_S4", "e_JB3_S5", "e_JB5_S4"]

    bags = []
    jams = []
    bag_counter = 1
    jam_counter = 1

    # =========================================================================
    # 1. PROCEDURAL BAGGAGE INFLOW GENERATOR
    # =========================================================================
    def spawn_wave(start_tick, end_tick, density_probability, strict_deadlines=False):
        nonlocal bag_counter
        for t in range(start_tick, end_tick + 1):
            if random.random() < density_probability:
                intake = random.choice(intake_nodes)
                if "A" in intake:
                    dest = random.choice(a_gates if random.random() < 0.8 else b_gates)
                else:
                    dest = random.choice(b_gates if random.random() < 0.8 else a_gates)

                bag_obj = {
                    "bag_id": f"B{bag_counter:04d}",
                    "intake_node": intake,
                    "destination_gate": dest,
                    "release_tick": t
                }

                if strict_deadlines or random.random() < 0.4:
                    window_size = random.randint(25, 35) if strict_deadlines else random.randint(45, 65)
                    bag_obj["deadline_tick"] = t + window_size

                bags.append(bag_obj)
                bag_counter += 1

    # Generate multi-phase baggage surges
    spawn_wave(1, 300, density_probability=0.05)       # Warm Up
    spawn_wave(301, 900, density_probability=0.15)     # First Pressure
    spawn_wave(901, 2100, density_probability=0.22)    # Sustained Load
    spawn_wave(2101, 3000, density_probability=0.38, strict_deadlines=True) # Crisis Peak
    spawn_wave(3001, 3300, density_probability=0.08)    # Wind Down

    # =========================================================================
    # 2. AUTOMATED STRATEGIC DISRUPTION GENERATOR (12-15 Jams)
    # =========================================================================
    def add_jam(edge_id, start_tick, duration, note):
        nonlocal jam_counter
        jams.append({
            "jam_id": f"J{jam_counter:03d}",
            "edge_id": edge_id,
            "start_tick": start_tick,
            "duration": duration,
            "note": note
        })
        jam_counter += 1

    # --- Archetype A: Concurrent Bottlenecks (Forces Cross-Terminal Bridge Usage) ---
    # Triggered during early Sustained Load to bottleneck both main spine feeders at once
    add_jam("e_JA2_S2", 1050, 80, "Concurrent Bottleneck A: Localizes Terminal A traffic.")
    add_jam("e_JB2_S4", 1050, 80, "Concurrent Bottleneck B: Localizes Terminal B traffic simultaneously.")

    # --- Archetype B: Cascading Traps (Tests Deep Real-time Rerouting Loops) ---
    # Trap 1: Sustained Load Phase
    add_jam("e_S2_S3", 1500, 100, "Cascading Trap 1A: Jams main spine backbone highway.")
    add_jam("e_S1_S6", 1520, 60,  "Cascading Trap 1B: Jams parallel detour 20 ticks later, catching rerouted bags.")
    
    # Trap 2: Extreme Crisis Peak Phase
    add_jam("e_S3_S4", 2500, 120, "Cascading Trap 2A: Massive trunk link failure inside maximum rush bank.")
    add_jam("e_S6_S5", 2515, 80,  "Cascading Trap 2B: Detour cutoff 15 ticks later to punish non-reactive pathfinding.")

    # --- Archetype C: High-Frequency Micro-Jams (Tests Dashboard/DHS Polling and UI Flicker) ---
    # Flickers an exit point rapidly to see if student frontends lag or logging pipelines saturate
    flicker_edge = "e_JA3_S3"
    flicker_start = 1800
    for i in range(4): # 4 back-to-back mini cycles
        add_jam(flicker_edge, flicker_start + (i * 45), 15, f"Micro-Jam Flicker Cycle {i+1}/4.")

    # --- Archetype D: The Wind-Down Blockade (Forces Load Balancing Evaluation) ---
    # Breaks a delivery channel when system is trying to flush out existing inventory
    add_jam("e_S4_S5", 3150, 150, "Wind-Down Blockade: Long duration trunk choke to accumulate end-game queues.")

    # --- Archetype E: Random Operational Friction (Padding Count to 14 Total Jams) ---
    add_jam(random.choice(terminal_a_exits), 450,  40, "Random Friction: Minor early morning structural delay.")
    add_jam(random.choice(terminal_b_exits), 2250, 50, "Random Friction: Mid-day sorting congestion failure.")

    # Sort jams chronologically by their activation tick to look polished
    jams.sort(key=lambda j: j["start_tick"])

    # =========================================================================
    # 3. BUILD UNIFIED JSON CONFIGURATION FILE
    # =========================================================================
    scenario_json = {
        "simulation": {
            "total_ticks": 3600,
            "description": "Airport BHS 1-Hour Operational Stress Scenario. 3,600 ticks with procedurally generated waves and automated strategic failures."
        },
        "phases": [
            { "name": "warm_up",        "start_tick": 1,    "end_tick": 300  },
            { "name": "first_pressure", "start_tick": 301,  "end_tick": 900  },
            { "name": "sustained_load", "start_tick": 901,  "end_tick": 2100 },
            { "name": "crisis_peak",    "start_tick": 2101, "end_tick": 3000 },
            { "name": "wind_down",      "start_tick": 3001, "end_tick": 3600 }
        ],
        "bags": bags,
        "jams": jams,
        "notes": {
            "generated_bag_count": len(bags),
            "automated_jam_count": len(jams),
            "design": "Procedurally optimized for Brock Solutions SmartSort challenge tracks to thoroughly separate basic static graph solvers from highly optimized dynamic systems engineering solutions."
        }
    }

    output_path = BASE_DIR / "data" / "simulation_scenario.json"
    with open(output_path, "w") as f:
        json.dump(scenario_json, f, indent=2)

    print(f"Success! Scaled scenario written to '{output_path}'.")
    print(f" -> Generated Bags: {len(bags)}")
    print(f" -> Automated Jams: {len(jams)} strategic failure blocks injected.")

if __name__ == "__main__":
    generate_3600_tick_scenario()