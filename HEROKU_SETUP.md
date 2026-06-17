# Hosting the DB4 dashboard on Heroku

The deployed architecture is:

```text
Browser -> Heroku Flask dashboard -> hosted MQTT broker -> ESP32
```

Heroku should host the Flask dashboard only. Use a hosted MQTT broker such as
HiveMQ Cloud, EMQX Cloud, or a Mosquitto server on a VPS for MQTT traffic.

## 1. Create a hosted MQTT broker

Create a broker and note these values:

```text
host
port
username
password
TLS enabled/disabled
```

Most hosted MQTT providers use port `8883` with TLS enabled.

## 2. Configure Heroku

Install and log into the Heroku CLI, then create or select your app:

```powershell
heroku login
heroku create your-app-name
```

Set the MQTT and dashboard credentials:

```powershell
heroku config:set MQTT_HOST="your-mqtt-broker-host"
heroku config:set MQTT_PORT="8883"
heroku config:set MQTT_USERNAME="your-mqtt-username"
heroku config:set MQTT_PASSWORD="your-mqtt-password"
heroku config:set MQTT_TLS="true"
heroku config:set DASHBOARD_USERNAME="admin"
heroku config:set DASHBOARD_PASSWORD="choose-a-strong-password"
```

Deploy:

```powershell
git add .
git commit -m "Deploy DB4 dashboard to Heroku"
git push heroku main
heroku open
```

Watch logs if the dashboard does not connect:

```powershell
heroku logs --tail
```

## 3. Configure the ESP32

In `controller.py`, replace these placeholders with the same broker values:

```python
MQTT_HOST = "your-mqtt-broker-host"
MQTT_PORT = 8883
MQTT_USER = b"your-mqtt-username"
MQTT_PASSWORD = b"your-mqtt-password"
MQTT_TLS = True
```

Then upload the updated controller:

```powershell
mpremote connect COM3 cp controller.py :controller.py
mpremote connect COM3 reset
```

## 4. Local development

For local testing with your existing laptop Mosquitto broker, leave the MQTT
environment variables unset and run:

```powershell
python webapp.py
```

The dashboard will use `localhost:1883` and listen on `http://localhost:8080`.
