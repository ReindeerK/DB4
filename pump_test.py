from pump import Pump
import time

# Use a different control pin for the second pump (B1/B2 channel)
# Example: GPIO 32. Change this if you have a different free pin.
CONTROL_PIN = 32

# If you are using the L9110S driver like before, keep use_pwm=False
pump = Pump(pin=CONTROL_PIN, use_pwm=False)

try:
    print("Second pump test starting on pin {}...".format(CONTROL_PIN))
    pump.off()
    time.sleep(2)

    print("Turning second pump ON for 5 seconds")
    pump.on()
    time.sleep(5)

    print("Turning second pump OFF")
    pump.off()
    time.sleep(2)

    print("Second pump test complete. Check whether water is moving.")

finally:
    pump.deinit()
