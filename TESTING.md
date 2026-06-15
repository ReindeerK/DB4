# Testing the DB4 bioreactor controller

This guide walks through testing the project from a completely fresh laptop +
ESP32 board, with no prior setup. Steps are written for Windows (PowerShell),
since that's what the development laptop runs, but the tools are
cross-platform.

## What you're testing

- `controller.py` — runs on the ESP32, connects to WiFi + an MQTT broker,
  reads sensors and controls the pump.
- `pump.py`, `temperature.py`, `light_sensor.py`, `rgb_led.py` — individual
  hardware drivers, each can be run standalone for a bench test.
- `main.py` — the boot entry point, just imports `controller`.
- `logger.py` — runs on the laptop, subscribes to all MQTT messages and
  writes them to a CSV file.

---

## 0. Install tools on the laptop

You need Python 3 installed (`python --version` to check). Then install:

```powershell
pip install mpremote paho-mqtt
```

- **mpremote** — official MicroPython tool for talking to the board over
  USB: copying files, running scripts, and opening a serial console.
- **paho-mqtt** — Python MQTT client library, needed by `logger.py`.

You'll also need an **MQTT broker** running on the laptop — see step 4.

---

## 1. Connect the ESP32 and find its COM port

1. Plug the ESP32 into the laptop with a USB cable.
2. Open **Device Manager** → expand **Ports (COM & LPT)**.
3. Look for an entry like `Silicon Labs CP210x USB to UART Bridge (COMx)` or
   `USB-SERIAL CH340 (COMx)`. Note the COM number (e.g. `COM3`).
   - If nothing shows up, you may need to install the USB-to-serial driver
     for your board (CP2102 or CH340, depending on the board).

Verify the connection works:

```powershell
mpremote connect COM3 exec "print('hello from esp32')"
```

You should see `hello from esp32` printed back. If `mpremote` can't find the
port, double-check the COM number in Device Manager and that no other program
(Thonny, Arduino IDE serial monitor, etc.) is holding the port open.

> From here on, examples use `COM3` — replace with your actual port. If only
> one device is plugged in, you can usually drop `connect COM3` entirely and
> `mpremote` will auto-detect it.

---

## 2. Install the MQTT library on the device

`controller.py` imports `umqtt.robust`, which is **not** built into
MicroPython by default. Install it onto the board's filesystem:

```powershell
mpremote connect COM3 mip install umqtt.robust
```

This downloads the library and places it in `/lib` on the ESP32, where
MicroPython automatically looks for imports.

---

## 3. Bench-test each driver individually

Before running the full system, test each piece of hardware on its own using
`mpremote run <file>`. This runs the script directly from your laptop without
permanently copying it to the board — perfect for quick iteration.

### `pump.py` — pump relay

```powershell
mpremote connect COM3 run pump.py
```

Expected output (takes ~4 seconds):

```
Testing pump on/off...
Pump OFF
Pump ON
Pump OFF
Test complete
```

Check: the pump should physically click/turn on for ~2 seconds, then off.

### `temperature.py` — thermistor

```powershell
mpremote connect COM3 run temperature.py
```

This loops forever, printing once per second:

```
ADC: 2048 Voltage: 1.650 V Resistance: 10000 ohm Temperature: 25.00 C
```

Check: the temperature value should be a sane room-temperature number
(roughly 15–35°C). If you see "ADC reading out of range. Check wiring.",
double-check the thermistor wiring.

Press **Ctrl+C** to stop it.

### `light_sensor.py` — LTR-329 ambient light sensor

```powershell
mpremote connect COM3 run light_sensor.py
```

Expected output:

```
LTR-329 initialized
Reading light sensor data...
----------------------------------------
Visible Light: 1234
----------------------------------------
```

repeating once per second. Try covering the sensor with your hand — the
number should drop noticeably. If you see `Error reading sensor: ...`,
check the I2C wiring (SDA → GPIO21, SCL → GPIO22).

Press **Ctrl+C** to stop it.

### `rgb_led.py` — blue LED

```powershell
mpremote connect COM3 run rgb_led.py
```

This runs to completion on its own (~6 seconds): sets the blue LED to full
brightness, then half, then pulses it (fades in/out twice). Check: the LED
should visibly light up, dim, and pulse.

---

## 4. Set up the MQTT broker on the laptop

