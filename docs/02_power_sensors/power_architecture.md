# Power Architecture

[Back to README](../../README.md)

---

## Objective

Explain how the robot is powered and why this power system was selected.

---

## Battery

- **Model**: Gens Ace 1300mAh 2S LiPo
- **Voltage**: 7.4V nominal
- **Capacity**: 1300mAh
- **Discharge rating**: 45C
- **Connector**: Deans-T

**Why this battery was selected:**
- 7.4V (2S) sits within the operating range of the Furitek Lizard Pro ESC and Micro Komodo motor. 3S was considered but rejected as it would require aggressive speed limiting in software and increases overcurrent risk.
- 1300mAh provides enough capacity for approximately 5 full competition runs without adding unnecessary weight to the chassis.
- The 45C discharge rating ensures the battery can deliver peak current during hard acceleration without voltage sag that would otherwise destabilize the Raspberry Pi and servo.
- Deans-T connector was chosen for its low resistance and secure connection at high current draw.

> **Note:** A melted Deans-T connector was encountered early in the build due to undersized wiring. All wiring has since been replaced with correctly rated wire. The connector is checked before every run.

---

## Power System Overview

- **Main battery**: Gens Ace 1300mAh 2S LiPo, 7.4V nominal, 45C discharge
- **Main power consumers**: Drive motor (up to 10A), Raspberry Pi (up to 2.4A at full load)
- **Expected runtime**: ~17 minutes at average load (~5 full competition runs per charge)

---

## Power Distribution

- **Direct battery power**: ESC and drive motor draw directly from the battery through the main power rail.
- **Regulated power**: The Raspberry Pi receives 5V from a Yahboom voltage regulator board. This isolates the Pi from voltage fluctuations caused by the motor during acceleration.
- **Servo power**: The ESC's built-in BEC supplies 5V or 6.5V to the servo motor independently from the main motor rail.
- **Camera power**: The OV5647 camera draws 3.3V from the Raspberry Pi's CSI rail.
- **Arduino power**: The Arduino draws 5V from the Raspberry Pi over USB.
- **Voltage step-down**: Yahboom voltage regulator board converts 7.4V battery output to stable 5V for the Raspberry Pi.

---

## Power Diagram

*Insert labeled power diagram here.*

---

## Component Power Table

| Component | Operating Voltage | Estimated Current | Power Source |
|-----------|-------------------|-------------------|--------------|
| RC Car Battery (Gens Ace 1300mAh 2S LiPo) | 7.4V nominal | — | Self (source) |
| Drive Motor (Furitek Micro Komodo 1212) | 7.4V–11.1V (2S–3S) | Up to 10A continuous | ESC / Battery |
| ESC (Furitek Lizard Pro 30A/50A) | 7.4V–11.1V (2S–3S) | 30A constant, 50A burst | Battery (direct) |
| Servo Motor (Hitec HS-5055MG) | 4.8V–6.0V | 120mA no-load, 700mA stall | ESC BEC (5V or 6.5V) |
| Raspberry Pi 5 8GB | 5V | 2A–5A (idle ~1A, full load ~2.4A) | Step-down regulator from battery |
| Camera (OV5647 5MP) | 3.3V | ~250mA | Raspberry Pi 5 (CSI / 3.3V rail) |
| Microcontroller (Arduino Uno R3) | 5V | ~50mA | Raspberry Pi 5 (USB) |
| Power Switch | 7.4V | Up to 20A | In series with battery main rail |

---

## Design Rationale

- **Why this battery was selected:** The Gens Ace 1300mAh 2S LiPo balances capacity, weight, and discharge rate. The 45C rating ensures peak current can be delivered without voltage sag, and 1300mAh is sufficient for multiple competition runs without unnecessary weight.
- **Why this voltage level was selected:** 2S (7.4V nominal) sits within the operating range of the ESC and motor. 3S would require more aggressive software speed limiting and increases overcurrent risk without meaningful benefit for a wall-following robot.
- **Why this regulator setup was selected:** A Yahboom voltage regulator board isolates the Raspberry Pi from motor-induced voltage fluctuations. The ESC's built-in BEC handles servo power separately, further reducing load on the regulator and preventing servo actuation from affecting the Pi's supply.
- **Why this design is safe and reliable:** Each subsystem is powered independently — the motor draws directly from the battery through the ESC, the Pi draws through a dedicated regulator, and the servo draws from the ESC BEC. A motor current spike cannot directly affect the Pi or servo.

---

## Runtime Considerations

- **Estimated average current draw:** ~5.5–6.5A total across all components during a normal competition run.
- **Estimated peak current draw:** ~12–13A during hard acceleration when the motor, Pi vision pipeline, and servo are all active simultaneously.
- **Expected runtime:** Runtime ≈ 1.3Ah × 0.8 ÷ 6A ≈ 17 minutes at average load. The 0.8 factor accounts for the recommended 80% discharge limit on LiPo cells.
- **Factors that reduce runtime:**
  - Aggressive acceleration and high-speed driving
  - Frequent steering corrections
  - Heavy computational load on the Raspberry Pi (vision pipeline at 60fps)
  - Cold ambient temperatures reducing LiPo cell capacity

---

## Risks and Mitigation

- **Voltage drop:** The 45C discharge rating minimizes voltage sag under peak current draw. Battery voltage is monitored during practice runs to identify cell degradation early.
- **Brownout:** The Pi is powered through a Yahboom voltage regulator board rather than directly from the battery, isolating it from motor-induced voltage dips. A regulator with sufficient headroom above the Pi's peak draw was selected.
- **Electrical noise:** Motor and ESC wiring are routed away from signal wires. The serial communication lines between the Pi and Arduino are kept short.
- **Loose connectors:** All connectors are secured with heat shrink. The Deans-T connector is checked before every run. A melted connector was encountered in Week 14 due to undersized wiring — all wiring has since been replaced with correctly rated wire.
- **Overheating:** The ESC and motor are mounted with airflow clearance. Competition runs are under 3 minutes, well within thermal limits. The Raspberry Pi fan is configured to always run after the temperature sensor proved unreliable on our unit.
- **Power spikes from motors / servos:** The ESC BEC powers the servo independently from the motor rail. The dedicated regulator for the Pi prevents motor spikes from reaching the compute system.

---

## Iterations

- **Initial power design:** Large 20A toggle switch sourced from school supply; undersized wiring throughout the power harness; no dedicated regulator mount.
- **Problems observed:** Deans-T male connector melted during a test run due to excessive resistance from undersized wiring carrying motor current (Week 14). Step-down voltage regulator short circuited when wires were caught in the motor system; the regulator port broke as a result (Week 19). Large toggle switch was physically difficult to mount cleanly on the chassis.
- **Changes made:** Undersized wiring replaced with correctly rated wire throughout. Large toggle switch replaced with a smaller switch. Deans-T connector replaced. Dedicated mounting location created for the step-down regulator to keep it away from moving parts.
- **Final improvement:** High-current motor wiring is now fully separated from low-current signal and compute wiring. Each subsystem is powered independently. The regulator is physically isolated from the drivetrain to prevent future damage.

---
