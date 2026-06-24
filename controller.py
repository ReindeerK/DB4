# controller.py on the ESP32
import gc
import os
import time
import network
import controller_config as config
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
from algae_controller import AlgaeFeedingController


def cfg(name, default):
    return getattr(config, name, default)


LED_ON_BRIGHTNESS = 255
WIFI_CONNECT_TIMEOUT_SECONDS = 15
WIFI_RETRY_DELAY_SECONDS = 5
WIFI_ENABLED = cfg("WIFI_ENABLED", True)
WIFI_MAX_ATTEMPTS = cfg("WIFI_MAX_ATTEMPTS", 2)
MQTT_ENABLED = cfg("MQTT_ENABLED", True)
CSV_LOG_ENABLED = cfg("CSV_LOG_ENABLED", True)
CSV_LOG_PATH = cfg("CSV_LOG_PATH", "measurements.csv")
CSV_LOG_INTERVAL_SECONDS = cfg("CSV_LOG_INTERVAL_SECONDS", 0)
CSV_LOG_FLUSH_EVERY_ROWS = cfg("CSV_LOG_FLUSH_EVERY_ROWS", 1)
TEMP_SETPOINT_C = cfg("TEMP_SETPOINT_C", 17.5)
TEMP_MIN_C = cfg("TEMP_MIN_C", 17.0)
TEMP_MAX_C = cfg("TEMP_MAX_C", 18.0)
TEMP_PID_KP = cfg("TEMP_PID_KP", 35.0)
TEMP_PID_KI = cfg("TEMP_PID_KI", 0.015)
TEMP_PID_KD = cfg("TEMP_PID_KD", 0.0)
TEMP_PID_DEADBAND_C = cfg("TEMP_PID_DEADBAND_C", 0.05)
TEMP_FILTER_ALPHA = cfg("TEMP_FILTER_ALPHA", 0.35)
TEMP_PREDICTION_HORIZON_SECONDS = cfg("TEMP_PREDICTION_HORIZON_SECONDS", 90.0)
TEMP_FEED_TEMP_RISE_C = cfg("TEMP_FEED_TEMP_RISE_C", 0.20)
TEMP_FEED_FORWARD_PERCENT = cfg("TEMP_FEED_FORWARD_PERCENT", 15.0)
TEMP_REPORT_INTERVAL_MS = cfg("TEMP_REPORT_INTERVAL_MS", 2000)
TEMP_AVERAGE_SAMPLES = cfg("TEMP_AVERAGE_SAMPLES", 12)
TEMP_AVERAGE_SAMPLE_DELAY_MS = cfg("TEMP_AVERAGE_SAMPLE_DELAY_MS", 120)
TEMP_CONTROL_MODE = cfg("TEMP_CONTROL_MODE", "auto")
COOLING_PUMP_USE_PWM = cfg("COOLING_PUMP_USE_PWM", False)
COOLING_PWM_FREQ = cfg("COOLING_PWM_FREQ", 1000)
COOLING_CONTROL_WINDOW_SECONDS = cfg("COOLING_CONTROL_WINDOW_SECONDS", 30)
CONTROL_LOOP_DELAY_SECONDS = cfg(
    "CONTROL_LOOP_DELAY_SECONDS",
    max(0.0, float(TEMP_REPORT_INTERVAL_MS) / 1000.0),
)

client = MQTTClient(
    b"esp32_db4",
    MQTT_HOST,
    port=MQTT_PORT,
    user=MQTT_USER,
    password=MQTT_PASSWORD,
    ssl=MQTT_TLS,
    ssl_params=MQTT_SSL_PARAMS,
)
mqtt_connected = False
csv_log_file = None
csv_log_rows_since_flush = 0
last_csv_log_s = None
led_on = True
pump1 = None
pump2 = None
temp_pid = None
feed_controller = None
cool_mode = TEMP_CONTROL_MODE
cooling_window_started_ms = 0
cooling_output_percent = 0.0
last_temp_sample_count = 0
last_feed_pump_on = None