The ESP32 needs an MQTT broker to publish to and subscribe from. We'll run
[Mosquitto](https://mosquitto.org/download/) on the laptop.

1. Download and run the Windows installer from
   https://mosquitto.org/download/.
2. By default, Mosquitto only accepts connections from the same machine
   (`localhost`) and may refuse anonymous connections. Since the ESP32 is a
   *different device* on the network, you need to open it up. Edit
   `C:\Program Files\mosquitto\mosquitto.conf` and add these two lines:

   ```
   listener 1883 0.0.0.0
   allow_anonymous true
   ```

   (This disables authentication — fine for a local test network, **not**
   for anything exposed to the internet.)

3. Restart the Mosquitto service so it picks up the new config. Open a
   PowerShell window **as Administrator**:

   ```powershell
   net stop mosquitto
   net start mosquitto
   ```

4. Allow incoming connections on port 1883 through the Windows Firewall:
   - Open **Windows Defender Firewall with Advanced Security**.
   - **Inbound Rules** → **New Rule** → **Port** → **TCP** → Specific local
     port `1883` → **Allow the connection** → apply to all profiles (or at
     least the one matching your WiFi network) → name it e.g. "Mosquitto".

5. Quick sanity check from the laptop itself:

   ```powershell
   & "C:\Program Files\mosquitto\mosquitto_sub.exe" -h localhost -t "test" -v
   ```

   Leave this running, then in another terminal:

   ```powershell
   & "C:\Program Files\mosquitto\mosquitto_pub.exe" -h localhost -t "test" -m "hello"
   ```

   You should see `test hello` appear in the subscriber window.

---

## 5. Configure `controller.py`

Find your laptop's IP address on the WiFi network the ESP32 will join:

```powershell
ipconfig
```

Look for the **IPv4 Address** under your WiFi adapter (e.g. `192.168.1.105`).

Open `controller.py` and edit these lines near the top/bottom:

```python
BROKER_IP = "192.168.1.105"   # <- your laptop's IPv4 address from ipconfig
...
wlan.connect("YourSSID", "YourPassword")  # <- your real WiFi name/password
```

> The ESP32 only supports **2.4 GHz** WiFi networks — if your router has a
> separate 5 GHz network with the same name, make sure the ESP32 can see a
> 2.4 GHz band.

---

## 6. Upload all files to the ESP32

Copy every module the controller needs onto the board's root filesystem:

```powershell
mpremote connect COM3 cp pump.py : + cp temperature.py : + cp light_sensor.py : + cp rgb_led.py : + cp controller.py : + cp main.py :
```

(The `+` chains multiple commands in a single connection.)

---

## 7. Run it and watch the output

Make sure `logger.py` is running first (see step 8), then reset the board:

```powershell
mpremote connect COM3
```

This opens a live serial console. Press **Ctrl+D** to soft-reset the board —
it will run `boot.py` (if any) then `main.py`, which imports `controller.py`.
You should see it connect to WiFi and MQTT, then settle into the main loop.

Any errors (WiFi timeout, MQTT connection refused, import errors) will print
here as a traceback — see Troubleshooting below.

To exit the console without resetting the board, press **Ctrl+]**.

---

## 8. Verify data is flowing (laptop side)

In a separate terminal, run the logger:

```powershell
python logger.py
```

It connects to the local broker, subscribes to `db4/#`, and prints + saves
every message to `db4_log.csv`. Once `controller.py` is running on the
ESP32, you should see new rows appear every ~2 seconds:

```
['2026-06-15T12:00:00.123456', 'db4/temperature', '24.31']
['2026-06-15T12:00:00.234567', 'db4/od', '1532']
['2026-06-15T12:00:00.345678', 'db4/pump/state', 'off']
```

---

## 9. Test pump control over MQTT

With `controller.py` running and `logger.py` watching, send a command from
the laptop:

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h localhost -t db4/pump/set -m on
```

Check:
- The physical pump turns on.
- `logger.py` shows a new `db4/pump/state` message with value `on`.

Then turn it off:

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h localhost -t db4/pump/set -m off
```

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `mpremote` can't find the device / "could not open port" | Wrong COM port, missing USB driver, or another program (Thonny, Arduino Serial Monitor) has the port open |
| `ImportError: no module named 'umqtt'` | `mip install umqtt.robust` step (2) was skipped, or files were copied before installing it |
| Board hangs forever after reset, never connects to WiFi | Wrong SSID/password in `controller.py`, or the network is 5 GHz only |
| `OSError: [Errno 113] ECONNABORTED` / MQTT connect fails | Broker not listening on `0.0.0.0` (step 4.2), or Windows Firewall blocking port 1883 (step 4.4), or wrong `BROKER_IP` |
| `temperature.py` prints "ADC reading out of range" | Thermistor/voltage-divider wiring issue on GPIO34 |
| `light_sensor.py` prints "Error reading sensor" | I2C wiring issue — check SDA/GPIO21, SCL/GPIO22, and sensor power |
| Nothing appears in `logger.py` | Broker not reachable from ESP32 (check firewall/IP), or `controller.py` crashed before reaching the main loop — check the `mpremote` console (step 7) for a traceback |
