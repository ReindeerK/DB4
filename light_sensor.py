from machine import I2C, Pin
import time

# I2C is initialised at module load time (before WiFi starts in controller.py).
# Lower frequency (100 kHz) gives wider timing margins when the WiFi radio is active.
i2c = I2C(1, scl=Pin(22), sda=Pin(21), freq=100000)

# LTR-329 I2C address
LTR329_ADDR = 0x29

# Register addresses
ALS_CONTR = 0x80
ALS_MEAS_RATE = 0x85
PART_ID = 0x86
DATA_CH1_0 = 0x88
DATA_CH1_1 = 0x89
DATA_CH0_0 = 0x8A
DATA_CH0_1 = 0x8B


def init_sensor():
    """Initialize the LTR-329 sensor."""
    # i2c.writeto_mem(LTR329_ADDR, ALS_CONTR, b"\x1D")   # Active mode, Gain 96×
    i2c.writeto_mem(LTR329_ADDR, ALS_CONTR, b"\x0D")   # Active mode, Gain 96×
    # i2c.writeto_mem(LTR329_ADDR, ALS_CONTR, b"\x19")   # Active mode, Gain 96×
    time.sleep(0.05)
    i2c.writeto_mem(LTR329_ADDR, ALS_MEAS_RATE, b"\x1B")  # 400 ms integration, 500 ms rate
    # i2c.writeto_mem(LTR329_ADDR, ALS_MEAS_RATE, b"\x03")  # 100 ms integration, 500 ms rate
    time.sleep(0.65)   # wait for first complete measurement cycle
    print("LTR-329 initialized")


# Time between independent measurements. The sensor only refreshes its data
# registers once per repeat-rate period (set to 500 ms via ALS_MEAS_RATE), so
# samples must be spaced at least this far apart to be genuinely new readings.
MEAS_PERIOD_S = 0.5


def read_sensor(samples=5):
    """Read visible light (Channel 0), averaged over independent samples.

    Takes `samples` readings spaced one measurement period apart, discards the
    single lowest and highest to reject outliers, and returns the mean of the
    rest. Averaging N independent samples cuts random noise by ~sqrt(N), which
    is what lets small OD differences at low algae concentration show through.

    Cost: roughly samples * MEAS_PERIOD_S seconds per call (default ~2 s).
    """
    try:
        readings = []
        for i in range(samples):
            # Wait for a fresh integration result before every sample after the
            # first; back-to-back reads would just return the same value.
            if i > 0:
                time.sleep(MEAS_PERIOD_S)
            ch0_data = i2c.readfrom_mem(LTR329_ADDR, DATA_CH0_0, 2)
            readings.append(ch0_data[0] | (ch0_data[1] << 8))

        if len(readings) >= 3:
            readings.sort()
            trimmed = readings[1:-1]  # drop min and max
            return sum(trimmed) // len(trimmed)
        return sum(readings) // len(readings)
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return None


def main():
    """Main loop"""
    init_sensor()

    print("Reading light sensor data...")
    print("-" * 40)

    try:
        while True:
            light = read_sensor()
            if light is not None:
                print(f"Visible Light: {light}")
                print("-" * 40)

            time.sleep(1)  # Read every 1 second
    except KeyboardInterrupt:
        print("Stopped")


if __name__ == "__main__":
    main()
