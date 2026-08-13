"""Turns a forecast into case-rounded orders per variety."""

import math

from src.forecasting import adjust_for_stockout, forecast_total_units
from src.models import DisplayConfig, Variety, VarietyOrder


def allocate_by_variety(
    config: DisplayConfig,
    varieties: list[Variety],
    bias_corrections: dict[str, float] | None = None,
) -> list[VarietyOrder]:
    """bias_corrections: {variety_name: multiplier}, from learning.compute_bias_correction.
    Missing varieties default to 1.0 (no correction)."""
    if not varieties:
        return []

    bias_corrections = bias_corrections or {}
    orders: list[VarietyOrder] = []

    for variety in varieties:
        prior_units = adjust_for_stockout(variety)
        bias = bias_corrections.get(variety.name, 1.0)

        raw_forecast = forecast_total_units(
            prior_year_total_units=prior_units,
            config=config,
            discount_pct=variety.discount_pct,
            elasticity_coefficient=variety.elasticity_coefficient,
            bias_correction=bias,
        )

        cases = math.ceil(raw_forecast / variety.case_pack) if variety.case_pack else 0
        order_units = cases * variety.case_pack

        min_units = variety.min_facings * variety.case_pack
        if order_units < min_units:
            order_units = min_units
            cases = math.ceil(order_units / variety.case_pack)

        orders.append(
            VarietyOrder(
                variety=variety,
                forecast_units=raw_forecast,
                order_units=order_units,
                order_cases=cases,
            )
        )

    return orders


def summarize(orders: list[VarietyOrder]) -> str:
    name_width = max(20, max((len(o.variety.name) for o in orders), default=20) + 2)
    header = f"{'Variety':<{name_width}}{'Forecast':>10}{'Order Units':>14}{'Cases':>8}"
    lines = [header, "-" * len(header)]
    for o in orders:
        lines.append(
            f"{o.variety.name:<{name_width}}{o.forecast_units:>10.1f}"
            f"{o.order_units:>14}{o.order_cases:>8}"
        )
    total_units = sum(o.order_units for o in orders)
    lines.append("-" * len(header))
    lines.append(f"{'TOTAL':<{name_width}}{'':>10}{total_units:>14}")
    return "\n".join(lines)
