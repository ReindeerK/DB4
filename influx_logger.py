# influx_logger.py - Heroku worker that stores selected MQTT messages in InfluxDB.
import os
import signal
import ssl
import sys
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


APP_NAME = os.environ.get("APP_NAME", "BioreactorDB4")

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
BROKER_USER = os.environ.get("MQTT_USERNAME")
BROKER_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TLS = os.environ.get("MQTT_TLS", "false").lower() in ("1", "true", "yes", "on")

INFLUXDB_URL = os.environ.get("INFLUXDB_URL")
STACKHERO_INFLUXDB_HOST = os.environ.get("STACKHERO_INFLUXDB_HOST")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN") or os.environ.get("STACKHERO_INFLUXDB_TOKEN")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "db4")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "db4")
INFLUXDB_MEASUREMENT = os.environ.get("INFLUXDB_MEASUREMENT", "db4")

if not INFLUXDB_URL and STACKHERO_INFLUXDB_HOST:
    INFLUXDB_URL = STACKHERO_INFLUXDB_HOST
    if not INFLUXDB_URL.startswith(("http://", "https://")):
        INFLUXDB_URL = "https://" + INFLUXDB_URL

TOPIC_FIELDS = {
    "db4/temperature": ("temperature", float),
    "db4/od": ("od", float),
    "db4/cell": ("cell", float),
    "db4/pump1/state": ("pump1_state", str),
    "db4/pump2/state": ("pump2_state", str),
    "db4/led/state": ("led_state", str),
}

influx_client = None
write_api = None
mqtt_client = None


def require_config():
    missing = []
    if not INFLUXDB_URL:
        missing.append("INFLUXDB_URL or STACKHERO_INFLUXDB_HOST")
    if not INFLUXDB_TOKEN:
        missing.append("INFLUXDB_TOKEN or STACKHERO_INFLUXDB_TOKEN")
    if missing:
        print("Missing required InfluxDB config: " + ", ".join(missing), file=sys.stderr)
        sys.exit(1)


def parse_payload(payload, parser):
    value = payload.strip()
    if parser is str:
        return value
    try:
        parsed = parser(value)
    except ValueError:
        return None
    if parsed != parsed:
        return None
    return parsed


def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"MQTT connection failed with code {rc}", file=sys.stderr)
        return

    for topic in TOPIC_FIELDS:
        client.subscribe(topic)
    print(f"{APP_NAME} Influx logger connected; subscribed to {len(TOPIC_FIELDS)} topics")


def on_disconnect(client, userdata, rc):
    if rc:
        print(f"MQTT disconnected with code {rc}", file=sys.stderr)


def on_message(client, userdata, msg):
    topic = msg.topic
    field = TOPIC_FIELDS.get(topic)
    if not field:
        return

    field_name, parser = field
    payload = msg.payload.decode(errors="replace")
    value = parse_payload(payload, parser)
    if value is None:
        print(f"Skipping non-numeric payload for {topic}: {payload!r}", file=sys.stderr)
        return

    point = (
        Point(INFLUXDB_MEASUREMENT)
        .tag("topic", topic)
        .field(field_name, value)
        .time(datetime.now(timezone.utc))
    )
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
    print(f"Wrote {topic}={payload}")


def shutdown(signum, frame):
    print("Shutting down Influx logger")
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    if write_api:
        write_api.close()
    if influx_client:
        influx_client.close()
    sys.exit(0)


def main():
    global influx_client, write_api, mqtt_client

    require_config()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    mqtt_client = mqtt.Client(client_id="db4-influx-logger")
    if BROKER_USER:
        mqtt_client.username_pw_set(BROKER_USER, BROKER_PASSWORD)
    if MQTT_TLS:
        mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    mqtt_client.connect(BROKER_HOST, BROKER_PORT)
    mqtt_client.loop_forever()


if __name__ == "__main__":
    main()
