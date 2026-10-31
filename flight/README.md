# Flight Module (PX4 SITL & MAVSDK)

## Tasks 5.3 & 5.4 Verification Log

### Environment
- **OS**: Ubuntu 22.04 LTS (WSL2)
- **Autopilot / Simulator**: PX4-Autopilot SITL + Gazebo Harmonic (x500 quadcopter)
- **Control Interface**: MAVSDK-Python (mavsdk<4) over udp://:14540

### Setup & Prerequisites
1. Follow PX4 installation for Ubuntu 22.04 (./Tools/setup/ubuntu.sh).
2. Install Python dependencies:
   pip3 install -r flight/requirements.txt

### Execution Steps
1. Launch SITL (Headless):
   cd ~/PX4-Autopilot
   HEADLESS=1 make px4_sitl gz_x500

2. Execute MAVSDK Waypoint Script:
   python3 flight/mission_test.py

### Acceptance Verification
- **Task 5.3 (SITL Launch)**: Simulator initializes cleanly, enters pxh> prompt, and accepts manual arming and takeoff commands.
- **Task 5.4 (Programmatic Flight Gate)**:
  - Telemetry handshake verified on udp://:14540.
  - Dispatches automated arm and takeoff to hover.
  - Enters offboard mode and routes to relative NED target ([10.0m, 10.0m, -5.0m]).
  - Achieved position tolerance gate: Err: 0.50m <= 0.5m.
  - Disengages offboard mode, touches down, and disarms cleanly.nano flight/README.md
