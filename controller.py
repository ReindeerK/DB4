# controller.py on the ESP32
import gc
import time
import network
import controller_config as controller_settings
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
WIFI_CONNECT_TIMEOUT_SECONDS = 15
WIFI_RETRY_DELAY_SECONDS = 5


def config_value(name, default):
    return getattr(controller_settings, name, default)


TEMP_SETPOINT_C = config_value("TEMP_SETPOINT_C", 17.5)
TEMP_MIN_C = config_value("TEMP_MIN_C", 17.0)
TEMP_MAX_C = config_value("TEMP_MAX_C", 18.0)
TEMP_PID_KP = config_value("TEMP_PID_KP", 35.0)
TEMP_PID_KI = config_value("TEMP_PID_KI", 0.015)
TEMP_PID_KD = config_value("TEMP_PID_KD", 0.0)
TEMP_PID_DEADBAND_C = config_value("TEMP_PID_DEADBAND_C", 0.05)
TEMP_FILTER_ALPHA = config_value("TEMP_FILTER_ALPHA", 0.35)
TEMP_PREDICTION_HORIZON_SECONDS = config_value("TEMP_PREDICTION_HORIZON_SECONDS", 90.0)
TEMP_FEED_TEMP_RISE_C = config_value("TEMP_FEED_TEMP_RISE_C", 0.20)
TEMP_FEED_FORWARD_PERCENT = config_value("TEMP_FEED_FORWARD_PERCENT", 15.0)
TEMP_REPORT_INTERVAL_MS = config_value("TEMP_REPORT_INTERVAL_MS", 2000)
TEMP_AVERAGE_SAMPLES = config_value("TEMP_AVERAGE_SAMPLES", 12)
TEMP_AVERAGE_SAMPLE_DELAY_MS = config_value("TEMP_AVERAGE_SAMPLE_DELAY_MS", 120)
TEMP_CONTROL_MODE = config_value("TEMP_CONTROL_MODE", "auto")
FEED_CONTROL_MODE = config_value("FEED_CONTROL_MODE", "off")
COOLING_PUMP_USE_PWM = config_value("COOLING_PUMP_USE_PWM", False)
COOLING_PWM_FREQ = config_value("COOLING_PWM_FREQ", 1000)
COOLING_CONTROL_WINDOW_SECONDS = config_value("COOLING_CONTROL_WINDOW_SECONDS", 30)

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
temp_pid = None
cool_mode = TEMP_CONTROL_MODE
feed_mode = FEED_CONTROL_MODE
cooling_window_started_ms = 0
cooling_output_percent = 0.0
last_temp_sample_count = 0


def measure_temp():
    """Read temperature in Celsius from the thermistor, or None if out of range."""
    try:
        return read_temperature()
    except Exception as e:
        print(f"Temperature read failed: {e}")
        return None


def sleep_ms(ms):
    if ms > 0:
        time.sleep(ms / 1000.0)


def measure_temp_mean():
    """Average several thermistor readings before publishing/control."""
    global last_temp_sample_count

    readings = []
    sample_count = max(1, int(TEMP_AVERAGE_SAMPLES))
    sample_delay_ms = max(0, int(TEMP_AVERAGE_SAMPLE_DELAY_MS))

    for i in range(sample_count):
        temp = measure_temp()
        if temp is not None:
            readings.append(temp)

        if i < sample_count - 1:
            sleep_ms(sample_delay_ms)

    last_temp_sample_count = len(readings)
    if not readings:
        return None
    return sum(readings) / len(readings)


def measure_od():
    """Read the light sensor. LED is controlled separately via db4/led/set."""
    return read_sensor()


def set_pump_output(pump, on):
    if on and not pump.is_on():
        pump.on()
    elif not on and pump.is_on():
        pump.off()


def pump_state(pump):
    return "on" if pump.is_on() else "off"


def publish_text(topic, value):
    client.publish(topic, str(value).encode())


def publish_float(topic, value, digits=2):
    if value is None:
        client.publish(topic, b"None")
    else:
        publish_text(topic, ("{:." + str(digits) + "f}").format(value))


def apply_cooling_output(output_percent, now_ms):
    global cooling_window_started_ms

    output_percent = max(0.0, min(100.0, output_percent))
    if COOLING_PUMP_USE_PWM:
        pump2.set_speed(output_percent)
        return

    if output_percent <= 0:
        set_pump_output(pump2, False)
        return
    if output_percent >= 100:
        set_pump_output(pump2, True)
        return

    window_ms = int(COOLING_CONTROL_WINDOW_SECONDS * 1000)
    if window_ms <= 0:
        window_ms = 30000

    if cooling_window_started_ms == 0:
        cooling_window_started_ms = now_ms

    elapsed_ms = time.ticks_diff(now_ms, cooling_window_started_ms)
    if elapsed_ms < 0 or elapsed_ms >= window_ms:
        cooling_window_started_ms = now_ms
        elapsed_ms = 0

    on_ms = int(window_ms * output_percent / 100.0)
    set_pump_output(pump2, elapsed_ms < on_ms)


def update_temperature_control(temp, now_ms):
    global cooling_output_percent

    if cool_mode == "auto":
        cooling_output_percent = temp_pid.update(temp, now_ms, pump1.is_on())
        apply_cooling_output(cooling_output_percent, now_ms)
    elif cool_mode == "on":
        cooling_output_percent = 100.0
        temp_pid.status = "FORCED_ON"
        set_pump_output(pump2, True)
    else:
        cooling_output_percent = 0.0
        temp_pid.status = "OFF"
        set_pump_output(pump2, False)