def sleep_ms(ms):
    if ms > 0:
        time.sleep(ms / 1000.0)


def measure_temp():
    """Read temperature in Celsius from the thermistor, or None if out of range."""
    try:
        return read_temperature()
    except Exception as e:
        print(f"Temperature read failed: {e}")
        return None


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


def mqtt_connect():
    global mqtt_connected
    if not MQTT_ENABLED:
        print("MQTT disabled")
        mqtt_connected = False
        return False
    try:
        client.connect()
        mqtt_connected = True
        print("MQTT connected")
        return True
    except Exception as e:
        mqtt_connected = False
        print(f"MQTT connect failed: {e}")
        return False


def mqtt_publish(topic, payload):
    global mqtt_connected
    if not mqtt_connected:
        return
    try:
        client.publish(topic, payload)
    except Exception as e:
        mqtt_connected = False
        print(f"MQTT publish failed: {e}")


def mqtt_check_msg():
    global mqtt_connected
    if not mqtt_connected:
        return
    try:
        client.check_msg()
    except Exception as e:
        mqtt_connected = False
        print(f"MQTT check failed: {e}")


def mqtt_subscribe(topic):
    global mqtt_connected
    if not mqtt_connected:
        return
    try:
        client.subscribe(topic)
    except Exception as e:
        mqtt_connected = False
        print(f"MQTT subscribe failed: {e}")


def publish_text(topic, value):
    mqtt_publish(topic, str(value).encode())


def publish_float(topic, value, digits=2):
    if value is None:
        mqtt_publish(topic, b"None")
    else:
        publish_text(topic, ("{:." + str(digits) + "f}").format(value))


def set_feed_pump(on):
    global last_feed_pump_on

    on = bool(on)
    if on == last_feed_pump_on:
        return

    drive_high = not on if cfg("FEED_PUMP_ACTIVE_LOW", False) else on
    if drive_high:
        pump1.on()
    else:
        pump1.off()

    last_feed_pump_on = on
    mqtt_publish(b"db4/pump1/state", b"on" if on else b"off")


def publish_feed_telemetry(concentration):
    telemetry = feed_controller.telemetry()
    publish_text(b"db4/feed/mode", telemetry["mode"])
    publish_text(b"db4/feed/status", telemetry["status"])
    publish_text(b"db4/feed/target", telemetry["target"])
    publish_text(b"db4/feed/low", telemetry["low"])
    publish_text(b"db4/feed/high", telemetry["high"])
    publish_text(b"db4/feed/dose_ml", telemetry["dose_ml"])
    publish_text(b"db4/feed/pump_seconds", telemetry["pump_seconds"])
    publish_text(b"db4/feed/grazing_coefficient", telemetry["grazing_coefficient"])
    if concentration is not None:
        publish_text(b"db4/feed/concentration", concentration)
        publish_text(b"db4/cell", concentration)


def csv_cell(value):
    if value is None:
        return ""
    return str(value)


def csv_file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def init_csv_logger():
    global csv_log_file
    if not CSV_LOG_ENABLED:
        print("CSV logging disabled")
        return

    try:
        needs_header = not csv_file_exists(CSV_LOG_PATH)
        csv_log_file = open(CSV_LOG_PATH, "a")
        if needs_header:
            csv_log_file.write(
                "elapsed_ms,epoch_s,temperature_c,od_raw,concentration,"
                "feed_pump_started,pump1_on,pump2_on,feed_mode,feed_status,"
                "feed_dose_ml,feed_pump_seconds,cool_mode,cool_status,"
                "cool_output_percent,led_on,temp_sample_count,mqtt_connected\n"
            )
            csv_log_file.flush()
        print("CSV logging to", CSV_LOG_PATH)
    except Exception as e:
        csv_log_file = None
        print(f"CSV logger failed: {e}")


