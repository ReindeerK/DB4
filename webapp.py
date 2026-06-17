# webapp.py - Flask dashboard for the DB4 bioreactor
# Subscribes to sensor topics over MQTT and lets the browser control the pumps.
import os
import secrets
import ssl
import threading
from functools import wraps

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, render_template, request

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
BROKER_USER = os.environ.get("MQTT_USERNAME")
BROKER_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() in ("1", "true", "yes", "on")

DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")

app = Flask(__name__)

state_lock = threading.Lock()
state = {
    "temperature": None,
    "od": None,
    "pump1_state": None,
    "pump2_state": None,
    "led_state": None,
}


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
            {"WWW-Authenticate": 'Basic realm="DB4 Dashboard"'},
        )

    return wrapped


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe("db4/temperature")
        client.subscribe("db4/od")
        client.subscribe("db4/pump1/state")
        client.subscribe("db4/pump2/state")
        client.subscribe("db4/led/state")
    else:
        print(f"MQTT connection failed with code {rc}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    with state_lock:
        if msg.topic == "db4/temperature":
            state["temperature"] = payload
        elif msg.topic == "db4/od":
            state["od"] = payload
        elif msg.topic == "db4/pump1/state":
            state["pump1_state"] = payload
        elif msg.topic == "db4/pump2/state":
            state["pump2_state"] = payload
        elif msg.topic == "db4/led/state":
            state["led_state"] = payload


mqtt_client = mqtt.Client()
if BROKER_USER:
    mqtt_client.username_pw_set(BROKER_USER, BROKER_PASSWORD)
if MQTT_TLS:
    mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect_async(BROKER_HOST, BROKER_PORT)
mqtt_client.loop_start()


@app.route("/")
@requires_auth
def index():
    return render_template("index.html")


@app.route("/status")
@requires_auth
def status():
    with state_lock:
        return jsonify(state)


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
