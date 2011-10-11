"""Base classes for vumidash."""


class MetricSource(object):

    def total_seconds(self, dt):
        """Calculate total seconds from a timedelta."""
        return (dt.days * 24 * 60 * 60) + dt.seconds

    def get_latest(self, metric_name, from_dt, until_dt, step_dt):
        raise NotImplementedError("Sub-class should implement get_latest")

    def get_history(self, metric_name, from_dt, until_dt, step_dt,
                    skip_nulls=True):
        raise NotImplementedError("Sub-class should implement get_history")


class UnknownMetricError(Exception):
    """Raised when a metric source encounters an unknown metric name."""
