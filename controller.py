# controller.py on the ESP32
import time, network
from umqtt.robust import MQTTClient
from pump import Pump
from temperature import read_temperature
from light_sensor import init_sensor, read_sensor
from rgb_led import set_blue_brightness

WIFI_SSID = "andrejs_iphone"
WIFI_PASSWORD = "2number9"

# Cloud MQTT broker settings. Use port 8883 with TLS for HiveMQ Cloud,
# EMQX Cloud, and most hosted MQTT providers.
MQTT_HOST = "your-mqtt-broker-host"
MQTT_PORT = 8883
MQTT_USER = b"your-mqtt-username"
MQTT_PASSWORD = b"your-mqtt-password"
MQTT_TLS = True

LED_ON_BRIGHTNESS = 255

pump1 = Pump(pin=32, use_pwm=False)
pump2 = Pump(pin=33, use_pwm=False)
client = MQTTClient(
    b"esp32_db4",
    MQTT_HOST,
    port=MQTT_PORT,
    user=MQTT_USER,
    password=MQTT_PASSWORD,
    ssl=MQTT_TLS,
)
led_on = True
set_blue_brightness(LED_ON_BRIGHTNESS)  # LED defaults to on at boot


def measure_temp():
    """Read temperature in Celsius from the thermistor, or None if out of range."""
    return read_temperature()


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

# Connect WiFi
wlan = network.WLAN(network.STA_IF)
if not wlan.active():
    wlan.active(True)
if not wlan.isconnected():
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while not wlan.isconnected():
        time.sleep(0.1)

# Connect MQTT and subscribe to control topic
client.set_callback(on_command)
client.connect()
time.sleep(1)   # let WiFi settle after MQTT handshake before touching I2C
try:
    init_sensor()
except OSError as e:
    print(f"Light sensor init failed: {e} — OD will read None until sensor is fixed")
client.subscribe(b"db4/pump1/set")
client.subscribe(b"db4/pump2/set")
client.subscribe(b"db4/led/set")
client.subscribe(b"db4/control/#")

while True:
    client.check_msg()           # non-blocking: handle incoming commands
    temp = measure_temp()
    od   = measure_od()
    client.publish(b"db4/temperature", str(temp))
    client.publish(b"db4/od",          str(od))
    client.publish(b"db4/pump1/state", "on" if pump1.digital.value() else "off")
    client.publish(b"db4/pump2/state", "on" if pump2.digital.value() else "off")
    client.publish(b"db4/led/state",   "on" if led_on else "off")
    time.sleep(2)
