# Copy this file to controller_config.py, fill in your real values, then upload
# controller_config.py to the ESP32 next to controller.py.

WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"

MQTT_HOST = "your-mqtt-broker-host"
MQTT_PORT = 8883
MQTT_USER = b"your-mqtt-username"
MQTT_PASSWORD = b"your-mqtt-password"
MQTT_TLS = True
MQTT_SSL_PARAMS = {"server_hostname": MQTT_HOST} if MQTT_TLS else {}

# Temperature regulation. The controller cools toward 17.5 C and treats
# 17.0-18.0 C as the safe operating band.
TEMP_CONTROL_MODE = "auto"  # auto, off, or on
FEED_CONTROL_MODE = "off"  # auto, off, or on
TEMP_SETPOINT_C = 17.5
TEMP_MIN_C = 17.0
TEMP_MAX_C = 18.0

# Conservative defaults for a slow water tank. Tune from logged data.
TEMP_PID_KP = 35.0
TEMP_PID_KI = 0.015
TEMP_PID_KD = 0.0
TEMP_PID_DEADBAND_C = 0.05
TEMP_FILTER_ALPHA = 0.35
TEMP_PREDICTION_HORIZON_SECONDS = 90.0

# Published temperature is the mean of several thermistor conversions taken
# across each reporting interval.
TEMP_REPORT_INTERVAL_MS = 2000
TEMP_AVERAGE_SAMPLES = 12
TEMP_AVERAGE_SAMPLE_DELAY_MS = 120
TEMP_DEBUG_READINGS = False
TEMP_OFFSET_C = 0.0

# Feed-forward compensation while the algae feed pump is running.
TEMP_FEED_TEMP_RISE_C = 0.20
TEMP_FEED_FORWARD_PERCENT = 15.0

# The coolant loop can use real PWM, or slow time-proportional on/off control.
COOLING_PUMP_USE_PWM = False
COOLING_PWM_FREQ = 1000
COOLING_CONTROL_WINDOW_SECONDS = 30
