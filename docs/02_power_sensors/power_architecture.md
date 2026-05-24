# Power Architecture

## Objective
Explain how the robot is powered and why this power system was selected.

## Power System Overview
- Main battery type: Gens Ace 1300mAh
- Battery voltage: 7.4V
- Battery capacity: 1300mAh
- Main power consumers: Drive motor (up to 10A), Raspberry Pi (2.4A)
- Expected runtime: N/A

## Power Distribution
- What components receive direct battery power: Everything other than Raspiberry Pi and Camera
- What components use regulated power: Raspberry Pi, Camera
- What regulators / BECs / converters are used:
- How voltage is stepped down if needed:

## Power Diagram
[Insert a labeled power diagram here]

## Component Power Table
| Component | Operating Voltage | Estimated Current | Power Source |
|----------|-------------------|-------------------|--------------|
| Drive Motor (Furitek Micro Komodo 1212) | 7.4V–11.1V (2S–3S) | Up to 10A continuous | ESC / Battery |
| ESC (Furitek Lizard Pro 30A/50A) | 7.4V–11.1V (2S–3S) | 30A constant, 50A burst | Battery (direct) |
| Servo Motor (Hitec HS-5055MG) | 4.8V–6.0V | 120mA no-load, 700mA stall | ESC BEC (5V or 6.5V) |
| Raspberry Pi 5 8GB | 5V | 2A–5A (idle ~1A, full load ~2.4A) | Step-down regulator from battery |
| Camera (OV5647 5MP) | 3.3V | ~250mA | Raspberry Pi 5 (CSI / 3.3V rail) |
| Microcontroller (Arduino Uno R3) | 5V | ~50mA | Raspberry Pi 5 (USB) |
|          |                   |                   |              |

## Design Rationale
- Why this battery was selected: 7.4V sits well in the operating range
- Why this voltage level was selected:
- Why this regulator setup was selected:
- Why this design is safe and reliable:

## Runtime Considerations
- Estimated average current draw:
- Estimated peak current draw:
- Expected runtime under testing conditions:
- Factors that reduce runtime:

## Risks and Mitigation
- Voltage drop:
- Brownout:
- Electrical noise:
- Loose connectors:
- Overheating:
- Power spikes from motors / servos:

## Iterations
- Initial power design:
- Problems observed:
- Changes made:
- Final improvement:

## Final Notes
Summarize why this power architecture was the best choice for the robot.