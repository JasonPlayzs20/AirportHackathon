# -*- coding: utf-8 -*-
import cv2
import json
from pyzbar.pyzbar import decode
from typing import Optional

import paho.mqtt.client as mqtt

VALID_GATES = {"GA1", "GA2", "GA3", "GA4", "GB1", "GB2", "GB3", "GB4"}

# Master list mapping barcodes to conveyor assignments.
# Includes the 10 real barcodes plus decoys to add search complexity.
MASTER_LIST = {
    # Real barcodes
    "JD|23.4|RED|GA2": "conveyor_1",
    "ML|15.0|BLU|GB3": "conveyor_2",
    "AK|31.2|BLK|GA1": "conveyor_1",
    "SP|09.8|GRN|GB4": "conveyor_3",
    "TR|18.5|YLW|GA3": "conveyor_2",
    "BW|27.1|GRY|GB1": "conveyor_1",
    "CN|12.3|ORG|GA4": "conveyor_3",
    "EV|20.0|PRP|GB2": "conveyor_2",
    "RH|08.6|RED|GA1": "conveyor_3",
    "FM|33.9|BLU|GB3": "conveyor_1",
    # Decoys
    "AA|10.0|RED|GA1": "conveyor_1",
    "BB|20.0|BLU|GA2": "conveyor_2",
    "CC|30.0|BLK|GA3": "conveyor_3",
    "DD|11.5|GRN|GB1": "conveyor_1",
    "EE|22.3|YLW|GB2": "conveyor_2",
    "FF|14.7|GRY|GA4": "conveyor_3",
    "GG|09.1|ORG|GB3": "conveyor_1",
    "HH|33.0|PRP|GA1": "conveyor_2",
    "II|17.6|RED|GB4": "conveyor_3",
    "JJ|25.4|BLU|GA2": "conveyor_1",
    "KK|08.2|BLK|GB1": "conveyor_2",
    "LL|19.9|GRN|GA3": "conveyor_3",
    "MM|12.8|YLW|GB2": "conveyor_1",
    "NN|28.5|GRY|GA4": "conveyor_2",
    "OO|16.3|ORG|GB3": "conveyor_3",
    "PP|21.7|PRP|GA1": "conveyor_1",
    "QQ|13.4|RED|GB4": "conveyor_2",
    "RR|31.0|BLU|GA2": "conveyor_3",
    "SS|07.5|BLK|GB1": "conveyor_1",
    "TT|24.6|GRN|GA3": "conveyor_2",
}

PICKLIST = [
    "JD|23.4|RED|GA2",
    "ML|15.0|BLU|GB3",
    "AK|31.2|BLK|GA1",
    "SP|09.8|GRN|GB4",
    "TR|18.5|YLW|GA3",
    "BW|27.1|GRY|GB1",
    "CN|12.3|ORG|GA4",
    "EV|20.0|PRP|GB2",
    "RH|08.6|RED|GA1",
    "FM|33.9|BLU|GB3",
]

def parse_barcode(data: str) -> Optional[dict]:
    """
    Parse a pipe-delimited baggage barcode string.

    Expected format: <INITIALS>|<WEIGHT_KG>|<COLOR>|<GATE>
    Example:         JD|23.4|RED|GA2

    Returns a dict with keys: initials, weight_kg, color, gate
    Returns None if the barcode is invalid / not a baggage barcode.
    """
    parts = data.strip().split("|")

    if len(parts) != 4:
        return None  # Not a baggage barcode - ignore silently

    initials, weight_str, color, gate = parts

    # Validate initials (2-3 uppercase letters)
    if not (2 <= len(initials) <= 3 and initials.isalpha() and initials.isupper()):
        print(f"  [WARN] Invalid initials: '{initials}'")
        return None

    # Validate weight (must be exactly 4 chars: XX.X, e.g. '23.4')
    if len(weight_str) != 4:
        print(f"  [WARN] Invalid weight length: '{weight_str}' (expected 4 chars, e.g. '23.4')")
        return None
    try:
        weight_kg = float(weight_str)
        if weight_kg <= 0:
            raise ValueError
    except ValueError:
        print(f"  [WARN] Invalid weight: '{weight_str}'")
        return None

    # Validate color (must be exactly 3 uppercase letters, e.g. 'RED', 'BLU')
    if len(color) != 3 or not (color.isalpha() and color.isupper()):
        print(f"  [WARN] Invalid color: '{color}' (expected 3-letter code, e.g. 'RED', 'BLU')")
        return None

    # Validate gate
    if gate not in VALID_GATES:
        print(f"  [WARN] Invalid gate: '{gate}' (must be one of {sorted(VALID_GATES)})")
        return None

    return {
        "initials":  initials,
        "weight_kg": weight_kg,
        "color":     color,
        "gate":      gate,
    }


if __name__ == "__main__":
    cap    = None
    client = None

    try:
        # -- Camera ------------------------------------------------------------
        print("Initializing camera...")
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)  # Change index if needed
        if not cap.isOpened():
            print("Camera failed to open.")
            exit(1)

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Flush stale frames from buffer
        for _ in range(5):
            cap.read()

        print("Camera initialized successfully.")

        # -- MQTT --------------------------------------------------------------
        broker = "129.97.228.106"
        print(f"Connecting to MQTT broker at {broker}...")
        client = mqtt.Client(client_id="InputOutputScript")

        mqtt_connected = False
        try:
            client.connect(broker, keepalive=60)
            client.loop_start()
            mqtt_connected = True
            print("Connected to MQTT broker.")
        except Exception as e:
            print(f"WARNING: MQTT connection failed: {e}")
            print("Continuing without MQTT...")
            client = None  # Prevent accidental use below

        # Publish initial picklist only if MQTT is up
        if mqtt_connected and client:
            client.publish(
                "Conveyor3/air_picklist",
                json.dumps(PICKLIST),
                qos=1,
                retain=True,
            )
            print("Published air picklist.")

        # -- Main loop ---------------------------------------------------------
        print("Starting camera loop (press ESC to quit)...")
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Camera read failed.")
                break

            for barcode in decode(frame):
                raw_data = barcode.data.decode("utf-8")
                print(f"\nDetected barcode: {raw_data}")

                bag = parse_barcode(raw_data)

                conveyor = MASTER_LIST.get(raw_data, "unassigned")
                in_picklist = raw_data in PICKLIST

                if bag:
                    print(
                        f"  Passenger : {bag['initials']}\n"
                        f"  Weight    : {bag['weight_kg']} kg\n"
                        f"  Color     : {bag['color']}\n"
                        f"  Gate      : {bag['gate']}\n"
                        f"  Conveyor  : {conveyor}\n"
                        f"  In picklist: {in_picklist}"
                    )
                else:
                    print("  Could not parse as baggage barcode - skipping.")

                if client:
                    # Publish raw string (low-latency, qos=0)
                    client.publish("Conveyor3/barcode_value", raw_data, qos=0)

                    # Publish routing info for Node-RED
                    routing = {
                        "barcode":     raw_data,
                        "in_picklist": in_picklist,
                        "conveyor":    conveyor,
                    }
                    client.publish(
                        "Conveyor3/baggage_routing",
                        json.dumps(routing),
                        qos=1,
                    )

            cv2.imshow("Camera", frame)
            if cv2.waitKey(1) == 27:  # ESC
                break

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nCleaning up...")
        if cap:
            cap.release()
        cv2.destroyAllWindows()
        if client:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass
        print("Done.")