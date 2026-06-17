# controller.py on the ESP32
import gc
import time
import network
from umqtt.robust import MQTTClient
from controller_config import (
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_PORT,
    MQTT_SSL_PARAMS,
    MQTT_TLS,
    MQTT_USER,
    WIFI_PASSWORD,
    WIFI_SSID,
)

LED_ON_BRIGHTNESS = 255

client = MQTTClient(
    b"esp32_db4",
    MQTT_HOST,
    port=MQTT_PORT,
    user=MQTT_USER,
    password=MQTT_PASSWORD,
    ssl=MQTT_TLS,
    ssl_params=MQTT_SSL_PARAMS,
)
led_on = True
pump1 = None
pump2 = None


def measure_temp():
    """Read temperature in Celsius from the thermistor, or None if out of range."""
    try:
        return read_temperature()
    except Exception as e:
        print(f"Temperature read failed: {e}")
        return None


def measure_od():
    """Read the light sensor. LED is controlled separately via db4/led/set."""
    return read_sensor()


def on_command(topic, msg):
    """Handle control commands from the dashboard."""
    global led_on
    cmd = msg.decode().strip()
    if topic == b"db4/pump1/set":
        if cmd == "on":
            pump1.on()
            client.publish(b"db4/pump1/state", b"on")
        elif cmd == "off":
            pump1.off()
            client.publish(b"db4/pump1/state", b"off")
    elif topic == b"db4/pump2/set":
        if cmd == "on":
            pump2.on()
            client.publish(b"db4/pump2/state", b"on")
        elif cmd == "off":
            pump2.off()
            client.publish(b"db4/pump2/state", b"off")
    elif topic == b"db4/led/set":
        if cmd == "on":
            set_blue_brightness(LED_ON_BRIGHTNESS)
            led_on = True
            client.publish(b"db4/led/state", b"on")
        elif cmd == "off":
            set_blue_brightness(0)
            led_on = False
            client.publish(b"db4/led/state", b"off")


# Connect WiFi.
wlan = network.WLAN(network.STA_IF)
if not wlan.active():
    wlan.active(True)
if not wlan.isconnected():
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while not wlan.isconnected():
        time.sleep(0.1)

# Connect MQTT before importing heavier hardware modules. The TLS handshake
# needs a large temporary allocation on the ESP32.
gc.collect()
client.connect()
time.sleep(1)

from pump import Pump
from temperature import read_temperature
from light_sensor import init_sensor, read_sensor
from rgb_led import set_blue_brightness

pump1 = Pump(pin=32, use_pwm=False)
pump2 = Pump(pin=33, use_pwm=False)
set_blue_brightness(LED_ON_BRIGHTNESS)  # LED defaults to on at boot

try:
    init_sensor()
except OSError as e:
    print(f"Light sensor init failed: {e} - OD will read None until sensor is fixed")

client.set_callback(on_command)
client.subscribe(b"db4/pump1/set")
client.subscribe(b"db4/pump2/set")
client.subscribe(b"db4/led/set")
client.subscribe(b"db4/control/#")

while True:
    client.check_msg()           # non-blocking: handle incoming commands
    temp = measure_temp()
    od = measure_od()
    client.publish(b"db4/temperature", str(temp))
    client.publish(b"db4/od", str(od))
    client.publish(b"db4/pump1/state", "on" if pump1.digital.value() else "off")
    client.publish(b"db4/pump2/state", "on" if pump2.digital.value() else "off")
    client.publish(b"db4/led/state", "on" if led_on else "off")
    time.sleep(2)
