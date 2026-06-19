# IMPLEMENT.md — design features awaiting backend support

The dashboard ([templates/index.html](templates/index.html)) was ported from the
Claude Design project **"Bioreactor eco-brutalism dashboard"** (`Bioreactor.dc.html`).
The original design ran on *simulated* data; this port is wired to the real Flask
endpoints in [webapp.py](webapp.py):

| Backend endpoint | Used by the UI for |
| --- | --- |
| `GET /status` → `{temperature, od, pump1_state, pump2_state, led_state}` | All live readouts (polled every 1 s) |
| `POST /pump/<1\|2>/<on\|off>` | Feed pump (id 1) / Coolant loop (id 2) ON/OFF |
| `POST /led/<on\|off>` | OD Sensor LED toggle |

**Actuator mapping (decided):** Algae Feed Pump → `pump 1`, Coolant Loop → `pump 2`.

Everything below is present in the design but has **no corresponding backend
functionality yet**. Each item lists exactly where the UI hook already exists so it
can be connected without re-touching the markup.

---

## 1. Algae density / cell count (no data source)

- **Design elements:** `CX·05` readout (`#cell-value`), the `AD·04` history graph
  (`#cell-canvas`, `#cell-graph-val`), and the `[data-fx="cellbar"]` bar.
- **Current behaviour:** The UI already reads `data.cell` from `/status`. Because the
  backend never sends it, the value falls back to `—` and the graph/bar stay empty.
- **To connect:**
  1. Have a sensor/process publish algae density (in `×10⁸ cells/mL`) to an MQTT topic,
     e.g. `db4/cell`.
  2. In [webapp.py](webapp.py): add `"cell": None` to the `state` dict, `client.subscribe("db4/cell")`
     in `on_connect`, and a branch in `on_message` setting `state["cell"]`.
  3. No frontend change needed — `refresh()` already plots `data.cell` and updates
     `#cell-value` / `#cell-graph-val`. Graph domain is `CELL_MIN..CELL_MAX` (0–4.5) in the JS constants.

## 2. Pump AUTO mode (no control loop)

- **Design elements:** the `OFF / AUTO / ON` segmented switches (`[data-seg-btn="feed:auto"]`,
  `[data-seg-btn="cool:auto"]`).
- **Current behaviour:** `OFF` and `ON` POST to the real `/pump/<id>/<cmd>` endpoint.
  **`AUTO` is UI-only** — selecting it highlights the segment but sends no command and
  starts no closed-loop control. Status text shows `AUTO · RUNNING/IDLE` based purely on
  the last reported pump state.
- **To connect:**
  1. Implement the control loops the design implies:
     - **Feed pump:** hysteresis on algae density (design used: turn on below 1.6, off above 2.6 ×10⁸).
     - **Coolant loop:** hysteresis on temperature around the setpoint (design used: on above 17.9 °C, off below 17.1 °C).
     This logic belongs server-side (e.g. in [controller.py](controller.py)), driving the same MQTT `set` topics.
  2. Add a mode endpoint, e.g. `POST /pump/<id>/mode/<off|auto|on>`, and report the current
     mode in `/status` (e.g. `pump1_mode`).
  3. In the JS, change the `data-seg-btn` handler so `auto` POSTs to the mode endpoint, and
     initialise `mode.feed`/`mode.cool` from the new `/status` mode fields instead of from on/off state.

## 3. Temperature setpoint (display only)

- **Design elements:** `SETPOINT` row (`#setpoint`) and the `Δ` deviation chip (`#temp-dev`),
  plus the NOMINAL/DRIFT/WARNING `STATUS` (`#temp-status`).
- **Current behaviour:** Setpoint is the JS constant `SETPOINT = 17.5`; deviation and status
  are derived client-side from it. The operator cannot change it.
- **To connect:** add `GET/POST /setpoint` (and include `setpoint` in `/status`), then replace
  the `SETPOINT` constant with the value from `data.setpoint`. The design's prop allowed
  14–21 °C in 0.5 steps if you add an editor control.

## 4. Uptime (client-side only)

- **Design element:** `UPTIME` (`#uptime`).
- **Current behaviour:** counted from browser page-load in `tickUptime()`; resets on refresh.
- **To connect:** expose process/reactor uptime (seconds) in `/status` and render that instead.

## 5. OD calibration to AU (raw shown)

- **Design element:** `OD·600` readout (`#od-value`, `[data-fx="odbar"]`).
- **Decision:** show the **raw sensor value** from `/status` (the design's 0–2.0 AU scale was scrapped).
- **Current behaviour:** raw counts are displayed; the bar scales against `OD_MAX = 65000`
  (tune this constant to the sensor's full-scale range). Shows `—` while the LED source is off.
- **Optional future work:** if calibrated optical density (AU) is wanted, convert raw counts
  using [calibration.py](calibration.py) / [linearize.py](linearize.py) server-side, publish the
  calibrated value, and adjust `OD_MAX`/the unit label (`raw`) accordingly.

## 6. Persistent history graphs

- **Design elements:** `TG·02` temp graph and `AD·04` density graph.
- **Current behaviour:** history is accumulated **in the browser** from polling (`HIST_LEN = 90`
  samples ≈ 60 s). Temperature works immediately; density needs item #1 first. History is lost on reload.
- **Optional future work:** add a backend history endpoint (e.g. `GET /history?metric=temperature&window=60`)
  backed by [logger.py](logger.py) and seed the `tempHist`/`cellHist` arrays from it on load.

## 7. Static / cosmetic items (no backend intended)

- **`ALARMS 0`** in the actuator header — hard-coded; wire to a real alarm count if an alarm
  system is added.
- **Organism label** (`#organism`) — JS constant `ORGANISM`; could come from config/`/status`.
- **`LIVE` indicator** (`#live-indicator`) — already reflects `/status` fetch success
  (flips to `OFFLINE` on fetch failure); no further work needed.
- Sub-labels such as `660nm SOURCE`, `0.8 mL/min`, `Δ-3.2°C`, `OPTIMAL 17–18 °C` are static
  descriptive text from the design.
