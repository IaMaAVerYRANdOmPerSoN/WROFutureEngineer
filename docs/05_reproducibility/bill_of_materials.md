# Bill of Materials

[Back to README](../../README.md)

This document lists all components used to build the robot, including electronics, mechanical parts, and consumables.

---

## Electronics

| Component | Model | Purpose | Quantity | Price (CAD) |
|-----------|-------|---------|----------|-------------|
| Main Compute | [Raspberry Pi 5 (8GB)](https://www.amazon.ca/RasTech-Raspberry-Pi-refroidisseur-inclus/dp/B0DQX6JPVM) | Vision, control logic, Arduino communication | 1 | $170 |
| Microcontroller | [Arduino Uno R3](https://grabcad.com/library/arduino-uno-r3-1) | PWM output to ESC and servo | 1 | $13 |
| Drive Motor | [Furitek Micro Komodo 1212 3450KV](https://furitek.com/products/furitek-micro-komodo-1212-3456kv-brushless-motor-with-15t-steel-pinion-for-fury-wagon-fx118) | Rear wheel drive | 1 | $35 |
| ESC | [Furitek Lizard Pro 30A/50A](https://furitek.com/products/combo-of-furitek-lizard-pro-30a-50a-brushed-brushless-esc-for-axial-scx24-with-bluetooth) | Motor speed control | 1 | $80 |
| Servo Motor | [Hitec HS-5055MG](https://hitecrcd.com/hs-5055mg-economy-metal-gear-feather-servo/) | Steering control | 1 | $25 |
| Camera | [OV5647 5MP 1080P](https://www.amazon.ca/dp/B0D324RKRZ) | Wall, pillar, and corner line detection | 1 | $35 |
| LiDAR | LD19 | 360-degree wall distance measurement | 1 | — |
| Battery | [Gens Ace 1300mAh 2S LiPo 45C](https://genstattu.com/gens-ace-1300mah-2s-7-4v-45c-g-tech-lipo-battery-pack-with-deans-plug/) | Main power source | 1 | $21 |
| Voltage Regulator | Pololu Step-Down (5V) | Powers Raspberry Pi from battery | 1 | $15 |
| Power Switch | — | Main battery on/off | 1 | — |
| Deans-T Connector | — | Battery main connector | 2 | — |

---

## Mechanical

| Component | Purpose | Quantity | Price (CAD) |
|-----------|---------|----------|-------------|
| Wheels (35mm rubber, 1/28 scale) | [1/28 RC Drift Tires](https://www.amazon.ca/AllinRC-Pre-glued-Compatible-WLtoys-Racing/dp/B0B4DH61L9) | Rear and front wheels | 4 | $27 (pack) |
| RC Differential Gearbox | Drive power to rear wheels | 1 | — |
| 6mm Ball Bearings | Axle support in rear body mount | 4 | — |
| M2 Screws | Securing small components | ~20 | — |
| M2.5 Screws | Raspberry Pi mounting (nylon) | ~8 | — |
| M3 Screws | Sensor tower, chassis mounts | ~16 | — |

---

## Tools Required

| Tool | Purpose |
|------|---------|
| FDM 3D Printer | Printing chassis and mount parts |
| Soldering Iron | Wiring and connector work |
| Solder | — |
| Electrical Tape | Wire insulation and securing |
| Heat Shrink | Connector protection |
| Wire Strippers | Wiring |
| Multimeter | Voltage and continuity checks |
| Drill | Chassis modifications |
| M2 / M2.5 / M3 Hex Driver | Fastening screws |

---

## Total Estimated Cost

| Category | Estimated Cost (CAD) |
|----------|----------------------|
| Electronics | ~$394 |
| Mechanical | ~$27 |
| Filament | ~$10 |
| **Total** | **~$431** |

*Prices are approximate and based on retail cost at time of purchase. Some components were sourced from existing supplies.*
