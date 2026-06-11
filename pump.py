from machine import Pin, PWM


class Pump:
    """
    Single-pin control for diaphragm pump via L9110S driver.

    Wiring:
    - L9110S A1 pin -> ESP32 GPIO 33
    - L9110S A2 pin -> GND (tied to ground)
    - L9110S VCC -> 12V supply
    - L9110S GND -> 12V GND and ESP32 GND (common ground)
    """

    def __init__(self, pin=33, use_pwm=False, freq=1000):
        """
        Initialize pump controller on given pin.

        Args:
            pin: GPIO pin number
            use_pwm: False for simple on/off, True for PWM speed control
            freq: PWM frequency (only used if use_pwm=True)
        """
        self.pin = pin
        self.use_pwm = use_pwm

        if use_pwm:
            self.pwm = PWM(Pin(pin), freq=freq)
        else:
            self.digital = Pin(pin, Pin.OUT)

    def on(self):
        """Turn pump on at full speed."""
        if self.use_pwm:
            self.set_speed(100)
        else:
            self.digital.value(1)
            print("Pump ON")

    def off(self):
        """Turn pump off."""
        if self.use_pwm:
            self.set_speed(0)
        else:
            self.digital.value(0)
            print("Pump OFF")

    # def set_speed(self, speed_percent):
    #     """
    #     Set pump speed as percentage (0-100). Only works if use_pwm=True.

    #     Args:
    #         speed_percent: 0 (off) to 100 (full speed)
    #     """
    #     if not self.use_pwm:
    #         print("Speed control requires use_pwm=True")
    #         return

    # # Clamp to valid range
    # speed_percent = max(0, min(100, speed_percent))

    # # Convert percentage to 16-bit duty cycle
    # duty = int(65535 * (speed_percent / 100))
    # self.pwm.duty_u16(duty)

    # print(f"Pump speed: {speed_percent}%")

    def stop(self):
        """Stop the pump."""
        self.off()

    def deinit(self):
        """Clean up."""
        if self.use_pwm:
            self.pwm.deinit()


# Example usage - simple on/off test
if __name__ == "__main__":
    import time

    # Simple on/off test (no PWM)
    pump = Pump(pin=33, use_pwm=False)

    try:
        print("Testing pump on/off...")

        pump.off()
        time.sleep(2)

        pump.on()
        time.sleep(2)

        pump.off()

        print("Test complete")

    finally:
        pump.deinit()
