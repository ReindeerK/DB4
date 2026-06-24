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
| `POST /cool/mode/<off\|auto\|on>` | Coolant loop PID mode |
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
db4/cool/mode
db4/temp/control/status
db4/temp/control/setpoint
db4/temp/control/predicted
db4/temp/control/filtered
db4/temp/control/rate_c_per_min
db4/temp/control/output
db4/temp/control/feed_forward
db4/temp/control/sample_count
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

## Temperature Control

The ESP32 publishes the mean of multiple thermistor conversions per reporting
interval, then runs a cooling-only PID around a 17.5 C setpoint. It filters the
averaged tank temperature, projects the current temperature trend forward, and
adds feed-forward cooling while the algae feed pump is running. The coolant
loop can use PWM or slow time-proportional on/off control depending on
`COOLING_PUMP_USE_PWM`.

Tune these values in `controller_config.py` after logging a few heating and
cooling runs:

```text
TEMP_PID_KP
TEMP_PID_KI
TEMP_PID_KD
TEMP_AVERAGE_SAMPLES
TEMP_AVERAGE_SAMPLE_DELAY_MS
TEMP_PREDICTION_HORIZON_SECONDS
TEMP_FEED_TEMP_RISE_C
TEMP_FEED_FORWARD_PERCENT
```
