# Copy this file to controller_config.py, fill in your real values, then upload
# controller_config.py to the ESP32 next to controller.py.

WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"
WIFI_ENABLED = True
WIFI_MAX_ATTEMPTS = 2

# For WPA2-Enterprise networks such as DTUsecure/eduroam, set:
# WIFI_SSID = "DTUsecure"
# WIFI_ENTERPRISE = True
# WIFI_USERNAME = "your-dtu-username"
# WIFI_IDENTITY = WIFI_USERNAME
# WIFI_PASSWORD = "your-dtu-password"

MQTT_HOST = "your-mqtt-broker-host"
MQTT_PORT = 8883
MQTT_USER = b"your-mqtt-username"
MQTT_PASSWORD = b"your-mqtt-password"
MQTT_TLS = True
MQTT_SSL_PARAMS = {"server_hostname": MQTT_HOST} if MQTT_TLS else {}
MQTT_ENABLED = True

# Offline backup logging on the ESP32 filesystem. Set WIFI_ENABLED = False for
# unattended offline runs; autonomous control and CSV logging will still run.
CSV_LOG_ENABLED = True
CSV_LOG_PATH = "measurements.csv"
CSV_LOG_INTERVAL_SECONDS = 0  # 0 logs every full control loop
CSV_LOG_FLUSH_EVERY_ROWS = 1

# Temperature regulation. The controller cools toward 17.5 C and treats
# 17.0-18.0 C as the safe operating band.
TEMP_CONTROL_MODE = "auto"  # auto, off, or on
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

# ---------------------------------------------------------------------------
# Autonomous algae feeding
# ---------------------------------------------------------------------------
#
# This section is the bridge between the Jupyter notebook model and the ESP32
# control loop. The controller uses these values to:
#
# 1. Convert OD sensor readings into algae concentration.
# 2. Compare that concentration with the desired feeding band.
# 3. Calculate how much algae stock water to pump into the mussel tank.
# 4. Convert that dose volume into pump-on time.
#
# Values marked "MODEL" are taken from the mathematical model/notebook.
# Values marked "MEASURE" must be measured on the real setup.
# Values marked "ASSUMED" are safe starting guesses, but should be validated.
# Values marked "SAFETY" limit what the software is allowed to do.
#
# AUTO can start on boot now that the measured values below are filled in.
AUTO_FEED_ENABLED_ON_BOOT = True

# MODEL / DESIGN TARGET:
# Desired algae concentration in the mussel tank.
# Unit: cells/mL.
#
# Measured/final selected biological target.
FEED_TARGET_CONCENTRATION = 1338.0

# ASSUMED CONTROL BAND:
# The controller does not try to hold exactly one value. It keeps concentration
# in a band to avoid rapid pump on/off switching.
FEED_LOW_FRACTION = 0.90
FEED_HIGH_FRACTION = 1.10

# MEASURE / MODEL INPUT:
# Actual water volume in the mussel tank.
# Unit: liters.
TANK_VOLUME_L = 4.0

# MEASURE:
# Algae concentration in the algae/feed stock tank.
# Unit: cells/mL.
ALGAE_STOCK_CONCENTRATION = 200000.0

# MEASURE / MODEL INPUT:
# Number of mussels currently in the mussel tank.
# Unit: count.
N_MUSSELS = 4

# MODEL / MEASURE:
# Clearance rate per mussel.
# Unit: liters per mussel per hour.
MUSSEL_CLEARANCE_RATE_L_H = 3.5

# MODEL / ASSUMED:
# Algae growth rate in the mussel tank.
# Unit: 1/hour.
ALGAE_GROWTH_RATE_H = 0.035

# ---------------------------------------------------------------------------
# Pump and dosing calibration
# ---------------------------------------------------------------------------

# MEASURE / ELECTRICAL:
# Set True only if your pump driver turns ON when the ESP32 output pin is LOW.
FEED_PUMP_ACTIVE_LOW = False

# MEASURE / PRODUCT DATASHEET STARTING POINT:
# Feed pump flow rate at the actual voltage, tubing, and height difference.
# Unit: mL/min.
#
# The DFRobot FIT0800 pump is listed around 80-100 L/h, or about
# 1330-1670 mL/min, under ideal/free-flow conditions. Measure the real flow
# through your tubing before enabling automatic dosing.
FEED_PUMP_FLOW_ML_MIN = 1500.0

# SAFETY:
# Minimum pump pulse. At 1500 mL/min, 0.10 s is already about 2.5 mL.
MIN_FEED_PUMP_SECONDS = 0.10

# SAFETY:
# Maximum single dose duration. This prevents a bad sensor reading from
# running the pump for a very long time.
MAX_FEED_PUMP_SECONDS = 2.0

# SAFETY:
# Minimum wait after starting one dose before another new dose may begin.
# Unit: seconds. The mathematical feeding model uses a 10-minute interval.
FEED_DOSE_COOLDOWN_SECONDS = 600

# SAFETY / SCHEDULE:
# Maximum wait between automatic feed doses when concentration is not above the
# high threshold. After this interval the controller gives a minimum pulse.
# Unit: seconds.
FEED_MAX_COOLDOWN_SECONDS = 900

# SAFETY:
# If the controller has not received a usable OD-derived concentration within
# this time, AUTO refuses to dose and reports NO_OD.
# Unit: seconds.
FEED_SENSOR_STALE_SECONDS = 120

# SOFTWARE TIMING:
# Delay between full sensor/control cycles. The controller has special handling
# for short feed pulses, so the pump can turn off before this delay finishes.
CONTROL_LOOP_DELAY_SECONDS = 2

# ---------------------------------------------------------------------------
# OD sensor calibration
# ---------------------------------------------------------------------------
#
# The controller needs concentration in cells/mL, but the LTR-329 gives raw
# light counts. These constants define that conversion.
#
# You must calibrate this with a dilution series:
# - known algae concentration in cells/mL
# - matching raw sensor reading

# "linear" means:
#     concentration = OD_LINEAR_SLOPE * raw_count + OD_LINEAR_INTERCEPT
OD_CALIBRATION_MODE = "linear"

# Placeholder values. Replace these with your calibration fit before using AUTO.
OD_LINEAR_SLOPE = -72.223
OD_LINEAR_INTERCEPT = 3000000.0

# "absorbance" mode means:
#     absorbance = log10(OD_BLANK_RAW / raw_count)
#     concentration = OD_ABSORBANCE_SLOPE * absorbance
#                     + OD_ABSORBANCE_INTERCEPT
OD_BLANK_RAW = 45000.0
OD_ABSORBANCE_SLOPE = 1.0
OD_ABSORBANCE_INTERCEPT = 0.0
