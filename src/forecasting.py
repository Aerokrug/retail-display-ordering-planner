"""Turns last year's sales into this year's unit forecast."""

from src.models import DisplayConfig, Variety


def forecast_total_units(
    prior_year_total_units: float,
    config: DisplayConfig,
    discount_pct: float = 0.0,
    elasticity_coefficient: float = -1.5,
    bias_correction: float = 1.0,
) -> float:
    """
    Normalize last year's units to a daily rate, scale to this year's
    duration, then apply growth target / tie-in / discount lift / bias
    correction on top.
    """
    if config.duration_days_prior_year <= 0:
        raise ValueError("duration_days_prior_year must be > 0")

    daily_run_rate = prior_year_total_units / config.duration_days_prior_year
    duration_adjusted = daily_run_rate * config.duration_days_this_year

    growth_multiplier = 1 + config.growth_target_pct
    tie_in_multiplier = 1 + config.tie_in_bonus_pct if config.tie_in else 1.0
    # lift = -elasticity * discount, comes out positive since elasticity is negative
    discount_multiplier = 1 + (-elasticity_coefficient * discount_pct)

    return (
        duration_adjusted
        * growth_multiplier
        * tie_in_multiplier
        * discount_multiplier
        * bias_correction
    )


def adjust_for_stockout(variety: Variety, assumed_lost_sales_pct: float = 0.15) -> float:
    """Bump up last year's units if we sold out - the recorded number
    understates real demand. Flat 15% bump for now, not a real model."""
    if variety.stockout_last_year:
        return variety.prior_year_units * (1 + assumed_lost_sales_pct)
    return variety.prior_year_units
