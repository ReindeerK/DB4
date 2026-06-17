# calibration.py - LED color/intensity calibration for the OD sensor
#
# Walks through a dilution series of algae and finds which LED color +
# brightness gives the best "contrast" (i.e. the algae absorbs the most
# light) without saturating the LTR-329 sensor.
#
# Wiring: fill in GPIO pins for any extra LED colors you have wired below.
# Any color left as None is skipped. Blue (GPIO 25) matches rgb_led.py.
#
# Usage (from the ESP32 REPL, with controller.py NOT running so it doesn't
# fight over the LED/I2C pins):
#   import calibration
#   calibration.run()

import time
from machine import Pin, PWM
from light_sensor import init_sensor, read_sensor

LED_PINS = {
    "blue": 25,
    "green": 26,
    "red": 27,
}

INTENSITIES = (64, 128, 192, 255)
SETTLE_TIME = 0.2   # seconds to let the LED/sensor settle before reading
SATURATION = 60000  # near the LTR-329 ch0 max (16-bit) - readings at/above this are unreliable
MIN_SIGNAL = 0    # readings below this are too dim to trust

leds = {}
for color, pin in LED_PINS.items():
    if pin is not None:
        leds[color] = PWM(Pin(pin), freq=1000)
        leds[color].duty(0)  # off at boot


def set_led(color, brightness):
    """Turn on one LED channel at the given brightness (0-255), others off."""
    for c, pwm in leds.items():
        pwm.duty(int((brightness / 255) * 1023) if c == color else 0)


def all_off():
    for pwm in leds.values():
        pwm.duty(0)


def read_sensor_avg(samples=5, delay=0.05):
    """Take multiple readings and return the average to reduce noise."""
    total = 0
    for _ in range(samples):
        total += read_sensor()
        time.sleep(delay)
    return int(total / samples)


def measure(color, intensity):
    """Take one ambient-corrected reading with the given LED on for 3 seconds."""
    set_led(color, intensity)
    time.sleep(SETTLE_TIME)
    # 30 samples with 0.1s delay takes exactly 3 seconds
    raw = read_sensor_avg(samples=30, delay=0.1)
    all_off()
    return raw


def run():
    """Interactive calibration across a dilution series. Returns the best
    (color, intensity) combo, or None if nothing usable was found."""
    init_sensor()

    n = int(input("How many samples in the dilution series? "))
    labels = [input(f"Label for sample {i + 1} (e.g. '0%', '25%', ...): ") for i in range(n)]

    combos = [(color, intensity) for color in leds for intensity in INTENSITIES]
    readings = {combo: [] for combo in combos}

    for label in labels:
        input(f"\nPlace sample '{label}' in front of the sensor, then press Enter")
        time.sleep(0.5)

        ambient = read_sensor_avg()  # LEDs off, for baseline subtraction

        for color, intensity in combos:
            raw = measure(color, intensity)
            corrected = max(raw - ambient, 0)
            readings[(color, intensity)].append(corrected)
            print(f"  {color} @ {intensity}: raw={raw} ambient={ambient} -> {corrected}")

    print("\n--- Results ---")
    scored = []
    for combo, values in readings.items():
        i0 = max(values)
        i_min = min(values)
        if i0 < MIN_SIGNAL:
            print(f"{combo}: too dim (max={i0}), skipped")
            continue
        if i0 >= SATURATION:
            print(f"{combo}: saturated (max={i0}), skipped")
            continue
        contrast = (i0 - i_min) / i0
        scored.append((contrast, combo, values))
        print(f"{combo}: readings={values} contrast={contrast:.3f}")

    if not scored:
        print("\nNo usable combination found - try different intensities or check wiring.")
        return None

    scored.sort(reverse=True)
    best_contrast, best_combo, best_values = scored[0]
    print(f"\nBest setting: {best_combo[0]} @ intensity {best_combo[1]} (contrast={best_contrast:.3f})")
    print(f"Readings across dilution series: {best_values}")
    return best_combo


if __name__ == "__main__":
    run()
