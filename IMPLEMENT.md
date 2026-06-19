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
```

`db4/cell` is optional. If it is not published, the backend derives a display
proxy from raw OD so the algae-density graph remains populated.

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
CELL_MAX=4.5
```

MQTT and authentication config remain in Heroku config vars and the local
ignored `controller_config.py`.

## Remaining UI-Only Item

Pump `AUTO` mode is still a UI placeholder. `ON` and `OFF` send real backend
commands. `AUTO` currently highlights the segment and reflects the last
hardware state, but there is no closed-loop control mode endpoint yet.
