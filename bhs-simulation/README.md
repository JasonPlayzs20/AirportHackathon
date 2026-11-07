# SmartSort Conveyor Simulation

## Introduction

This toolkit models an airport baggage handling system (BHS) controlled by a High-Level Control (HLC) framework. The environment presents a realistic sandbox for testing how software reacts to fluid physical constraints: unexpected hardware breakdowns, compounding traffic density delays, and strict delivery windows.

You can use these utilities to explore backend algorithmic optimization, engineer advanced predictive metrics, or completely overhaul the operator dashboard.

---

## System Architecture and Geography

The simulated airport infrastructure is represented as a directed network graph configured within [`data/network_layout.json`](data/network_layout.json).

### Graph Topology Configuration

The topology consists of **28 unique nodes** interconnected by directed conveyor track edges:

* **Intake Ports (`IA1`, `IA2`, `IB1`, `IB2`)**: Entry nodes where baggage items are scheduled to spawn and feed into the sorting network.
* **Junctions (`JA1` through `JA5`, `JB1` through `JB5`)**: Active split-points and intersections where routing choices must be evaluated.
* **Spines (`S1` through `S6`)**: High-speed, high-capacity central transport corridors running between major terminal zones.
* **Gates (`GA1` through `GA4`, `GB1` through `GB4`)**: Terminal delivery sinks. These represent the final flight docking points and act as exit boundaries with no outgoing paths.

### Conveyor Line Edge Mechanics

* **Directed Flow**: Every line edge represents a conveyor track moving in a single direction from a source node (`from`) to a target node (`to`).
* **Base Travel Cost**: Each track carries a fixed baseline physical traversal length measured in simulation ticks.
* **Parallel Bidirectional Corridors**: High-speed corridors flagged with `"bidirectional": true` are automatically split by the simulation engine at runtime into two distinct, parallel tracks running in opposite directions (suffixed with `_FWD` and `_REV`). Each lane operates as a completely independent physical resource with its own separate volume tracking, congestion state, and localized breakdown variables.

---

## Simulation Dynamics and Physics

The environment runs using a **Discrete Time-Step (Tick-Based) Simulation Loop**. One simulation tick corresponds to one second of real-world operational time. Your solution does not run the primary execution loop; the master engine updates the system state and queries your routing hooks at intersection intervals.

### Dynamic Traffic Congestion

Conveyor speeds vary based on active track volume. The total time required for a bag to traverse a specific track scales dynamically based on the current bag density. The effective travel cost formula is computed as:

$$\text{Effective Cost (Ticks)} = \text{Base Cost} + (\text{Active Bags Occupying Track} \times 2)$$

As a track crowds, its latency spikes. A physically direct path may become slower than a clear outer detour route under heavy loads.

### Environmental Fault Events (Jams)

Conveyor belts can experience unexpected mechanical or electrical failures, entering a `JAMMED` state.

* **Mid-Transit Freezing**: If a track experiences a jam while a bag is traversing it, the conveyor halts and the bag's remaining travel countdown freezes.
* **Junction Trapping**: If your routing system assigns a bag to a line that is already jammed, the bag is successfully transferred onto the belt but freezes at the entrance. It cannot be rerouted or updated until the line returns to an `OPERATIONAL` status and the bag reaches the next consecutive junction node.

### Mechanical Wear-and-Tear Degradation

Conveyor motors degrade based on cumulative usage metrics. Each line carries a strict `wear_threshold` value inside `data/network_layout.json`. If the cumulative count of bags processed by a specific track crosses this usage threshold, the line triggers an automated **Mechanical Overload**, inducing an unannounced, 20-tick operational breakdown lock.

---

## The 1-Hour Operational Scenario

The evaluation framework executes against a 1-hour stress profile outlined in `data/simulation_scenario.json`. The scenario tracks **705 bags** injected across a **3,600-tick timeline** divided into five distinct operational phases:

