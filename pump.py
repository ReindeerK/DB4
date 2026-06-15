# main.py on the ESP32
import time, network
from umqtt.robust import MQTTClient
from pump import Pump

BROKER_IP = "192.168.1.105"  # your laptop IP
pump = Pump(pin=33, use_pwm=False)
client = MQTTClient("esp32_db4", BROKER_IP)

def on_command(topic, msg):
    """Handle control commands from the dashboard."""
    cmd = msg.decode().strip()
    if topic == b"db4/pump/set":
        if cmd == "on":
            pump.on()
            client.publish(b"db4/pump/state", b"on")
        elif cmd == "off":
            pump.off()
            client.publish(b"db4/pump/state", b"off")

# Connect WiFi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("YourSSID", "YourPassword")
while not wlan.isconnected():
    time.sleep(0.1)

# Connect MQTT and subscribe to control topic
client.set_callback(on_command)
client.connect()
client.subscribe(b"db4/pump/set")
client.subscribe(b"db4/control/#")

while True:
    client.check_msg()           # non-blocking: handle incoming commands
    temp = 18.5                  # replace with measureTemp()
    od   = 0.42                  # replace with measureOD()
    client.publish(b"db4/temperature", str(temp))
    client.publish(b"db4/od",          str(od))
    client.publish(b"db4/pump/state",  "on" if pump.digital.value() else "off")
    time.sleep(2)