"""Shelf capacity + facing placement."""

import math
from dataclasses import dataclass

from src.models import Shelf, Variety, VarietyOrder

DEFAULT_UNIT_DIM_IN = 3.0

# TODO: units_per_facing always uses shelves[0] for the math, so this
# breaks if you mix shelf sizes on one fixture. haven't hit that case yet


@dataclass
class _ShelfState:
    index: int
    shelf: Shelf
    remaining_width_in: float


def units_per_facing(shelf: Shelf, variety: Variety) -> int:
    depth = variety.unit_depth_in or DEFAULT_UNIT_DIM_IN
    depth_fit = max(1, int(shelf.depth_in // depth))

    if shelf.max_stack_height_in and variety.unit_height_in:
        height_fit = max(1, int(shelf.max_stack_height_in // variety.unit_height_in))
    else:
        height_fit = 1

    return depth_fit * height_fit


def max_facings_on_shelf(shelf: Shelf, variety: Variety) -> int:
    width = variety.unit_width_in or DEFAULT_UNIT_DIM_IN
    return max(1, int(shelf.width_in // width))


def facing_capacity_units(shelf: Shelf, variety: Variety) -> int:
    return max_facings_on_shelf(shelf, variety) * units_per_facing(shelf, variety)


def shelf_visibility_weight(shelf: Shelf, index: int, num_shelves: int) -> float:
    # eye level ~30% down from the top scores highest, tapers off toward
    # top/bottom. made this number up based on general merchandising
    # advice, not real data - override Shelf.visibility_weight if you
    # actually know how a shelf performs
    if shelf.visibility_weight is not None:
        return shelf.visibility_weight

    if num_shelves <= 1:
        return 1.0

    ideal_index = 0.3 * (num_shelves - 1)
    sigma = max(num_shelves / 2.5, 0.75)
    return math.exp(-((index - ideal_index) ** 2) / (2 * sigma ** 2))


def _compute_facing_targets(
    shelves: list[Shelf],
    orders: list[VarietyOrder],
) -> tuple[dict, dict]:
    # largest-remainder split proportional to order size, floored at
    # min_facings, capped at what the variety could actually use
    total_width = sum(s.width_in for s in shelves)
    avg_width = sum(
        (o.variety.unit_width_in or DEFAULT_UNIT_DIM_IN) for o in orders
    ) / len(orders)
    capacity_facings = int(total_width // avg_width) if avg_width else 0

    total_order_units = sum(o.order_units for o in orders) or 1

    facings_wanted = {}
    ideal_shares = {}
    for order in orders:
        per_facing = units_per_facing(shelves[0], order.variety)
        facings_wanted[id(order)] = (
            math.ceil(order.order_units / per_facing) if per_facing else 1
        )
        ideal_shares[id(order)] = capacity_facings * (order.order_units / total_order_units)

    targets = {}
    for order in orders:
        floor = order.variety.min_facings
        capped = min(ideal_shares[id(order)], facings_wanted[id(order)])
        targets[id(order)] = max(floor, capped)

    return targets, facings_wanted


def assign_layout(
    shelves: list[Shelf],
    orders: list[VarietyOrder],
    target_facings: dict | None = None,
) -> list[VarietyOrder]:
    if not shelves or not orders:
        for o in orders:
            o.facings = 0
            o.display_units = 0
            o.backroom_units = o.order_units
            o.shelf_breakdown = {}
        return orders

    shelf_states = [_ShelfState(i, s, s.width_in) for i, s in enumerate(shelves)]
    num_shelves = len(shelves)
    visibility_order = sorted(
        range(num_shelves),
        key=lambda i: shelf_visibility_weight(shelves[i], i, num_shelves),
        reverse=True,
    )

    if target_facings is not None:
        targets = {id(o): target_facings.get(o.variety.name, 0) for o in orders}
    else:
        targets, _facings_wanted = _compute_facing_targets(shelves, orders)

    # biggest priority picks its shelf first, and fills it before spilling
    # to the next one - keeps facings together instead of scattered everywhere
    priority = sorted(orders, key=lambda o: targets[id(o)], reverse=True)

    for order in priority:
        order.facings = 0
        order.shelf_breakdown = {}
        needed_width = order.variety.unit_width_in or DEFAULT_UNIT_DIM_IN
        remaining = int(round(targets[id(order)]))

        for shelf_idx in visibility_order:
            if remaining <= 0:
                break
            state = shelf_states[shelf_idx]
            while remaining > 0 and state.remaining_width_in >= needed_width:
                state.remaining_width_in -= needed_width
                order.facings += 1
                order.shelf_breakdown[shelf_idx] = order.shelf_breakdown.get(shelf_idx, 0) + 1
                remaining -= 1
            # no break here on purpose, keep going to the next shelf for the remainder

    for order in orders:
        per_facing = units_per_facing(shelves[0], order.variety)
        capacity = order.facings * per_facing
        order.display_units = min(order.order_units, capacity)
        order.backroom_units = order.order_units - order.display_units

    return orders


def summarize_layout(orders: list[VarietyOrder]) -> str:
    name_width = max(20, max((len(o.variety.name) for o in orders), default=20) + 2)

    shelves_strs = {
        id(o): (
            ", ".join(f"#{idx + 1}:{count}" for idx, count in sorted(o.shelf_breakdown.items()))
            or "-"
        )
        for o in orders
    }
    shelves_width = max(9, max((len(s) for s in shelves_strs.values()), default=9) + 2)

    header = (
        f"{'Variety':<{name_width}}{'Facings':>9}{'Shelves':>{shelves_width}}"
        f"{'On Display':>12}{'Backroom':>10}"
    )
    lines = [header, "-" * len(header)]
    for o in orders:
        lines.append(
            f"{o.variety.name:<{name_width}}{o.facings:>9}{shelves_strs[id(o)]:>{shelves_width}}"
            f"{o.display_units:>12}{o.backroom_units:>10}"
        )
    total_backroom = sum(o.backroom_units for o in orders)
    lines.append("-" * len(header))
    if total_backroom > 0:
        lines.append(
            f"Note: {total_backroom} units won't fit on the display initially "
            "-- plan for a mid-run restock."
        )
    else:
        lines.append("Full order fits on the display at once.")
    return "\n".join(lines)
