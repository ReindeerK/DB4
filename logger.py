# logger.py - run this on your laptop to save all sensor data
import csv
import datetime
import os
import ssl

import paho.mqtt.client as mqtt
<<<<<<< HEAD

LOG_FILE = "db4_log.csv"
BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
BROKER_USER = os.environ.get("MQTT_USERNAME")
BROKER_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() in ("1", "true", "yes", "on")

=======
import csv, datetime, os, threading

LOG_DIR = "logs"
WRITE_DELAY = 0.5  # seconds to wait for the rest of a cycle's messages before writing a row

state = {"pump1": "", "pump2": "", "temperature": "", "od": ""}
log_path = None
write_timer = None
>>>>>>> 26790027050b14419c03b8ae9202f903bb8793d0

def on_connect(client, userdata, flags, rc):
    client.subscribe("db4/#")
    print("Logger connected, listening on db4/#")

<<<<<<< HEAD

def on_message(client, userdata, msg):
    row = [datetime.datetime.now().isoformat(), msg.topic, msg.payload.decode()]
=======
def write_row():
    now = datetime.datetime.now()
    row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
           state["pump1"], state["pump2"], state["temperature"], state["od"]]
>>>>>>> 26790027050b14419c03b8ae9202f903bb8793d0
    print(row)
    with open(log_path, "a", newline="") as f:
        csv.writer(f).writerow(row)

<<<<<<< HEAD
=======
def on_message(client, userdata, msg):
    global write_timer
    payload = msg.payload.decode()
    if msg.topic == "db4/temperature":
        state["temperature"] = payload
    elif msg.topic == "db4/od":
        state["od"] = payload
    elif msg.topic == "db4/pump1/state":
        state["pump1"] = payload
    elif msg.topic == "db4/pump2/state":
        state["pump2"] = payload
    else:
        return
    # debounce: collapse a whole cycle's worth of messages into a single row
    if write_timer:
        write_timer.cancel()
    write_timer = threading.Timer(WRITE_DELAY, write_row)
    write_timer.start()

os.makedirs(LOG_DIR, exist_ok=True)
name = input("Name for this log file: ").strip() or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOG_DIR, f"{name}.csv")
while os.path.exists(log_path):
    name = input(f"'{name}.csv' already exists, choose another name: ").strip()
    if name:
        log_path = os.path.join(LOG_DIR, f"{name}.csv")

with open(log_path, "w", newline="") as f:
    csv.writer(f).writerow(["date", "time", "pump1", "pump2", "temperature", "od"])
print(f"Logging to {log_path}")
>>>>>>> 26790027050b14419c03b8ae9202f903bb8793d0

client = mqtt.Client()
if BROKER_USER:
    client.username_pw_set(BROKER_USER, BROKER_PASSWORD)
if MQTT_TLS:
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
client.on_connect = on_connect
client.on_message = on_message
<<<<<<< HEAD
client.connect(BROKER_HOST, BROKER_PORT)
=======
client.connect("localhost", 1883)
>>>>>>> 26790027050b14419c03b8ae9202f903bb8793d0
client.loop_forever()
