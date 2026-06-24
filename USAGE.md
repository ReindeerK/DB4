# DB4 Bioreactor — Usage Guide

Quick reference for day-to-day operation and for re-running the OD sensor
LED calibration. For first-time setup from a blank laptop/board, see
[TESTING.md](TESTING.md).

## System overview

- **ESP32** runs `main.py` -> `controller.py` on boot: connects to WiFi and
  the MQTT broker, reads the temperature and OD sensors every ~2s, and
  controls two pumps (GPIO 32 and GPIO 33) via MQTT commands. Both pumps
  default to OFF on boot.
- **Laptop** runs the MQTT broker (Mosquitto, as a Windows service) and the
  Flask dashboard (`webapp.py`) at http://localhost:5000.
- *(Optional)* `logger.py` records every MQTT message to `db4_log.csv`.

---

## Normal startup

1. **Broker** — Mosquitto runs as a Windows service and starts
   automatically. Check it's running:
   ```powershell
   Get-Service mosquitto
   ```
   If `Status` isn't `Running`, start it (as Administrator):
   ```powershell
   Start-Service mosquitto
   ```

2. **WiFi** — turn on the iPhone Personal Hotspot with **Maximize
   Compatibility** enabled. The ESP32 only sees 2.4 GHz networks, and this
   setting is what makes the hotspot visible to it.

3. **ESP32** — plug it in / power it on. It boots automatically, connects
   to WiFi and MQTT, and starts publishing sensor data and pump state.
   - If the laptop's hotspot IP ever changes, update `BROKER_IP` in
     `controller.py` and re-flash it.

4. **Dashboard** — on the laptop:
   ```powershell
   python webapp.py
   ```
   Then open http://localhost:5000 in a browser. You should see live
   Temperature and OD readings, plus ON/OFF/AUTO controls for the feed pump.
   Use AUTO only after `controller_config.py` contains the measured OD
   calibration and feed-pump flow rate.

5. *(Optional)* **Logger** — to record everything to CSV:
   ```powershell
   python logger.py
   ```

## Shutting down

- Stop `webapp.py` / `logger.py` with Ctrl+C.
- The ESP32 can just be unplugged — both pumps come back up OFF on the next
  boot/reconnect.

## Autonomous feeding

The feed pump can run in three modes:

- **OFF** keeps the algae feed pump stopped.
- **ON** forces the algae feed pump on for manual priming/testing.
- **AUTO** lets the ESP32 dose algae from the OD-derived concentration.

In AUTO, the controller keeps the mussel-tank concentration between
`FEED_LOW_FRACTION * FEED_TARGET_CONCENTRATION` and
`FEED_HIGH_FRACTION * FEED_TARGET_CONCENTRATION`. When the OD-derived
concentration falls below the low threshold, it computes the required dose from
the mass-balance model and runs Pump 1 for the calibrated time. If the
concentration is too high or the OD signal is missing/stale, the pump stays off.

---

## Running the LED/OD calibration

`calibration.py` finds the LED color + brightness that gives the best
contrast for sensing algae density — i.e. the setting where the algae
absorbs the most light without saturating the sensor. Run this once per
physical sensor/LED setup, or whenever the LED, sensor position, or cuvette
changes.

You'll need a **dilution series** of algae samples ready (e.g. 0%, 25%,
50%, 75%, 100%).

1. Stop `controller.py` so it isn't fighting over the LED/I2C pins —
   connect to the board and press Ctrl-C to interrupt the running loop:
   ```powershell
   mpremote connect COM3
   ```
   (Ctrl-C interrupts the loop, Ctrl-] exits back to the shell)

2. Copy the calibration script to the board:
   ```powershell
   mpremote connect COM3 cp calibration.py :calibration.py
   ```

3. Connect to the REPL and run it interactively:
   ```powershell
   mpremote connect COM3
   ```
   ```python
   import calibration
   calibration.run()
   ```

4. Follow the prompts:
   - Enter how many samples you have, and a label for each.
   - For each sample, place it in front of the sensor and press Enter — the
     script automatically sweeps every LED color/intensity combo and takes
     a reading for each, with no further input needed until the next swap.

5. Read the results: it prints a table of `(color, intensity) -> contrast`
   for every combo, then the winning combo at the end.

6. **Apply the result** — in `controller.py`'s `measure_od()`, update
   `set_blue_brightness(255)` to use the winning intensity (and add the
   matching color call if you wired up red/green LEDs). Then re-flash and
   reset:
   ```powershell
   mpremote connect COM3 cp controller.py :controller.py
   mpremote connect COM3 reset
   ```

> Only blue (GPIO 25) is wired by default. To test red/green too, wire them
> up and fill in their GPIO pins in `LED_PINS` at the top of
> `calibration.py`.
