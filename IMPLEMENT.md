# BioreactorDB4 dashboard backend notes

The dashboard in `templates/index.html` is wired to the Flask endpoints in
`webapp.py` and the MQTT topics published by the ESP32 controller.

## Live Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /status` | Latest app name, MQTT status, sensor values, actuator states, uptime, and last-seen timestamp |
| `GET /history?limit=90` | Recent temperature, OD, derived cell-density history, and MQTT event rows |
| `GET /events?limit=12` | Recent MQTT event log rows for the dashboard log strip |
| `POST /pump/<1\|2>/<on\|off>` | Pump 1/feed pump and pump 2/coolant loop commands |
| `POST /feed/mode/<off\|auto\|on>` | Feed-pump mode command for autonomous algae dosing |
| `POST /led/<on\|off>` | OD sensor LED command |

## MQTT Topics

The dashboard subscribes to:

```text
db4/temperature
db4/od
db4/cell
db4/pump1/state
db4/pump2/state
db4/led/state
db4/feed/#
```

`db4/cell` is optional. If it is not published, the backend derives a display
proxy from raw OD so the algae-density graph remains populated. The ESP32
closed-loop controller publishes `db4/cell` and `db4/feed/concentration` after
applying the configured OD calibration.

The controller accepts:

```text
db4/feed/mode/set = off | auto | on
```

In `auto`, the ESP32 uses the notebook mass-balance model:

```text
dose_ml = V_tank_ml * (C_target - C_current) / (C_stock - C_target)
pump_seconds = dose_ml / pump_flow_ml_min * 60
```

It doses only below `FEED_LOW_FRACTION * FEED_TARGET_CONCENTRATION`, stops
feeding above `FEED_HIGH_FRACTION * FEED_TARGET_CONCENTRATION`, and refuses to
dose if the OD signal is stale.

## Runtime Config

Branding:

```text
APP_NAME=BioreactorDB4
```

History/log sizing:

```text
HISTORY_LIMIT=720
EVENT_LIMIT=160
CELL_OD_FULL_SCALE=65000
CELL_MAX=5000
```

MQTT and authentication config remain in Heroku config vars and the local
ignored `controller_config.py`.

## Remaining UI-Only Item

Coolant-loop `AUTO` is still a UI placeholder. Feed-pump `AUTO`, `ON`, and
`OFF` send real backend commands.
