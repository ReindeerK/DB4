from machine import ADC, Pin
from time import sleep
from math import log

# Pin setup
adc = ADC(Pin(34))  # GPIO34 / ADC1_6

# ESP32 ADC setup
adc.width(ADC.WIDTH_12BIT)  # values from 0 to 4095
adc.atten(ADC.ATTN_11DB)  # allows reading up to about 3.3V

# Thermistor settings
VCC = 3.3
R_FIXED = 10000  # 10k fixed resistor
R0 = 10000  # thermistor resistance at 25C
T0 = 25 + 273.15  # 25C in Kelvin
BETA = 3950  # common value for 10k NTC thermistors


def read_adc_average(samples=20):
    total = 0
    for _ in range(samples):
        total += adc.read()
        sleep(0.01)
    return total / samples


def read_temperature():
    raw = read_adc_average()

    if raw <= 0 or raw >= 4095:
        return None

    voltage = raw / 4095 * VCC

    # For wiring:
    # 3V3 -> thermistor -> ADC pin -> fixed resistor -> GND
    r_thermistor = R_FIXED * ((VCC / voltage) - 1)

    temp_k = 1 / ((1 / T0) + (1 / BETA) * log(r_thermistor / R0))
    temp_c = temp_k - 273.15

    return temp_c, raw, voltage, r_thermistor


while True:
    result = read_temperature()

    if result is None:
        print("ADC reading out of range. Check wiring.")
    else:
        temp_c, raw, voltage, resistance = result
        print(
            "ADC:",
            int(raw),
            "Voltage: {:.3f} V".format(voltage),
            "Resistance: {:.0f} ohm".format(resistance),
            "Temperature: {:.2f} C".format(temp_c),
        )

    sleep(1)
