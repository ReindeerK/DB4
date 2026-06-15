# logger.py — run this on your laptop to save all sensor data
import paho.mqtt.client as mqtt
import csv, datetime, os

LOG_FILE = "db4_log.csv"

def on_connect(client, userdata, flags, rc):
    client.subscribe("db4/#")
    print("Logger connected, listening on db4/#")

def on_message(client, userdata, msg):
    row = [datetime.datetime.now().isoformat(), msg.topic, msg.payload.decode()]
    print(row)
    with open(LOG_FILE, "a", newline="") as f:
        csv.writer(f).writerow(row)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("localhost", 1883)
client.loop_forever()