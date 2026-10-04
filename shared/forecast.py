"""Small forecasts shared by the Docker and Prometheus MCP servers."""


def linear_forecast(samples: list[float], steps_ahead: int) -> float | None:
    """Project the next value with a straight line through the samples.

    A memory leak in this project looks like a straight climb, so a line is
    enough. Returns None when there are fewer than two points.
    """
    if len(samples) < 2 or steps_ahead < 1:
        return None
    n = len(samples)
    mean_x = (n - 1) / 2
    mean_y = sum(samples) / n
    variance_x = sum((i - mean_x) ** 2 for i in range(n))
    if variance_x == 0:
        return samples[-1]
    slope = sum((i - mean_x) * (samples[i] - mean_y) for i in range(n)) / variance_x
    intercept = mean_y - slope * mean_x
    return intercept + slope * (n - 1 + steps_ahead)


def minutes_to_limit(samples: list[float], limit: float, interval_seconds: int) -> int | None:
    """How many minutes until the line crosses the limit. None if it does not."""
    if len(samples) < 2 or limit <= 0 or interval_seconds <= 0:
        return None
    projected = linear_forecast(samples, 1)
    if projected is None:
        return None
    slope_per_step = projected - samples[-1]
    if slope_per_step <= 0:
        return None
    remaining = limit - samples[-1]
    if remaining <= 0:
        return 0
    steps = remaining / slope_per_step
    return max(0, round(steps * interval_seconds / 60))
