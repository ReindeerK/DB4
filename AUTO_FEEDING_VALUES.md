# Autonomous Feeding Values To Measure

This checklist lists the assumed values that must be decided, measured, or
calibrated before trusting the automatic algae feeding mode.

## Highest Priority

These values are required before using `AUTO` with live mussels.

| Config value | What it means | Current value | What to do |
| --- | --- | --- | --- |
| `OD_CALIBRATION_MODE` | OD conversion method: `linear` or `absorbance` | `linear` | Choose based on your calibration curve |
| `OD_LINEAR_SLOPE` | Linear conversion from raw OD count to cells/mL | `1.0` | Replace with dilution-series fit |
| `OD_LINEAR_INTERCEPT` | Linear calibration offset | `0.0` | Replace with dilution-series fit |
| `OD_BLANK_RAW` | Clean-water sensor reading for absorbance mode | `65000.0` | Measure with clean water, same LED setup |
| `OD_ABSORBANCE_SLOPE` | Absorbance-to-cells/mL fit | `1.0` | Replace if using absorbance mode |
| `OD_ABSORBANCE_INTERCEPT` | Absorbance calibration offset | `0.0` | Replace if using absorbance mode |
| `FEED_PUMP_FLOW_ML_MIN` | Actual feed pump flow rate | `1500.0` | Measure at 5 V with real tubing and height |
| `ALGAE_STOCK_CONCENTRATION` | Algae concentration in feed tank | `250000.0` | Measure in cells/mL |
| `FEED_TARGET_CONCENTRATION` | Desired algae concentration in mussel tank | `2000.0` | Confirm biological target |
| `TANK_VOLUME_L` | Actual water volume in mussel tank | `4.0` | Measure real filled volume |
| `MUSSEL_CLEARANCE_RATE_L_H` | Clearance rate per mussel | `2.5` | Measure with decline experiment |

## Model And Control Values

These values affect how the model decides when and how much to feed.

| Config value | What it means | Current value | Notes |
| --- | --- | --- | --- |
| `FEED_LOW_FRACTION` | Lower feeding threshold as fraction of target | `0.90` | With target `2000`, feeds below `1800` |
| `FEED_HIGH_FRACTION` | Upper stop/hold threshold as fraction of target | `1.10` | With target `2000`, holds above `2200` |
| `N_MUSSELS` | Number of mussels in tank | `4` | Update whenever mussel count changes |
| `ALGAE_GROWTH_RATE_H` | Algae growth rate | `0.035` | Less critical because control uses live OD |

## Pump Safety Values

These protect against overfeeding or unreliable tiny pump pulses.

| Config value | What it means | Current value | Notes |
| --- | --- | --- | --- |
| `MIN_FEED_PUMP_SECONDS` | Shortest allowed pump pulse | `0.10` | At `1500 mL/min`, this is about `2.5 mL` |
| `MAX_FEED_PUMP_SECONDS` | Longest allowed single pump run | `2.0` | At `1500 mL/min`, this is about `50 mL` |
| `FEED_DOSE_COOLDOWN_SECONDS` | Minimum wait between new doses | `30` | Increase if mixing is slow |
| `FEED_SENSOR_STALE_SECONDS` | Max age of OD reading before AUTO refuses to dose | `120` | Keep short for safety |
| `FEED_PUMP_ACTIVE_LOW` | Whether pump driver is active-low | `False` | Set `True` only if LOW turns pump on |
| `CONTROL_LOOP_DELAY_SECONDS` | Delay between full sensor/control cycles | `2` | Short pump pulses are handled separately |

## Pump Calibration Procedure

Use the actual 5 V supply, tubing, height difference, and pump placement.

1. Put the pump intake in water.
2. Run the pump for a short measured time, for example `5-10 s`.
3. Collect the pumped water.
4. Weigh it in grams. For water, `grams ~= mL`.
5. Calculate:

```text
FEED_PUMP_FLOW_ML_MIN = collected_mL / run_time_minutes
```

Example:

```text
Collected water = 120 mL
Run time = 5 s = 0.0833 min
Flow = 120 / 0.0833 = 1440 mL/min
```

## OD Calibration Procedure

Use the same LED brightness, sensor geometry, cuvette/tube, and algae species as
the real system.

1. Prepare a dilution series with known algae concentrations in `cells/mL`.
2. Measure the raw OD sensor value for each concentration.
3. Fit either:

```text
linear: concentration = slope * raw_count + intercept
```

or:

```text
absorbance = log10(blank_raw / raw_count)
concentration = slope * absorbance + intercept
```

4. Copy the fitted slope/intercept values into `controller_config.py`.

## Clearance Rate Procedure

This measures how fast the mussels remove algae.

1. Put `N_MUSSELS` mussels in a known volume `TANK_VOLUME_L`.
2. Turn feeding off.
3. Measure algae concentration at time `t1`.
4. Wait a known time.
5. Measure algae concentration at time `t2`.
6. Calculate the grazing coefficient:

```text
g = ln(C1 / C2) / (t2 - t1)
```

7. Calculate clearance rate per mussel:

```text
MUSSEL_CLEARANCE_RATE_L_H = g * TANK_VOLUME_L / N_MUSSELS
```
