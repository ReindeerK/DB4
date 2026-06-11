from machine import Pin, PWM
import time

# HW-479 RGB LED pins (adjust these to your GPIO pins)
BLUE_PIN = 25  # GPIO pin for blue LED

# Create PWM object for blue channel
blue_led = PWM(Pin(BLUE_PIN), freq=1000)


def set_blue_brightness(brightness):
    """Set blue LED brightness (0-255)"""
    # PWM duty cycle is 0-1023 for ESP32
    duty = int((brightness / 255) * 1023)
    blue_led.duty(duty)
    print(f"Blue brightness: {brightness}")


def pulse_blue(pulses=2):
    """Pulse the blue LED"""
    print(f"Pulsing blue LED {pulses} times...")
    try:
        for pulse_count in range(pulses):
            # Fade in
            for brightness in range(0, 256, 10):
                set_blue_brightness(brightness)
                time.sleep(0.05)

            # Fade out
            for brightness in range(255, -1, -10):
                set_blue_brightness(brightness)
                time.sleep(0.05)

            print(f"Pulse {pulse_count + 1} complete")

        set_blue_brightness(0)
        print("All pulses complete")
    except KeyboardInterrupt:
        set_blue_brightness(0)
        print("Stopped")


def main():
    """Main loop"""
    print("HW-479 Blue LED Control")
    print("-" * 40)

    # Test: Set to full brightness
    set_blue_brightness(255)
    time.sleep(2)

    # Test: Set to half brightness
    set_blue_brightness(127)
    time.sleep(2)

    # Pulse effect
    pulse_blue()


if __name__ == "__main__":
    main()
