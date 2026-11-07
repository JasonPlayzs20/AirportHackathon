# Physical Vision-Guided Conveyor Tutorial

## Introduction

If your team wants to work with physical hardware, edge computing, computer vision, and industrial IoT communication loops, this folder provides a hands-on sandbox using a **Physical Sorting Testbed**.

The setup models a real-world inspection, tracking, and diverter station. It combines an edge-computing processor running computer vision with a Programmable Logic Controller (PLC) that manages motor outputs and mechanical actuators.

This tutorial walks through the basic steps to initialize, wire, and execute a complete hardware-software tracking loop. Once the baseline architecture is running, you have the freedom to modify the vision models, alter the IoT data flows, build graphical operator dashboards, pioneer a completely unique automated sorting process, or do whatever you want to expand on this solution.

---

## The Physical & Network Infrastructure

The physical sorting workstation consists of three primary components:

1. **The Transport Layer**: A physical conveyor belt powered by an industrial motor, paired with a downstream mechanical diverter arm.
2. **The Sensor Layer**: A camera mounted directly above the track to inspect passing cargo items.
3. **The Control Brains**: An NVIDIA Jetson Nano handling the computer vision, connected via the network to an Opto22 Groov RIO PLC that commands the physical sorting hardware.

![Physical Conveyor Testbed Layout](/baggage-handling-system/assets/conveyor.jpg)
*Figure 1: This is what the conveyor setup should look like when you arrive at it.*

### Network Architecture and MQTT Broker Specs

To bridge these platforms without complex point-to-point wiring, the system utilizes a centralized MQTT messaging architecture. Both the Jetson Nano and the PLC connect to a shared network server acting as an MQTT message broker:

* **MQTT Broker IP Address**: `129.97.228.106`
* **Broker Port**: `1883`

The vision script publishes real-time tracking data across two topics (channels):

* `Conveyor3/barcode_value`: Transmits the raw barcode text string instantly upon camera discovery (QoS 0).
* `Conveyor3/baggage_routing`: Transmits an structured JSON tracking payload containing parsed object metadata and picklist validation states (QoS 1).

---

## Step 1: Setting up the Edge Vision Sensor (Jetson Nano)

The Jetson Nano is responsible for capturing the camera feed, identifying barcodes, parsing structural string values into structured objects, and publishing tracking payloads to the network.

### 1. Environment and Dependencies Installation

Because the Jetson Nano operates within an isolated engineering lab network without active internet connectivity, all mandatory system utilities, hardware drivers, and software libraries have been pre-installed. Before initializing your tracking loops, open a local terminal window on the Jetson Nano desktop (should be in the middle of the desktop home screen) and execute the following diagnostic command to verify that your execution environment is fully prepared:

```bash
python3 -c "import cv2, pyzbar, paho.mqtt; print('\n[SYSTEM OK] Core tracking dependencies (OpenCV, PyZbar, Paho-MQTT) are successfully verified and active!')"

```

If your environment is intact, the terminal will print the green-light `[SYSTEM OK]` status confirmation message. You are completely ready to proceed. If the terminal returns an ImportError, inform a teaching assistant or lab instructor to fix the issue.

![NVIDIA Jetson Nano Edge Developer Kit](/baggage-handling-system/assets/jetson.jpg)
*Figure 2: The NVIDIA Jetson Nano device, responsible for vision and MQTT publishing.*

### 2. Exploring the Baseline Script (`barcode_scanner.py`)

A baseline computer vision tracking script is provided in this folder. The script initializes the camera loop, decodes barcodes via the `pyzbar` engine, checks values against a master picklist, and structures the data.

When a bag passes under the lens, the camera captures a string sequence formatted as follows:

`"Initials | Bag Weight | Tracking Color | Target Flight Gate"` (e.g., `"JD|23.4|RED|GA2"`).

The script tokenizes this raw string and maps it into a structured payload dictionary:

```json
{
  "barcode": "JD|23.4|RED|GA2",
  "in_picklist": true,
  "conveyor": "conveyor_1"
}

```

![Overhead Camera Sensor Array](/baggage-handling-system/assets/camera.jpg)
*Figure 3: The camera that will be facing down at the conveyor belt.*

### 3. Launching the Vision Loop

To execute the vision script, run the following code:

```bash
cd /home/ideasclinic/
python barcode_scanner.py

```

A live camera view will open on the window. Hold a valid tracking barcode up to the camera lens to observe the real-time parsing logs in your terminal output and verify that data packets are successfully streaming out to the network broker. If available, you may use the bags provided for the securebag solution and put a barcode on them to simulate a real bag passing through the conveyor. 

---

## Step 2: Accessing the Industrial PLC (Node-RED)

The physical conveyor loop and mechanical diverter outputs are managed by an Opto22 Groov RIO PLC. This device hosts a browser-based **Node-RED Editor**, allowing you to create automation flows using visual nodes.

