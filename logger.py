# logger.py — run this on your laptop to save all sensor data
import paho.mqtt.client as mqtt
import csv, datetime, os, threading

LOG_DIR = "logs"
WRITE_DELAY = 0.5  # seconds to wait for the rest of a cycle's messages before writing a row

state = {"pump1": "", "pump2": "", "temperature": "", "od": ""}
log_path = None
write_timer = None

def on_connect(client, userdata, flags, rc):
    client.subscribe("db4/#")
    print("Logger connected, listening on db4/#")

def write_row():
    now = datetime.datetime.now()
    row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
           state["pump1"], state["pump2"], state["temperature"], state["od"]]
    print(row)
    with open(log_path, "a", newline="") as f:
        csv.writer(f).writerow(row)

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

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("localhost", 1883)
client.loop_forever()
