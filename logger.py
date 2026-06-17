# logger.py - run this on your laptop to save all sensor data
import csv
import datetime
import os
import ssl

import paho.mqtt.client as mqtt

LOG_FILE = "db4_log.csv"
BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
BROKER_USER = os.environ.get("MQTT_USERNAME")
BROKER_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() in ("1", "true", "yes", "on")


def on_connect(client, userdata, flags, rc):
    client.subscribe("db4/#")
    print("Logger connected, listening on db4/#")


def on_message(client, userdata, msg):
    row = [datetime.datetime.now().isoformat(), msg.topic, msg.payload.decode()]
    print(row)
    with open(LOG_FILE, "a", newline="") as f:
        csv.writer(f).writerow(row)


client = mqtt.Client()
if BROKER_USER:
    client.username_pw_set(BROKER_USER, BROKER_PASSWORD)
if MQTT_TLS:
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER_HOST, BROKER_PORT)
client.loop_forever()
