from machine import I2C, Pin, PWM
import time

# ===== SENSOR SETUP (LTR-329) =====
i2c = I2C(1, scl=Pin(22), sda=Pin(21), freq=400000)
LTR329_ADDR = 0x29

ALS_CONTR = 0x80
ALS_MEAS_RATE = 0x85
DATA_CH0_0 = 0x8A
DATA_CH0_1 = 0x8B

# ===== LED SETUP (HW-479) =====
BLUE_PIN = 25
blue_led = PWM(Pin(BLUE_PIN), freq=1000)


# ===== SENSOR FUNCTIONS =====
def init_sensor():
    """Initialize the LTR-329 sensor with fixed gain"""
    # Set ALS control register with fixed gain (no auto-gain)
    # Bit 0: ALS enable (1)
    # Bits 2-3: Gain selection (01 = 8x gain, 00 = 1x, 10 = 2x, 11 = 4x)
    # Using 0x09 = fixed 8x gain, ALS enabled
    i2c.writeto_mem(LTR329_ADDR, ALS_CONTR, b"\x09")
    time.sleep(0.01)

    # Set measurement rate (100ms integration time, 500ms repeat rate)
    i2c.writeto_mem(LTR329_ADDR, ALS_MEAS_RATE, b"\x03")
    time.sleep(0.01)

    print("LTR-329 initialized (fixed gain mode)")


def read_sensor(samples=5):
    """Read visible light from the sensor (averaged)"""
    try:
        readings = []
        for _ in range(samples):
            ch0_data = i2c.readfrom_mem(LTR329_ADDR, DATA_CH0_0, 2)
            ch0 = ch0_data[0] | (ch0_data[1] << 8)
            readings.append(ch0)
            time.sleep(0.05)  # Small delay between samples

        # Return average, ignoring min/max to remove outliers
        readings.sort()
        avg = sum(readings[1:-1]) // (len(readings) - 2)  # Skip min and max
        return avg
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return None


# ===== LED FUNCTIONS =====
def set_blue_brightness(brightness):
    """Set blue LED brightness (0-255)"""
    duty = int((brightness / 255) * 1023)
    blue_led.duty(duty)


# ===== COMBINED TEST =====
def test_led_with_sensor(pulses=2):
    """Pulse LED while reading sensor"""
    print("Starting LED + Sensor test...")
    print("=" * 50)

    init_sensor()
    time.sleep(0.5)

    try:
        for pulse_count in range(pulses):
            print(f"\n--- Pulse {pulse_count + 1}/{pulses} ---")

            # Fade in
            print("Fading IN:")
            for brightness in range(0, 256, 20):
                set_blue_brightness(brightness)
                time.sleep(0.2)  # Wait for light to stabilize
                light = read_sensor()
                print(
                    f"  LED: {brightness:3d}  |  Sensor: {light if light is not None else 'N/A'}"
                )

            # Fade out
            print("Fading OUT:")
            for brightness in range(255, -1, -20):
                set_blue_brightness(brightness)
                time.sleep(0.2)  # Wait for light to stabilize
                light = read_sensor()
                print(
                    f"  LED: {brightness:3d}  |  Sensor: {light if light is not None else 'N/A'}"
                )

            # Give sensor time to stabilize between pulses
            set_blue_brightness(0)
            print("(Resetting sensor...)")
            init_sensor()  # Re-initialize to reset auto-gain
            time.sleep(2)

        set_blue_brightness(0)
        print("\n" + "=" * 50)
        print("Test complete!")

    except KeyboardInterrupt:
        set_blue_brightness(0)
        print("Stopped")


def main():
    test_led_with_sensor(pulses=2)


if __name__ == "__main__":
    main()