def log_measurement_csv(temp, od, concentration, feed_pump_started):
    global csv_log_rows_since_flush, last_csv_log_s
    if csv_log_file is None:
        return

    now_s = time.time()
    interval_s = float(CSV_LOG_INTERVAL_SECONDS)
    if (
        interval_s > 0
        and last_csv_log_s is not None
        and (now_s - last_csv_log_s) < interval_s
    ):
        return

    telemetry = feed_controller.telemetry()
    snap = temp_pid.snapshot()
    row = [
        time.ticks_ms(),
        now_s,
        temp,
        od,
        concentration,
        feed_pump_started,
        last_feed_pump_on,
        pump_state(pump2),
        telemetry["mode"],
        telemetry["status"],
        telemetry["dose_ml"],
        telemetry["pump_seconds"],
        cool_mode,
        snap["status"],
        cooling_output_percent,
        led_on,
        last_temp_sample_count,
        mqtt_connected,
    ]

    try:
        csv_log_file.write(",".join(csv_cell(value) for value in row) + "\n")
        csv_log_rows_since_flush += 1
        last_csv_log_s = now_s
        if csv_log_rows_since_flush >= int(CSV_LOG_FLUSH_EVERY_ROWS):
            csv_log_file.flush()
            csv_log_rows_since_flush = 0
    except Exception as e:
        print(f"CSV write failed: {e}")


def finish_short_feed_pulse(started):
    """Turn off a timed auto-feed pulse before slower loop work runs."""
    if not started or feed_controller.pump_until_s is None:
        return

    remaining_s = feed_controller.pump_until_s - time.time()
    if remaining_s > 0:
        time.sleep(remaining_s)

    set_feed_pump(False)
    feed_controller.pump_until_s = None
    if feed_controller.status in ("DOSING", "MAX_INTERVAL_DOSING"):
        feed_controller.status = "DOSE_COMPLETE"


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


def update_temperature_control(temp, now_ms, feed_pump_on=None):
    global cooling_output_percent

    if cool_mode == "auto":
        if feed_pump_on is None:
            feed_pump_on = last_feed_pump_on
        cooling_output_percent = temp_pid.update(temp, now_ms, feed_pump_on)
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


def on_command(topic, msg):
    """Handle control commands from the dashboard."""
    global led_on, cool_mode, cooling_window_started_ms

    cmd = msg.decode().strip()
    if topic == b"db4/pump1/set":
        if cmd == "on":
            feed_controller.set_mode("on", time.time())
            set_feed_pump(True)
        elif cmd == "off":
            feed_controller.set_mode("off", time.time())
            set_feed_pump(False)
        publish_feed_telemetry(feed_controller.last_concentration)
    elif topic in (b"db4/feed/mode/set", b"db4/control/feed/set"):
        if feed_controller.set_mode(cmd, time.time()):
            if cmd == "off":
                set_feed_pump(False)
            elif cmd == "on":
                set_feed_pump(True)
            publish_feed_telemetry(feed_controller.last_concentration)
    elif topic == b"db4/pump2/set":
        if cmd == "on":
            cool_mode = "on"
            cooling_window_started_ms = 0
            set_pump_output(pump2, True)
            publish_text(b"db4/pump2/state", "on")
            publish_text(b"db4/cool/mode", cool_mode)
        elif cmd == "off":
            cool_mode = "off"
            cooling_window_started_ms = 0
            set_pump_output(pump2, False)
            publish_text(b"db4/pump2/state", "off")
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
            mqtt_publish(b"db4/led/state", b"on")
        elif cmd == "off":
            set_blue_brightness(0)
            led_on = False
            mqtt_publish(b"db4/led/state", b"off")


def connect_wifi():
    if not WIFI_ENABLED:
        print("WiFi disabled; running offline")
        return None

    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)

    attempt = 1
    max_attempts = int(WIFI_MAX_ATTEMPTS)
    while not wlan.isconnected() and (max_attempts <= 0 or attempt <= max_attempts):
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

    if not wlan.isconnected():
        print("WiFi unavailable; continuing offline")
        return wlan

    print("WiFi already connected:", wlan.ifconfig())
    return wlan


wlan = connect_wifi()

# Connect MQTT before importing heavier hardware modules. The TLS handshake
# needs a large temporary allocation on the ESP32.
gc.collect()
if wlan is not None and wlan.isconnected():
    mqtt_connect()
