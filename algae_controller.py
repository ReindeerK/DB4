import math


class AlgaeFeedingController:
    """Closed-loop feeding controller for the mussel tank.

    The controller uses the notebook model:
    - mussels remove algae with g = N * clearance_rate / tank_volume
    - feed dose is a mass balance back to the target concentration
    - pump run time is dose volume divided by calibrated pump flow
    """

    def __init__(
        self,
        target_concentration,
        tank_volume_l,
        stock_concentration,
        pump_flow_ml_min,
        low_fraction=0.90,
        high_fraction=1.10,
        mussel_count=4,
        clearance_rate_l_h=2.5,
        algae_growth_rate_h=0.035,
        min_pump_seconds=2,
        max_pump_seconds=300,
        dose_cooldown_seconds=600,
        max_dose_cooldown_seconds=900,
        sensor_stale_seconds=120,
        od_mode="linear",
        od_linear_slope=1.0,
        od_linear_intercept=0.0,
        od_blank_raw=65000.0,
        od_absorbance_slope=1.0,
        od_absorbance_intercept=0.0,
        enabled=False,
    ):
        self.target = float(target_concentration)
        self.tank_volume_l = float(tank_volume_l)
        self.stock_concentration = float(stock_concentration)
        self.pump_flow_ml_min = float(pump_flow_ml_min)
        self.low_fraction = float(low_fraction)
        self.high_fraction = float(high_fraction)
        self.mussel_count = float(mussel_count)
        self.clearance_rate_l_h = float(clearance_rate_l_h)
        self.algae_growth_rate_h = float(algae_growth_rate_h)
        self.min_pump_seconds = float(min_pump_seconds)
        self.max_pump_seconds = float(max_pump_seconds)
        self.dose_cooldown_seconds = float(dose_cooldown_seconds)
        self.max_dose_cooldown_seconds = float(max_dose_cooldown_seconds)
        self.sensor_stale_seconds = float(sensor_stale_seconds)
        self.od_mode = od_mode
        self.od_linear_slope = float(od_linear_slope)
        self.od_linear_intercept = float(od_linear_intercept)
        self.od_blank_raw = float(od_blank_raw)
        self.od_absorbance_slope = float(od_absorbance_slope)
        self.od_absorbance_intercept = float(od_absorbance_intercept)

        self.mode = "auto" if enabled else "off"
        self.status = "AUTO_READY" if enabled else "OFF"
        self.pump_until_s = None
        self.last_dose_s = None
        self.max_cooldown_anchor_s = None
        self.last_concentration_s = None
        self.last_concentration = None
        self.last_dose_ml = 0.0
        self.last_pump_seconds = 0.0

    @property
    def low_threshold(self):
        return self.target * self.low_fraction

    @property
    def high_threshold(self):
        return self.target * self.high_fraction

    def set_mode(self, mode, now_s=None):
        if mode not in ("off", "auto", "on"):
            return False
        self.mode = mode
        if mode == "off":
            self.status = "OFF"
            self.pump_until_s = None
        elif mode == "on":
            self.status = "FORCED_ON"
            self.pump_until_s = None
        else:
            self.status = "AUTO_READY"
            if now_s is not None:
                self.last_dose_s = None
        return True

    def concentration_from_od(self, od_raw):
        if od_raw is None:
            return None
        raw = float(od_raw)
        if raw < 0:
            return None

        if self.od_mode == "absorbance":
            if raw <= 0 or self.od_blank_raw <= 0:
                return None
            # Beer-Lambert style calibration from transmitted light.
            absorbance = math.log(self.od_blank_raw / raw) / math.log(10)
            concentration = (
                self.od_absorbance_slope * absorbance
                + self.od_absorbance_intercept
            )
        else:
            concentration = self.od_linear_slope * raw + self.od_linear_intercept

        if concentration < 0:
            return 0.0
        return concentration

    def predicted_concentration(self, concentration, elapsed_hours):
        g = self.grazing_coefficient()
        net_rate = self.algae_growth_rate_h - g
        return concentration * math.exp(net_rate * elapsed_hours)

    def grazing_coefficient(self):
        if self.tank_volume_l <= 0:
            return 0.0
        return (self.mussel_count * self.clearance_rate_l_h) / self.tank_volume_l

    def required_dose_ml(self, concentration):
        if concentration is None:
            return 0.0
        if concentration >= self.target:
            return 0.0
        if self.stock_concentration <= self.target:
            return 0.0
        tank_volume_ml = self.tank_volume_l * 1000.0
        dose_ml = (
            tank_volume_ml
            * (self.target - concentration)
            / (self.stock_concentration - self.target)
        )
        if dose_ml < 0:
            return 0.0
        return dose_ml

    def pump_seconds_for_dose(self, dose_ml):
        if dose_ml <= 0 or self.pump_flow_ml_min <= 0:
            return 0.0
        seconds = (dose_ml / self.pump_flow_ml_min) * 60.0
        if seconds < self.min_pump_seconds:
            seconds = self.min_pump_seconds
        if seconds > self.max_pump_seconds:
            seconds = self.max_pump_seconds
        return seconds

    def minimum_dose_ml(self):
        if self.pump_flow_ml_min <= 0:
            return 0.0
        return (self.pump_flow_ml_min * self.min_pump_seconds) / 60.0

    def max_cooldown_elapsed(self, now_s):
        if self.max_dose_cooldown_seconds <= 0:
            return False
        if self.max_cooldown_anchor_s is None:
            self.max_cooldown_anchor_s = now_s
            return False
        return (now_s - self.max_cooldown_anchor_s) >= self.max_dose_cooldown_seconds

    def start_dose(self, dose_ml, pump_seconds, now_s, status="DOSING"):
        self.last_dose_ml = dose_ml
        self.last_pump_seconds = pump_seconds

        if pump_seconds <= 0:
            self.status = "CANNOT_DOSE"
            return False

        self.last_dose_s = now_s
        self.max_cooldown_anchor_s = now_s
        self.pump_until_s = now_s + pump_seconds
        self.status = status
        return True

    def _sensor_is_stale(self, now_s):
        if self.last_concentration_s is None:
            return True
        return (now_s - self.last_concentration_s) > self.sensor_stale_seconds

    def update(self, concentration, now_s):
        """Return desired feed-pump state for the current control step."""
        now_s = float(now_s)
        if concentration is not None:
            self.last_concentration = float(concentration)
            self.last_concentration_s = now_s

        if self.mode == "off":
            self.status = "OFF"
            self.pump_until_s = None
            return False

        if self.mode == "on":
            self.status = "FORCED_ON"
            return True

        if self._sensor_is_stale(now_s):
            self.status = "NO_OD"
            self.pump_until_s = None
            return False

        current = self.last_concentration

        if self.pump_until_s is not None:
            if current > self.high_threshold:
                self.pump_until_s = None
                self.status = "HIGH_HOLD"
                return False
            if current >= self.target:
                self.pump_until_s = None
                self.status = "DOSE_COMPLETE"
                return False
            if now_s < self.pump_until_s:
                self.status = "DOSING"
                return True
            self.pump_until_s = None
            self.status = "DOSE_COMPLETE"
            return False

        if current > self.high_threshold:
            self.status = "HIGH_HOLD"
            return False

        if current >= self.low_threshold:
            if self.max_cooldown_elapsed(now_s):
                return self.start_dose(
                    self.minimum_dose_ml(),
                    self.min_pump_seconds,
                    now_s,
                    "MAX_INTERVAL_DOSING",
                )
            self.status = "IN_BAND"
            return False

        if (
            self.last_dose_s is not None
            and (now_s - self.last_dose_s) < self.dose_cooldown_seconds
        ):
            self.status = "COOLDOWN"
            return False

        dose_ml = self.required_dose_ml(current)
        pump_seconds = self.pump_seconds_for_dose(dose_ml)
        return self.start_dose(dose_ml, pump_seconds, now_s)

    def telemetry(self):
        return {
            "mode": self.mode,
            "status": self.status,
            "target": self.target,
            "low": self.low_threshold,
            "high": self.high_threshold,
            "concentration": self.last_concentration,
            "dose_ml": self.last_dose_ml,
            "pump_seconds": self.last_pump_seconds,
            "min_cooldown_seconds": self.dose_cooldown_seconds,
            "max_cooldown_seconds": self.max_dose_cooldown_seconds,
            "grazing_coefficient": self.grazing_coefficient(),
        }
