# webapp.py - Flask dashboard for BioreactorDB4
# Subscribes to sensor topics over MQTT and lets the browser control the pumps.
import os
import secrets
import ssl
import threading
import time
from collections import deque
from datetime import datetime, timezone
from functools import wraps

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, render_template, request

APP_NAME = os.environ.get("APP_NAME", "BioreactorDB4")

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
BROKER_USER = os.environ.get("MQTT_USERNAME")
BROKER_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() in ("1", "true", "yes", "on")

DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")

HISTORY_LIMIT = int(os.environ.get("HISTORY_LIMIT", "720"))
EVENT_LIMIT = int(os.environ.get("EVENT_LIMIT", "160"))
CELL_OD_FULL_SCALE = float(os.environ.get("CELL_OD_FULL_SCALE", "65000"))
CELL_MAX = float(os.environ.get("CELL_MAX", "4.5"))

app = Flask(__name__)
started_at = time.time()

state_lock = threading.Lock()
state = {
    "app_name": APP_NAME,
    "temperature": None,
    "od": None,
    "cell": None,
    "cell_source": None,
    "pump1_state": None,
    "pump2_state": None,
    "led_state": None,
    "mqtt_connected": False,
    "last_seen": None,
}

history = {
    "temperature": deque(maxlen=HISTORY_LIMIT),
    "od": deque(maxlen=HISTORY_LIMIT),
    "cell": deque(maxlen=HISTORY_LIMIT),
}
events = deque(maxlen=EVENT_LIMIT)

TOPIC_TO_KEY = {
    "db4/temperature": "temperature",
    "db4/od": "od",
    "db4/cell": "cell",
    "db4/pump1/state": "pump1_state",
    "db4/pump2/state": "pump2_state",
    "db4/led/state": "led_state",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_float(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def derived_cell_from_od(od_value):
    od_float = parse_float(od_value)
    if od_float is None or CELL_OD_FULL_SCALE <= 0:
        return None
    return max(0.0, min(CELL_MAX, (od_float / CELL_OD_FULL_SCALE) * CELL_MAX))


def add_history(metric, value, ts):
    parsed = parse_float(value)
    if parsed is not None:
        history[metric].append({"ts": ts, "value": parsed})


def add_event(topic, payload, ts):
    events.appendleft({"ts": ts, "topic": topic, "value": payload})


def requires_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not DASHBOARD_PASSWORD:
            return view(*args, **kwargs)

        auth = request.authorization
        valid_username = auth and secrets.compare_digest(
            auth.username or "",
            DASHBOARD_USERNAME,
        )
        valid_password = auth and secrets.compare_digest(
            auth.password or "",
            DASHBOARD_PASSWORD,
        )
        if valid_username and valid_password:
            return view(*args, **kwargs)

        return Response(
            "Authentication required",
            401,
            {"WWW-Authenticate": f'Basic realm="{APP_NAME}"'},
        )

    return wrapped


def on_connect(client, userdata, flags, rc):
    with state_lock:
        state["mqtt_connected"] = rc == 0
    if rc == 0:
        client.subscribe("db4/temperature")
        client.subscribe("db4/od")
        client.subscribe("db4/cell")
        client.subscribe("db4/pump1/state")
        client.subscribe("db4/pump2/state")
        client.subscribe("db4/led/state")
    else:
        print(f"MQTT connection failed with code {rc}")


def on_disconnect(client, userdata, rc):
    with state_lock:
        state["mqtt_connected"] = False
    if rc:
        print(f"MQTT disconnected with code {rc}")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    key = TOPIC_TO_KEY.get(topic)
    ts = now_iso()

    with state_lock:
        state["last_seen"] = ts
        if key:
            state[key] = payload

        if key in history:
            add_history(key, payload, ts)

        if key == "od":
            derived_cell = derived_cell_from_od(payload)
            if derived_cell is not None and state.get("cell_source") != "mqtt":
                state["cell"] = f"{derived_cell:.3f}"
                state["cell_source"] = "derived"
                add_history("cell", derived_cell, ts)
        elif key == "cell":
            state["cell"] = payload
            state["cell_source"] = "mqtt"

        add_event(topic, payload, ts)


mqtt_client = mqtt.Client()
if BROKER_USER:
    mqtt_client.username_pw_set(BROKER_USER, BROKER_PASSWORD)
if MQTT_TLS:
    mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message
mqtt_client.connect_async(BROKER_HOST, BROKER_PORT)
mqtt_client.loop_start()


@app.route("/")
@requires_auth
def index():
    return render_template("index.html", app_name=APP_NAME)


@app.route("/status")
@requires_auth
def status():
    with state_lock:
        payload = dict(state)
        payload["uptime_seconds"] = int(time.time() - started_at)
        return jsonify(payload)


@app.route("/history")
@requires_auth
def get_history():
    limit = request.args.get("limit", type=int) or HISTORY_LIMIT
    limit = max(1, min(limit, HISTORY_LIMIT))
    with state_lock:
        return jsonify(
            {
                "app_name": APP_NAME,
                "temperature": list(history["temperature"])[-limit:],
                "od": list(history["od"])[-limit:],
                "cell": list(history["cell"])[-limit:],
                "events": list(events)[: min(limit, EVENT_LIMIT)],
            }
        )


@app.route("/events")
@requires_auth
def get_events():
    limit = request.args.get("limit", type=int) or 60
    limit = max(1, min(limit, EVENT_LIMIT))
    with state_lock:
        return jsonify({"events": list(events)[:limit]})


@app.route("/pump/<int:pump_id>/<cmd>", methods=["POST"])
@requires_auth
def pump(pump_id, cmd):
    if pump_id not in (1, 2) or cmd not in ("on", "off"):
        return jsonify({"error": "invalid command"}), 400
    mqtt_client.publish(f"db4/pump{pump_id}/set", cmd)
    return jsonify({"ok": True})


@app.route("/led/<cmd>", methods=["POST"])
@requires_auth
def led(cmd):
    if cmd not in ("on", "off"):
        return jsonify({"error": "invalid command"}), 400
    mqtt_client.publish("db4/led/set", cmd)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