def publish_temperature_control_state():
    snap = temp_pid.snapshot()
    publish_text(b"db4/cool/mode", cool_mode)
    publish_text(b"db4/temp/control/status", snap["status"])
    publish_float(b"db4/temp/control/setpoint", snap["setpoint"], 2)
    publish_float(b"db4/temp/control/predicted", snap["predicted_temp"], 2)
    publish_float(b"db4/temp/control/filtered", snap["filtered_temp"], 2)
    publish_float(b"db4/temp/control/rate_c_per_min", snap["rate_c_per_min"], 4)
    publish_float(b"db4/temp/control/output", cooling_output_percent, 1)
    publish_float(b"db4/temp/control/feed_forward", snap["feed_forward_percent"], 1)
    publish_text(b"db4/temp/control/sample_count", last_temp_sample_count)


def apply_feed_mode():
    if feed_mode == "on":
        set_pump_output(pump1, True)
    else:
        set_pump_output(pump1, False)


def feed_status():
    if feed_mode == "on":
        return "FORCED_ON"
    if feed_mode == "auto":
        return "AUTO_IDLE"
    return "OFF"


def publish_feed_control_state():
    publish_text(b"db4/feed/mode", feed_mode)
    publish_text(b"db4/feed/status", feed_status())


def on_command(topic, msg):
    """Handle control commands from the dashboard."""
    global led_on, cool_mode, feed_mode, cooling_window_started_ms
    cmd = msg.decode().strip()
    if topic == b"db4/pump1/set":
        if cmd == "on":
            feed_mode = "on"
            pump1.on()
            client.publish(b"db4/pump1/state", b"on")
        elif cmd == "off":
            feed_mode = "off"
            pump1.off()
            client.publish(b"db4/pump1/state", b"off")
    elif topic == b"db4/feed/mode/set":
        if cmd in ("auto", "on", "off"):
            feed_mode = cmd
            apply_feed_mode()
    elif topic == b"db4/pump2/set":
        if cmd == "on":
            cool_mode = "on"
            pump2.on()
            client.publish(b"db4/pump2/state", b"on")
            publish_text(b"db4/cool/mode", cool_mode)
        elif cmd == "off":
            cool_mode = "off"
            pump2.off()
            client.publish(b"db4/pump2/state", b"off")
            publish_text(b"db4/cool/mode", cool_mode)
    elif topic in (b"db4/cool/mode/set", b"db4/temp/control/mode/set"):
        if cmd in ("auto", "on", "off"):
            cool_mode = cmd
            cooling_window_started_ms = 0
            temp_pid.reset()
            publish_text(b"db4/cool/mode", cool_mode)
    elif topic == b"db4/led/set":
        if cmd == "on":
            set_blue_brightness(LED_ON_BRIGHTNESS)
            led_on = True
            client.publish(b"db4/led/state", b"on")
        elif cmd == "off":
            set_blue_brightness(0)
            led_on = False
            client.publish(b"db4/led/state", b"off")


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
from temp_pid import TemperaturePID
from temperature import read_temperature
from light_sensor import init_sensor, read_sensor
from led_sensor_combined import set_blue_brightness

pump1 = Pump(pin=32, use_pwm=False)
pump2 = Pump(pin=27, use_pwm=COOLING_PUMP_USE_PWM, freq=COOLING_PWM_FREQ)
temp_pid = TemperaturePID(
    setpoint_c=TEMP_SETPOINT_C,
    min_c=TEMP_MIN_C,
    max_c=TEMP_MAX_C,
    kp=TEMP_PID_KP,
    ki=TEMP_PID_KI,
    kd=TEMP_PID_KD,
    deadband_c=TEMP_PID_DEADBAND_C,
    filter_alpha=TEMP_FILTER_ALPHA,
    prediction_horizon_s=TEMP_PREDICTION_HORIZON_SECONDS,
    feed_temp_rise_c=TEMP_FEED_TEMP_RISE_C,
    feed_forward_percent=TEMP_FEED_FORWARD_PERCENT,
)
set_blue_brightness(LED_ON_BRIGHTNESS)  # LED defaults to on at boot

try:
    init_sensor()
except OSError as e:
    print(f"Light sensor init failed: {e} - OD will read None until sensor is fixed")

client.set_callback(on_command)
client.subscribe(b"db4/pump1/set")
client.subscribe(b"db4/feed/mode/set")
client.subscribe(b"db4/pump2/set")
client.subscribe(b"db4/cool/mode/set")
client.subscribe(b"db4/temp/control/mode/set")
client.subscribe(b"db4/led/set")
client.subscribe(b"db4/control/#")

while True:
    loop_started_ms = time.ticks_ms()
    client.check_msg()           # non-blocking: handle incoming commands
    temp = measure_temp_mean()
    now_ms = time.ticks_ms()
    od = measure_od()
    update_temperature_control(temp, now_ms)
    gc.collect()
    publish_text(b"db4/temperature", temp)
    publish_text(b"db4/od", od)
    publish_text(b"db4/pump1/state", pump_state(pump1))
    publish_text(b"db4/pump2/state", pump_state(pump2))
    publish_text(b"db4/led/state", "on" if led_on else "off")
    publish_feed_control_state()
    publish_temperature_control_state()
    elapsed_ms = time.ticks_diff(time.ticks_ms(), loop_started_ms)
    sleep_ms(max(0, int(TEMP_REPORT_INTERVAL_MS) - elapsed_ms))
