"""
Feedback loop - log what actually happened, use it to correct future
forecasts. Two things get learned per variety:

1. Bias correction: average (actual/forecast) ratio from past runs.
   If we're consistently 15% low, bump future forecasts by 15%.
2. Fitted elasticity: once a variety has been logged at a few different
   discount depths, fit a real elasticity from a log-log regression
   instead of guessing -1.5.

Both are simple stats, not ML - there's not enough dimensionality here
to need anything heavier.
"""

import math

from src.db import DEFAULT_DB_PATH
from src.db import load_results as _load_results
from src.db import log_result as _log_result
from src.models import ResultRecord

RESULTS_LOG_PATH = DEFAULT_DB_PATH  # old name, kept around in case anything imports it


def log_result(record: ResultRecord, db_path: str = DEFAULT_DB_PATH) -> None:
    _log_result(record, db_path)


def load_results(db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    return _load_results(db_path=db_path)


def compute_bias_correction(
    variety_name: str,
    db_path: str = DEFAULT_DB_PATH,
    min_history: int = 2,
) -> float:
    """Average actual/forecast ratio for this variety. Returns 1.0
    (no correction) if there's not enough history yet."""
    rows = _load_results(variety_name=variety_name, db_path=db_path)
    if len(rows) < min_history:
        return 1.0

    ratios = []
    for r in rows:
        forecast = float(r["forecast_units"])
        actual = float(r["actual_units"])
        if forecast > 0:
            ratios.append(actual / forecast)

    if not ratios:
        return 1.0

    return sum(ratios) / len(ratios)


def compute_all_bias_corrections(db_path: str = DEFAULT_DB_PATH) -> dict[str, float]:
    """Bias correction for every variety with history in one call."""
    rows = _load_results(db_path=db_path)
    names = {r["variety_name"] for r in rows}
    return {name: compute_bias_correction(name, db_path) for name in names}


def fit_elasticity(
    variety_name: str,
    db_path: str = DEFAULT_DB_PATH,
    min_points: int = 3,
) -> float | None:
    """Fits elasticity from log(units) ~ log(1 - discount). Needs at
    least min_points runs with actual discount variation, otherwise
    returns None and the caller keeps its assumed coefficient."""
    rows = _load_results(variety_name=variety_name, db_path=db_path)

    xs, ys = [], []
    for r in rows:
        discount = float(r["discount_pct"])
        actual = float(r["actual_units"])
        price_ratio = 1 - discount
        if price_ratio > 0 and actual > 0:
            xs.append(math.log(price_ratio))
            ys.append(math.log(actual))

    if len(xs) < min_points or len(set(xs)) < 2:
        return None

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)

    if denominator == 0:
        return None

    return numerator / denominator  # the slope is the elasticity coefficient
