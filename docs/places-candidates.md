# Baylands Candidate Places (Task 6.2 / R1 Lane S)

Generated from `tools/baylands_map.py` mesh analysis and verified via MAVSDK flight telemetry in PX4 SITL + Gazebo Harmonic (x500).

## Origin Verification
* **Measured `[SIM] home`**: `lat=37.412173`, `lon=-121.998879`, `amsl=38.1 m`
* **Gazebo `baylands.sdf` Anchor**: `37.412173071650805, -121.998878727967`, elevation `38 m`
* **Match**: Confirmed exact match to world origin anchor. Frame is ENU ($+X$ East, $+Y$ North, $+Z$ Up).

## Conversion Formula
* $1^\circ \text{ Latitude} = 111,320\text{ m}$
* $1^\circ \text{ Longitude} = 111,320 \times \cos(37.412173^\circ) \approx 88,419.9\text{ m}$
* $\text{lat} = \text{lat}_0 + \frac{\text{north\_m}}{111320}$
* $\text{lon} = \text{lon}_0 + \frac{\text{east\_m}}{88419.9}$

## Candidate Places Table

| Name | north_m | east_m | lat | lon | Verified in Sim | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`north_field`** | $+200$ | $+240$ | `37.413972` | `-121.996161` | Yes (`3.0 m` horiz, `0.3 m` vert) | Open flat ground (`:`) in north-east sector. Clear for search patterns and landings. |
| **`buildings`** | $+80$ | $+160$ | `37.412892` | `-121.997066` | Yes (`3.0 m` horiz, `0.0 m` vert) | Near tall geometry cluster (`#`, structures/trees). Suitable for overwatch or perimeter checks. |
| **`bridge`** | $+280$ | $+40$ | `37.414691` | `-121.998425` | Yes (`3.0 m` horiz, `0.0 m` vert) | Near elevated boardwalk / bridge crossing extending over the water channel (`#` over `.`). |

*Note: Per team contract, `integration/places.json` is owned by R5/Language. This file records the simulator-validated candidates.*
