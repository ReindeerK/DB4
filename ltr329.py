from machine import I2C, Pin
import time

# Initialize I2C on GPIO 21 (SDA) and GPIO 22 (SCL)
i2c = I2C(1, scl=Pin(22), sda=Pin(21), freq=400000)

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
    """Initialize the LTR-329 sensor"""
    # Set ALS control register (enable sensor, gain=1, integration time)
    i2c.writeto_mem(LTR329_ADDR, ALS_CONTR, b"\x01")
    time.sleep(0.01)

    # Set measurement rate (100ms integration time, 500ms repeat rate)
    i2c.writeto_mem(LTR329_ADDR, ALS_MEAS_RATE, b"\x03")
    time.sleep(0.01)

    print("LTR-329 initialized")


def read_sensor():
    """Read visible light from the sensor"""
    try:
        # Read Channel 0 (visible light) - 2 bytes
        ch0_data = i2c.readfrom_mem(LTR329_ADDR, DATA_CH0_0, 2)
        ch0 = ch0_data[0] | (ch0_data[1] << 8)

        return ch0
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