1. **Warm Up (`Ticks 1–300`)**: Low-density traffic baseline to initialize system flows.
2. **First Pressure (`Ticks 301–900`)**: Ramping inflow volumes testing early distribution lanes.
3. **Sustained Load (`Ticks 901–2100`)**: High-density steady-state flow causing continuous track accumulation and triggering targeted structural spine maintenance blockades.
4. **Crisis Peak (`Ticks 2101–3000`)**: Maximum congestion surge modeling a multi-flight check-in bank. Bags during this phase are carrying strict `deadline_tick` constraints.
5. **Wind Down (`Ticks 3001–3600`)**: Intake ports stop spawning new inventory by tick 3,300, providing a 300-tick window for the conveyor grid to flush out its remaining assets.

---

## Programmatic API Integration

If you choose to work on the sorting logic, the evaluation engine (`evaluator.py`) looks for a file named `solution.py` inside the same directory. This script must expose the exact Sort Allocation Controller (SAC) function interface defined below.

### The Routing Hook Function Signature

```python
def route_bag(bag_id, current_node, destination_gate, active_faults, edge_occupancy):
    """
    Evaluates real-time routing choices for a bag arriving at an intersection.
    
    Parameters:
    -----------
    bag_id : str
        The unique identification string of the baggage item (e.g., 'B0024')
    current_node : str
        The ID of the junction node the bag has physically reached (e.g., 'JA3')
    destination_gate : str
        The final destination gate where the bag must be delivered (e.g., 'GA2')
    active_faults : list of str
        A list of specific edge IDs currently experiencing active jams (e.g., ['e_JA2_S2'])
    edge_occupancy : dict
        A key-value map linking edge IDs to integers representing the exact count 
        of active bags currently traversing that conveyor line.
        
    Returns:
    --------
    str
        The node ID of the next adjacent junction or gate to guide the bag toward.
    """
    # Custom optimization, pathfinding, or routing logic here
    return "JA4"

```

A sample solution has been provided with a basic BFS implementation. This algorithm is highly unoptimized but can still route all bags (though not all on time). You can improve the algorithm within the route_bag function to increase the efficiency of the system.

### Safety and Exception Rules

The simulator enforces strict system rules. Triggering any of the following boundary conditions results in a **Hard Failure** and immediate simulation termination:

* **Invalid Pathing Steps**: Returning a destination node that is not connected to the bag's current location by a valid directed conveyor track.
* **Uncaught Exceptions**: Allowing your routing logic to crash when encountering an unannounced mechanical wear-and-tear jam.
* **Illegal Node Teleportation**: Attempting to skip intermediary tracks or bypass travel cost increments.

---

## Running the Sandbox Tools

### 1. Running the Simulation Loop

To run the evaluation cycle, execute the master engine script. By default, it imports your `solution.py` module and processes the scenario. From the bhs-simulation folder, simply run the script:

```bash
python evaluator.py
```

Upon completion, the engine prints a performance summary tracking two primary quantitative metrics:

* **Total Misrouted Bags**: The count of bags that breached their strict `deadline_tick` arrival window, plus any assets left stranded on the belts at tick 3,600. (*Lower is better*).
* **Mean Transit Latency**: The average number of ticks required for successfully delivered bags to navigate from intake to gate. (*Lower is better*).

### 2. Launching the Playback Dashboard (BSD)

Every simulation run automatically generates a high-frequency event file named `live_telemetry.csv`. To visually analyze how your routing choices behaved, launch the pre-built **Bag Status Display (BSD)** playback utility:

```bash
python bsd_dashboard.py
```

![alt text](/baggage-handling-system/assets/BSD.png)

* **Interactive Scrubbing**: Use the horizontal timeline slider to instantly seek to any specific snapshot across the 3,600 ticks to isolate and inspect bottleneck points.
* **Visual Status Legend**:
    * **Charcoal Grey Tracks**: Idle, empty conveyor lines.
    * **Safety Orange Tracks**: Active lines with moving baggage streams.
    * **Solid Crimson Red Tracks**: Broken conveyor segments currently experiencing active jams.

The current BSD is a very surface level implementation that can be improved extensively to have better UI/UX. This is an area your team can focus on improving.