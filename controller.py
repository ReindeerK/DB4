# controller.py on the ESP32
import gc
import time
import network
from umqtt.robust import MQTTClient
import controller_config as config
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
from algae_controller import AlgaeFeedingController

LED_ON_BRIGHTNESS = 255
WIFI_CONNECT_TIMEOUT_SECONDS = 15
WIFI_RETRY_DELAY_SECONDS = 5

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
feed_controller = None
last_feed_pump_on = False


def cfg(name, default):
    return getattr(config, name, default)


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


def set_feed_pump(on):
    global last_feed_pump_on
    if on == last_feed_pump_on:
        return
    drive_high = not on if cfg("FEED_PUMP_ACTIVE_LOW", False) else on
    if drive_high:
        pump1.on()
    else:
        pump1.off()
    last_feed_pump_on = on
    client.publish(b"db4/pump1/state", b"on" if on else b"off")


def publish_feed_telemetry(concentration):
    telemetry = feed_controller.telemetry()
    client.publish(b"db4/feed/mode", telemetry["mode"])
    client.publish(b"db4/feed/status", telemetry["status"])
    client.publish(b"db4/feed/target", str(telemetry["target"]))
    client.publish(b"db4/feed/low", str(telemetry["low"]))
    client.publish(b"db4/feed/high", str(telemetry["high"]))
    client.publish(b"db4/feed/dose_ml", str(telemetry["dose_ml"]))
    client.publish(b"db4/feed/pump_seconds", str(telemetry["pump_seconds"]))
    client.publish(b"db4/feed/grazing_coefficient", str(telemetry["grazing_coefficient"]))
    if concentration is not None:
        client.publish(b"db4/feed/concentration", str(concentration))
        client.publish(b"db4/cell", str(concentration))


def on_command(topic, msg):
    """Handle control commands from the dashboard."""
    global led_on
    cmd = msg.decode().strip()
    if topic == b"db4/pump1/set":
        if cmd == "on":
            feed_controller.set_mode("on", time.time())
            set_feed_pump(True)
        elif cmd == "off":
            feed_controller.set_mode("off", time.time())
            set_feed_pump(False)
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
    elif topic in (b"db4/feed/mode/set", b"db4/control/feed/set"):
        if feed_controller.set_mode(cmd, time.time()):
            if cmd == "off":
                set_feed_pump(False)
            elif cmd == "on":
                set_feed_pump(True)
            client.publish(b"db4/feed/mode", feed_controller.mode)
            client.publish(b"db4/feed/status", feed_controller.status)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)

    attempt = 1
    while not wlan.isconnected():
        print("Connecting to WiFi, attempt", attempt)
        try:
            wlan.disconnect()
        except Exception:
            pass
        time.sleep(1)

        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        waited = 0
        while waited < WIFI_CONNECT_TIMEOUT_SECONDS:
            if wlan.isconnected():
                print("WiFi connected:", wlan.ifconfig())
                return wlan
            time.sleep(1)
            waited += 1

        print("WiFi not connected, status:", wlan.status())
        attempt += 1
        time.sleep(WIFI_RETRY_DELAY_SECONDS)

    print("WiFi already connected:", wlan.ifconfig())
    return wlan


wlan = connect_wifi()

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
pump2 = Pump(pin=27, use_pwm=False)
set_blue_brightness(LED_ON_BRIGHTNESS)  # LED defaults to on at boot
feed_controller = AlgaeFeedingController(
    target_concentration=cfg("FEED_TARGET_CONCENTRATION", 2000.0),
    tank_volume_l=cfg("TANK_VOLUME_L", 4.0),
    stock_concentration=cfg("ALGAE_STOCK_CONCENTRATION", 250000.0),
    pump_flow_ml_min=cfg("FEED_PUMP_FLOW_ML_MIN", 0.8),
    low_fraction=cfg("FEED_LOW_FRACTION", 0.90),
    high_fraction=cfg("FEED_HIGH_FRACTION", 1.10),
    mussel_count=cfg("N_MUSSELS", 4),
    clearance_rate_l_h=cfg("MUSSEL_CLEARANCE_RATE_L_H", 2.5),
    algae_growth_rate_h=cfg("ALGAE_GROWTH_RATE_H", 0.035),
    min_pump_seconds=cfg("MIN_FEED_PUMP_SECONDS", 2),
    max_pump_seconds=cfg("MAX_FEED_PUMP_SECONDS", 300),
    dose_cooldown_seconds=cfg("FEED_DOSE_COOLDOWN_SECONDS", 60),
    sensor_stale_seconds=cfg("FEED_SENSOR_STALE_SECONDS", 120),
    od_mode=cfg("OD_CALIBRATION_MODE", "linear"),
    od_linear_slope=cfg("OD_LINEAR_SLOPE", 1.0),
    od_linear_intercept=cfg("OD_LINEAR_INTERCEPT", 0.0),
    od_blank_raw=cfg("OD_BLANK_RAW", 65000.0),
    od_absorbance_slope=cfg("OD_ABSORBANCE_SLOPE", 1.0),
    od_absorbance_intercept=cfg("OD_ABSORBANCE_INTERCEPT", 0.0),
    enabled=cfg("AUTO_FEED_ENABLED_ON_BOOT", False),
)

try:
    init_sensor()
except OSError as e:
    print(f"Light sensor init failed: {e} - OD will read None until sensor is fixed")

client.set_callback(on_command)
client.subscribe(b"db4/pump1/set")
client.subscribe(b"db4/pump2/set")
client.subscribe(b"db4/led/set")
client.subscribe(b"db4/feed/mode/set")
client.subscribe(b"db4/control/#")
client.publish(b"db4/feed/mode", feed_controller.mode)
client.publish(b"db4/feed/status", feed_controller.status)

while True:
    client.check_msg()           # non-blocking: handle incoming commands
    temp = measure_temp()
    od = measure_od()
    concentration = feed_controller.concentration_from_od(od)
    desired_feed_pump = feed_controller.update(concentration, time.time())
    set_feed_pump(desired_feed_pump)
    client.publish(b"db4/temperature", str(temp))
    client.publish(b"db4/od", str(od))
    publish_feed_telemetry(concentration)
    client.publish(b"db4/pump1/state", "on" if last_feed_pump_on else "off")
    client.publish(b"db4/pump2/state", "on" if pump2.digital.value() else "off")
    client.publish(b"db4/led/state", "on" if led_on else "off")
    time.sleep(2)