else:
    print("Skipping MQTT because WiFi is offline")
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
feed_controller = AlgaeFeedingController(
    target_concentration=cfg("FEED_TARGET_CONCENTRATION", 1338.0),
    tank_volume_l=cfg("TANK_VOLUME_L", 4.0),
    stock_concentration=cfg("ALGAE_STOCK_CONCENTRATION", 200000.0),
    pump_flow_ml_min=cfg("FEED_PUMP_FLOW_ML_MIN", 1500.0),
    low_fraction=cfg("FEED_LOW_FRACTION", 0.90),
    high_fraction=cfg("FEED_HIGH_FRACTION", 1.10),
    mussel_count=cfg("N_MUSSELS", 4),
    clearance_rate_l_h=cfg("MUSSEL_CLEARANCE_RATE_L_H", 3.5),
    algae_growth_rate_h=cfg("ALGAE_GROWTH_RATE_H", 0.035),
    min_pump_seconds=cfg("MIN_FEED_PUMP_SECONDS", 0.10),
    max_pump_seconds=cfg("MAX_FEED_PUMP_SECONDS", 2.0),
    dose_cooldown_seconds=cfg("FEED_DOSE_COOLDOWN_SECONDS", 600),
    max_dose_cooldown_seconds=cfg("FEED_MAX_COOLDOWN_SECONDS", 900),
    sensor_stale_seconds=cfg("FEED_SENSOR_STALE_SECONDS", 120),
    od_mode=cfg("OD_CALIBRATION_MODE", "linear"),
    od_linear_slope=cfg("OD_LINEAR_SLOPE", -72.223),
    od_linear_intercept=cfg("OD_LINEAR_INTERCEPT", 3000000.0),
    od_blank_raw=cfg("OD_BLANK_RAW", 45000.0),
    od_absorbance_slope=cfg("OD_ABSORBANCE_SLOPE", 1.0),
    od_absorbance_intercept=cfg("OD_ABSORBANCE_INTERCEPT", 0.0),
    enabled=cfg("AUTO_FEED_ENABLED_ON_BOOT", True),
)
set_feed_pump(False)
init_csv_logger()

try:
    init_sensor()
except OSError as e:
    print(f"Light sensor init failed: {e} - OD will read None until sensor is fixed")

client.set_callback(on_command)
mqtt_subscribe(b"db4/pump1/set")
mqtt_subscribe(b"db4/pump2/set")
mqtt_subscribe(b"db4/feed/mode/set")
mqtt_subscribe(b"db4/cool/mode/set")
mqtt_subscribe(b"db4/temp/control/mode/set")
mqtt_subscribe(b"db4/led/set")
mqtt_subscribe(b"db4/control/#")
publish_feed_telemetry(None)
publish_text(b"db4/cool/mode", cool_mode)

while True:
    loop_started_ms = time.ticks_ms()
    mqtt_check_msg()

    temp = measure_temp_mean()
    now_ms = time.ticks_ms()
    od = measure_od()
    concentration = feed_controller.concentration_from_od(od)
    desired_feed_pump = feed_controller.update(concentration, time.time())
    set_feed_pump(desired_feed_pump)
    finish_short_feed_pulse(desired_feed_pump)
    update_temperature_control(temp, now_ms, desired_feed_pump)
    log_measurement_csv(temp, od, concentration, desired_feed_pump)

    gc.collect()
    publish_text(b"db4/temperature", temp)
    publish_text(b"db4/od", od)
    publish_feed_telemetry(concentration)
    publish_text(b"db4/pump1/state", "on" if last_feed_pump_on else "off")
    publish_text(b"db4/pump2/state", pump_state(pump2))
    publish_text(b"db4/led/state", "on" if led_on else "off")
    publish_temperature_control_state()

    elapsed_s = time.ticks_diff(time.ticks_ms(), loop_started_ms) / 1000.0
    time.sleep(max(0.0, float(CONTROL_LOOP_DELAY_SECONDS) - elapsed_s))
