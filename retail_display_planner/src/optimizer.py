"""
LP facing optimizer - how many facings should each variety get to
maximize expected sales, instead of the plain proportional split
layout.py falls back to. Only picks counts, not which shelf - layout.py
still handles placement, tried combining both into one MILP and it
wasn't worth the headache.
"""

import math

import pulp

from src.layout import DEFAULT_UNIT_DIM_IN, units_per_facing
from src.models import Shelf, VarietyOrder


def marginal_value(
    order: VarietyOrder,
    facing_number: int,
    shelf: Shelf,
    decay_fraction: float = 0.35,
) -> float:
    # saturating curve: cumulative_sales(f) = order_units * (1 - exp(-f / f0))
    # first few facings matter a lot, extra ones barely move the needle.
    # totally made-up curve shape honestly, no facings-vs-sales data to fit
    # a real one from yet
    per_facing = units_per_facing(shelf, order.variety)
    facings_needed = math.ceil(order.order_units / per_facing) if per_facing else 1
    f0 = max(decay_fraction * facings_needed, 0.5)

    def cumulative(f):
        return order.order_units * (1 - math.exp(-f / f0))

    return cumulative(facing_number) - cumulative(facing_number - 1)


def optimize_facing_counts(
    shelves: list[Shelf],
    orders: list[VarietyOrder],
    decay_fraction: float = 0.35,
) -> dict:
    """
    Returns {variety_name: facing_count} maximizing total expected
    sales subject to total shelf width. Feed straight into
    layout.assign_layout(shelves, orders, target_facings=...).

    min_facings gets enforced as a hard constraint only if every
    variety's floor fits simultaneously - otherwise we don't force it
    and let the LP figure out the best it can.
    """
    if not shelves or not orders:
        return {}

    total_width = sum(s.width_in for s in shelves)
    reference_shelf = shelves[0]

    total_min_width = sum(
        o.variety.min_facings * (o.variety.unit_width_in or DEFAULT_UNIT_DIM_IN)
        for o in orders
    )
    enforce_min_facings = total_min_width <= total_width

    problem = pulp.LpProblem("facing_allocation", pulp.LpMaximize)

    slot_vars = {}
    objective_terms = []
    width_terms = []

    for order in orders:
        per_facing = units_per_facing(reference_shelf, order.variety)
        facings_needed = math.ceil(order.order_units / per_facing) if per_facing else 1
        # need at least min_facings slots even if the order is tiny, or the
        # constraint below has nothing to bind against
        max_k = max(facings_needed, order.variety.min_facings)
        needed_width = order.variety.unit_width_in or DEFAULT_UNIT_DIM_IN

        variables = []
        for k in range(1, max_k + 1):
            var = pulp.LpVariable(f"y_{order.variety.name}_{k}", cat="Binary")
            variables.append(var)
            value = marginal_value(order, k, reference_shelf, decay_fraction)
            objective_terms.append(value * var)
            width_terms.append(needed_width * var)
        slot_vars[order.variety.name] = variables

        if enforce_min_facings and order.variety.min_facings > 0:
            floor = min(order.variety.min_facings, len(variables))
            if floor > 0:
                problem += pulp.lpSum(variables[:floor]) == floor

    problem += pulp.lpSum(objective_terms)
    problem += pulp.lpSum(width_terms) <= total_width

    problem.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[problem.status] != "Optimal":
        raise RuntimeError(
            f"LP solver did not find an optimal solution "
            f"(status: {pulp.LpStatus[problem.status]})"
        )

    return {
        name: sum(1 for v in variables if pulp.value(v) and pulp.value(v) > 0.5)
        for name, variables in slot_vars.items()
    }
