# Copy this file to controller_config.py, fill in your real values, then upload
# controller_config.py to the ESP32 next to controller.py.

WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"

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
# Keep AUTO disabled on boot until the MEASURE values below are filled in.
AUTO_FEED_ENABLED_ON_BOOT = False

# MODEL / DESIGN TARGET:
# Desired algae concentration in the mussel tank.
# Unit: cells/mL.
#
# This value comes from the final model simulation. Earlier notebook cells used
# 1338 cells/mL, while the later coupled-system simulation used 2000 cells/mL.
# The current controller default uses the later value: 2000 cells/mL.
#
# Change this if your final chosen biological target is different.
FEED_TARGET_CONCENTRATION = 2000.0

# ASSUMED CONTROL BAND:
# The controller does not try to hold exactly one value. It keeps concentration
# in a band to avoid rapid pump on/off switching.
#
# With target = 2000:
# - low threshold  = 0.90 * 2000 = 1800 cells/mL
# - high threshold = 1.10 * 2000 = 2200 cells/mL
#
# If concentration is below the low threshold, AUTO doses algae.
# If concentration is above the high threshold, AUTO keeps the pump off.
FEED_LOW_FRACTION = 0.90
FEED_HIGH_FRACTION = 1.10

# MEASURE / MODEL INPUT:
# Actual water volume in the mussel tank.
# Unit: liters.
#
# The notebook assumes 4.0 L. Change this to the real filled water volume,
# not the nominal tank size.
TANK_VOLUME_L = 4.0

# MEASURE:
# Algae concentration in the algae/feed stock tank.
# Unit: cells/mL.
#
# The notebook used 250000 cells/mL as a dense algae stock example.
# This should be measured with cell counts or a calibrated OD reading.
# The dosing equation depends strongly on this value.
ALGAE_STOCK_CONCENTRATION = 250000.0

# MEASURE / MODEL INPUT:
# Number of mussels currently in the mussel tank.
# Unit: count.
#
# The coupled-system notebook simulation used 4 mussels.
# Change this whenever the number of mussels changes.
N_MUSSELS = 4

# MODEL / MEASURE:
# Clearance rate per mussel.
# Unit: liters per mussel per hour.
#
# This is the key biological parameter in the model:
#     grazing_coefficient = N_MUSSELS * MUSSEL_CLEARANCE_RATE_L_H / TANK_VOLUME_L
#
# The notebook tried values such as 2.5 and 3.46 L/h. The current default is
# 2.5 L/h because that was used in the final coupled-system simulations.
#
# Best practice: measure this with a closed-tank decline experiment:
# record algae concentration at two times with no feeding, then calculate
# clearance from the exponential drop.
MUSSEL_CLEARANCE_RATE_L_H = 2.5

# MODEL / ASSUMED:
# Algae growth rate in the mussel tank.
# Unit: 1/hour.
#
# The notebook used 0.035 1/h. In the controller this only affects prediction
# helpers/status math; the actual dosing decision is based on live OD readings.
# You can leave this value unless you are refining the biological model.
ALGAE_GROWTH_RATE_H = 0.035

# ---------------------------------------------------------------------------
# Pump and dosing calibration
# ---------------------------------------------------------------------------

# MEASURE / ELECTRICAL:
# Set True only if your pump driver turns ON when the ESP32 output pin is LOW.
# Most simple driver wiring is active-high, so False is the normal value.
FEED_PUMP_ACTIVE_LOW = False

# MEASURE / PRODUCT DATASHEET STARTING POINT:
# Feed pump flow rate at the actual voltage, tubing, and height difference.
# Unit: mL/min.
#
# Your current pump is the DFRobot FIT0800 amphibious/submersible pump.
# The vendor lists:
# - voltage: 3-6 V
# - flow: 80-100 L/h
# - lift/head: 25-45 cm
# - power: 0.4-2 W
#
# 80-100 L/h is about 1330-1670 mL/min at ideal/free-flow conditions.
# At 5 V, 1500 mL/min is a reasonable FIRST ESTIMATE, but it is not a final
# calibration value. Real flow can change a lot with tube diameter, vertical
# lift, restrictions, algae viscosity, and water level.
#
# Measure this gravimetrically:
# 1. Run the feed pump for a short known time, e.g. 5-10 s.
# 2. Collect the pumped water.
# 3. Weigh it in grams. For water, grams ~= mL.
# 4. flow = collected_mL / minutes.
#
# Important: this pump is much faster than a peristaltic dosing pump. If your
# calculated algae doses are only a few mL, pump pulses will be very short and
# less precise. For fine dosing, use diluted algae stock, a lower-flow pump, a
# restriction valve, PWM, or a peristaltic pump.
FEED_PUMP_FLOW_ML_MIN = 1500.0

# SAFETY:
# Minimum pump pulse.
#
# With this pump, 0.10 s at 1500 mL/min is already about 2.5 mL. If the pump
# does not start reliably at 0.10 s, increase this value and/or dilute the
# algae stock so each dose can be physically larger.
MIN_FEED_PUMP_SECONDS = 0.10

# SAFETY:
# Maximum single dose duration. This prevents a bad sensor reading from
# running the pump for a very long time.
#
# With FEED_PUMP_FLOW_ML_MIN = 1500, 2 s means at most about 50 mL per dose.
MAX_FEED_PUMP_SECONDS = 2.0

# SAFETY:
# Minimum wait after starting one dose before another new dose may begin.
# Unit: seconds.
FEED_DOSE_COOLDOWN_SECONDS = 30

# SAFETY:
# If the controller has not received a usable OD-derived concentration within
# this time, AUTO refuses to dose and reports NO_OD.
# Unit: seconds.
FEED_SENSOR_STALE_SECONDS = 120

# SOFTWARE TIMING:
# Delay between full sensor/control cycles.
#
# The controller has special handling for short feed pulses, so the pump can
# turn off before this delay finishes. The OD sensor itself still takes time to
# average samples, so concentration feedback is not instantaneous.
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
#
# There are two supported calibration styles.

# MEASURE:
# "linear" means:
#     concentration = OD_LINEAR_SLOPE * raw_count + OD_LINEAR_INTERCEPT
#
# Use this if your calibration curve was fit directly from raw LTR-329 counts
# to known cell concentrations.
OD_CALIBRATION_MODE = "linear"

# MEASURE:
# Placeholder values. With slope=1 and intercept=0, raw sensor counts are
# treated as cells/mL, which is almost certainly not physically correct.
# Replace these with your calibration fit before using AUTO.
OD_LINEAR_SLOPE = 1.0
OD_LINEAR_INTERCEPT = 0.0

# MEASURE:
# "absorbance" mode means:
#     absorbance = log10(OD_BLANK_RAW / raw_count)
#     concentration = OD_ABSORBANCE_SLOPE * absorbance
#                     + OD_ABSORBANCE_INTERCEPT
#
# This is usually better for optical-density measurements, because algae reduce
# transmitted light. To use it, set:
#     OD_CALIBRATION_MODE = "absorbance"
#
# OD_BLANK_RAW is the raw sensor reading for clean water / no algae with the
# same LED brightness and sensor geometry.
OD_BLANK_RAW = 65000.0

# MEASURE:
# Placeholder absorbance calibration fit. Replace with your dilution-series fit
# if you use absorbance mode.
OD_ABSORBANCE_SLOPE = 1.0
OD_ABSORBANCE_INTERCEPT = 0.0
