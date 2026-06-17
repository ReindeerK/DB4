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
