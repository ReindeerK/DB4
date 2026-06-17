# webapp.py — Flask dashboard for the DB4 bioreactor
# Subscribes to sensor topics over MQTT and lets the browser control the pump.
import threading

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template

BROKER_HOST = "localhost"
BROKER_PORT = 1883

app = Flask(__name__)

state_lock = threading.Lock()
state = {
    "temperature": None,
    "od": None,
    "pump1_state": None,
    "pump2_state": None,
    "led_state": None,
}


def on_connect(client, userdata, flags, rc):
    client.subscribe("db4/temperature")
    client.subscribe("db4/od")
    client.subscribe("db4/pump1/state")
    client.subscribe("db4/pump2/state")
    client.subscribe("db4/led/state")


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
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(BROKER_HOST, BROKER_PORT)
mqtt_client.loop_start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    with state_lock:
        return jsonify(state)


@app.route("/pump/<int:pump_id>/<cmd>", methods=["POST"])
def pump(pump_id, cmd):
    if pump_id not in (1, 2) or cmd not in ("on", "off"):
        return jsonify({"error": "invalid command"}), 400
    mqtt_client.publish(f"db4/pump{pump_id}/set", cmd)
    return jsonify({"ok": True})


@app.route("/led/<cmd>", methods=["POST"])
def led(cmd):
    if cmd not in ("on", "off"):
        return jsonify({"error": "invalid command"}), 400
    mqtt_client.publish("db4/led/set", cmd)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
