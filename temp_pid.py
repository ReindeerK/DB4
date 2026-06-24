class TemperaturePID:
    """Cooling-only PID with simple tank prediction and feed-forward support."""

    def __init__(
        self,
        setpoint_c=17.5,
        min_c=17.0,
        max_c=18.0,
        kp=35.0,
        ki=0.015,
        kd=0.0,
        deadband_c=0.05,
        output_min=0.0,
        output_max=100.0,
        filter_alpha=0.35,
        prediction_horizon_s=90.0,
        feed_temp_rise_c=0.20,
        feed_forward_percent=15.0,
    ):
        self.setpoint_c = setpoint_c
        self.min_c = min_c
        self.max_c = max_c
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.deadband_c = deadband_c
        self.output_min = output_min
        self.output_max = output_max
        self.filter_alpha = filter_alpha
        self.prediction_horizon_s = prediction_horizon_s
        self.feed_temp_rise_c = feed_temp_rise_c
        self.feed_forward_percent = feed_forward_percent

        self.integral = 0.0
        self.filtered_temp = None
        self.last_temp = None
        self.last_time_ms = None
        self.last_rate_c_per_s = 0.0
        self.last_output = 0.0
        self.last_predicted_temp = None
        self.last_feed_forward = 0.0
        self.status = "INIT"

    def reset(self):
        self.integral = 0.0
        self.filtered_temp = None
        self.last_temp = None
        self.last_time_ms = None
        self.last_rate_c_per_s = 0.0
        self.last_output = 0.0
        self.last_predicted_temp = None
        self.last_feed_forward = 0.0
        self.status = "RESET"

    def _clamp(self, value, low, high):
        if value < low:
            return low
        if value > high:
            return high
        return value

    def _elapsed_seconds(self, now_ms):
        diff_ms = now_ms - self.last_time_ms
        if diff_ms < 0:
            diff_ms += 1 << 30
        return diff_ms / 1000.0

    def update(self, temp_c, now_ms, feed_pump_on=False):
        if temp_c is None:
            self.status = "NO_TEMP"
            self.last_output = 0.0
            return self.last_output

        if self.filtered_temp is None:
            self.filtered_temp = temp_c
        else:
            alpha = self._clamp(self.filter_alpha, 0.0, 1.0)
            self.filtered_temp = (alpha * temp_c) + ((1.0 - alpha) * self.filtered_temp)

        dt = 0.0
        if self.last_time_ms is not None:
            dt = self._elapsed_seconds(now_ms)

        if dt > 0 and self.last_temp is not None:
            self.last_rate_c_per_s = (self.filtered_temp - self.last_temp) / dt

        feed_rise = self.feed_temp_rise_c if feed_pump_on else 0.0
        self.last_feed_forward = self.feed_forward_percent if feed_pump_on else 0.0
        predicted = self.filtered_temp + (self.last_rate_c_per_s * self.prediction_horizon_s) + feed_rise
        self.last_predicted_temp = predicted

        error = predicted - self.setpoint_c

        if temp_c <= self.min_c:
            self.integral = min(0.0, self.integral)
            output = 0.0
            self.status = "LOW_HOLD"
        else:
            if abs(error) <= self.deadband_c:
                error = 0.0
                self.integral *= 0.95

            candidate_integral = self.integral + (error * dt)
            p_term = self.kp * error
            i_term = self.ki * candidate_integral
            d_term = self.kd * self.last_rate_c_per_s
            raw_output = p_term + i_term + d_term + self.last_feed_forward
            output = self._clamp(raw_output, self.output_min, self.output_max)

            saturated_high = output >= self.output_max and error > 0
            saturated_low = output <= self.output_min and error < 0
            if not saturated_high and not saturated_low:
                self.integral = candidate_integral

            if temp_c >= self.max_c:
                output = max(output, 60.0)
                self.status = "HIGH_COOL"
            elif output > 0:
                self.status = "COOLING"
            else:
                self.status = "IDLE"

        self.last_temp = self.filtered_temp
        self.last_time_ms = now_ms
        self.last_output = output
        return output

    def snapshot(self):
        return {
            "status": self.status,
            "setpoint": self.setpoint_c,
            "predicted_temp": self.last_predicted_temp,
            "filtered_temp": self.filtered_temp,
            "rate_c_per_min": self.last_rate_c_per_s * 60.0,
            "output_percent": self.last_output,
            "feed_forward_percent": self.last_feed_forward,
        }
