from machine import Pin, PWM
import time

# HW-479 RGB LED pins (adjust these to your GPIO pins)
BLUE_PIN = 25  # GPIO pin for blue LED

# Create PWM object for blue channel
blue_led = PWM(Pin(BLUE_PIN), freq=1000)
blue_led.duty(1023)  # on at boot


def set_blue_brightness(brightness):
    """Set blue LED brightness (0=off, 255=full on)."""
    duty = int((brightness / 255) * 1023)
    blue_led.duty(duty)



def main():
    """Main loop"""
    # print("HW-479 Blue LED Control")
    # print("-" * 40)

    # Test: Set to full brightness
    set_blue_brightness(255)
    # time.sleep(2)

    # # Test: Set to half brightness
    # set_blue_brightness(127)
    # time.sleep(2)


if __name__ == "__main__":
    main()