### 1. Accessing the PLC Web Interface

Open a web browser on a laptop connected to the eduroam and navigate to the following URL (make sure you are on eduroam wifi):

* **PLC Editor Portal**: `https://ideasplc3.uwaterloo.ca/manage/home`

*Note: If your browser displays a "Your connection is not private" security warning page, click **Advanced** and select **Proceed to...***

### 2. Authentication Login

When the login console appears, input the following credentials:

* **Username**: `ideasclinic`
* **Password**: `plc123`

### 3. Launching the Node-RED Editor

From the primary landing homepage dashboard, click on the **Node-RED** button. Inside it, click the **Open Node-RED Editor** link option. This should load your team's visual canvas environment, featuring a palette of hardware and logic nodes along the left side menu bar.

*Note: You may need to verify that you are in the correct flow. The top banner over the flow grid should show which flow you are in. The correct flow for this sub problem is the **Barcode Scanner** flow. If you are in another flow, switch to that flow. If there are additional or other issues, please ask the teaching team for assistance.*

---

## Step 3: Implementing the Sorting & Safe-State Logic

To make the physical testbed work as an automated sorting system, you must configure a flow in Node-RED that subscribes to the Jetson Nano's telemetry and fires physical outputs based on operational rules.

### The Core Concept: The Active Conveyor State

Because this testbed is a single physical loop, we use a global variable inside Node-RED called the **Active Conveyor** state. This variable acts as a "virtual downstream gate assignment" filter (e.g., configuring the system to actively sort items bound for `conveyor_3`). 

### Boolean Logic Sorting Rules

Your control logic must listen to incoming JSON payloads on `Conveyor3/baggage_routing` and execute the following conditional rules precisely to safeguard the physical equipment:

1. **Condition A: Route Allowed (Successful Sort)**
* *Criteria:* The scanned barcode string is recognized as valid (`"in_picklist": true`) **AND** its mapped conveyor value matches the current `Active Conveyor` state variable in Node-RED. 
* *Action:* Keep the conveyor motor running, engage the mechanical downstream diverter arm to capture the item, and track the successful sort event. You can implement specific patterns for diverters to simulate destination conveyors. 


2. **Condition B: Misrouted Asset or Invalid Code (Emergency Safety Halt)**
* *Criteria:* The barcode string is unrecognized (`"in_picklist": false`) **OR** the item's target conveyor route differs from the current `Active Conveyor` layout state filter.
* *Action:* Trigger an automated **Auto-Kill Safe State Interlock**. The conveyor belt motor must be **halted instantly**, stopping the track to prevent an asset from being incorrectly routed into the wrong collection zone.



### Basic Flow Structure

The Barcode Scanner flow should already have a basic flow configuration that can successfully meet all conditions. You may create your custom flow based on this flow or you can build an entirely different flow that meets the requirements (and potentially may be more effective). The following provides a starting point for how to set up the flow. You may also check **Node-Red Guide.docx** in this folder for more detailed information:

1. **An MQTT Input Node**: Double-click it to modify its settings. Set the server property to `129.97.228.106:1883` and set the target subscription topic to `Conveyor3/baggage_routing`.
2. **A JSON Parser Node**: Connect the output of the MQTT node into a standard `json` node to automatically convert the incoming string packet back into an accessible JavaScript object.
3. **A Function Node**: Write a clean JavaScript block to evaluate the parsed properties against your `Active Conveyor` context filter and output appropriate boolean signals to your physical PLC output channels (`groov i/o write`).
4. **Deploying the Changes**: Click the bright red **Deploy** button at the top-right of your screen to compile and flash your logic changes live onto the physical hardware controller.

*Note: Any changes you make to the original flow should be done in a new flow so that the original flow remains unchanged. Do this by pressing the plus symbol next to the flows and copy pasting the original flow as needed. Before running your modified flow, remember the diable the original flow. If you accidentally change the original flow, use the [`flows.json`](flows.json) file to import it back.*

---

## Avenues for Innovation/Extension

Once your baseline setup is running and passing test barcodes successfully, your project will be evaluated based on how creatively and robustly your team scales this architecture. Consider the following engineering exploration routes:

* **Dynamic Manifest Systems**: Instead of relying on a static, hardcoded dictionary of 10 barcodes hidden deep inside the local Python file, can you adapt the script to pull tracking definitions from a remote database, web API, or sync live manifests directly from a custom node network?
* **Edge UI Camera Overlays**: Modify the OpenCV frame capture threads inside `barcode_scanner.py`. Use polygon line rendering to draw colored, floating tracking bounding boxes around barcodes as they are scanned, printing the passenger initials and weights directly onto the visual screen matrix.
* **IoT Efficiency Dashboards**: Leverage Node-RED’s dashboard node palettes to design a comprehensive user interface. Create live chart panels to record system health variables over time, graphing metrics like total cargo counts, scanner read rates, or tracking diverter mechanical latency under various transport speeds.