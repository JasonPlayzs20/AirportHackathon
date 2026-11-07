# Baggage Handling System Subproblem
## Table of Contents

- [The Problem](#the-problem)
- [The Challenge](#the-challenge)
- [Potential Solutions](#potential-solutions)
- [Resources](#resources)

## The Problem

To get from check-in to airplane, baggage travels over a large system of conveyors. The bags are taken through hold baggage screening, then must be routed to the correct lateral or chute to be loaded onto the plane. To get the bag to the correct terminal, the conveyor system needs to know where the bag needs to end up, to track where it is, and to move it onto the correct conveyors. It does this for thousands of bags, all at the same time. 
In addition to routing the bags, the conveyor system needs to have methods identify irregular luggage that could get stuck or damage the system. The system also needs to be safe for the operators.

## The Challenge

Your challenge is to design a BHS that can identify, track, route baggage through a simplified baggage handling environment, and detect anomalies or foreign objects on conveyor systems to ensure operational safety.

## Potential Solutions

The ideas below are examples to help teams explore possible directions. They are not the only possible solutions.

Teams are encouraged to combine ideas, explore new approaches, and develop creative solutions. 

| Potential solution | Description | Resources |
| --- | --- | --- | 
| Conveyor control [Supported] | Focuses on physical hardware and edge-computing setups centered on camera-driven barcode tracking, diverter actuation timing, and real-time scanner/routing logging. | [Barcode-Conveyor](barcode-conveyor/) |
| BHS simulation [Supported] | Simulation of bag movement through a simplified baggage handling system | [BHS Simulation](bhs-simulation/)
| Error handling | Error handling for unreadable, oversized, overweight, fragile, or untagged bags | 
| Detection | Foreign object, human intrusion, or anomaly detection on conveyor tracks |
| Operator signaling | Emergency stop, slowdown, or warning signals for conveyor operations | 

Your solution may be software-only, hardware-assisted, simulation-based or a combination. 

It is suggested to use the physical conveyor setup for this subproblem, although not necessary. Resources are provided to help you use the conveyor setup. Additional hardware can be borrowed from the IDEAs Clinic. You may also use the code provided for other subproblems, if you find it useful.

## Resources

### Industry Solutions

- [Brock Solutions SmartDrop](https://www.brocksolutions.com/smartdrop/): A system that allows passengers to self tag bags.
- [Daifuku sortation solutions](https://daifukuatec.com/airport-technologies/baggage-handling-systems/sortation): Daifuku offers various systems to aid in the tracking and sortation of baggage.

### Background Information

- **IATA Baggage Standards:** [Resolutions & Recommended Practices (e.g., Resolution 753 on tracking and Resolution 739 on security control)](https://www.iata.org/en/programs/ops-infra/baggage/standards/)
- **IATA Baggage Reference Manual (BRM):** [Consolidated industry operational guidelines and best practices](https://www.iata.org/en/publications/manuals/baggage-reference-manual/)
- **ACI World:** [Airport Operations & Terminal Processing Context](https://aci.aero/)
- **ICAO Publications:** [Global Standards for Secure & Interoperable Aviation Systems](https://www.icao.int/publications)

### Technical Resources

- **IATA Technical Peripheral Specifications (ITPS):** [Standard Device Communications for Printers, Self-Bag Drop, and Hardware](https://www.iata.org/en/publications/manuals/iata-technical-peripheral-specifications/)
- **IATA Baggage Information eXchange (BIX):** [Data Exchange & Interoperability Standards for Tracking](https://www.iata.org/en/programs/ops-infra/baggage/baggage-information-exchange-bix/)
- **Node-RED Guide:** [Node-RED Integration Guide](barcode-conveyor/Node-Red%20Guide.docx)
- **Barcode Recognition Script:** [Python Camera Barcode Tracking Script](barcode-conveyor/barcode_scanner.py)

### Data Sources

- **SecureBag Verification Dataset:** Sample images and bag metadata in [`securebag/sample_img/`](securebag/sample_img/) and [`securebag/bags.json`](securebag/bags.json)
- **BHS Simulation Scenarios:** Topology and scenario datasets in [`bhs-simulation/data/network_layout.json`](bhs-simulation/data/network_layout.json) and [`simulation_scenario.json`](bhs-simulation/data/simulation_scenario.json)

### Additional References

- **IABSC:** [International Association of Baggage System Companies (BHS technology and deployment)](https://www.iabsc.org/)
- **SITA Airport Solutions:** [Insights on End-to-End Baggage Tracking & Digital Operations](https://www.sita.aero/)
- **Brock Solutions:** [Industrial Logistics & Automation Integration Overview](https://www.brocksolutions.com/)
  
