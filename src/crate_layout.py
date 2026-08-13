"""
Bulk bin displays - produce bins, candy bins, that sort of thing.
Whole crates get assigned to one variety at a time (mixing products
in one bin doesn't really happen in practice).

No LP here like the shelf version has - with only a handful of crates
this doesn't need it, greedy priority works fine.
"""

from dataclasses import dataclass

from src.models import Crate, Variety, VarietyOrder

DEFAULT_UNIT_DIM_IN = 3.0


def crate_capacity_units(crate: Crate, variety: Variety) -> int:
    # accounts for packing_efficiency since dumped product leaves gaps
    width = variety.unit_width_in or DEFAULT_UNIT_DIM_IN
    depth = variety.unit_depth_in or DEFAULT_UNIT_DIM_IN
    height = variety.unit_height_in or DEFAULT_UNIT_DIM_IN

    crate_volume = crate.width_in * crate.depth_in * crate.fill_height_in
    unit_volume = width * depth * height
    if unit_volume <= 0:
        return 0

    raw_capacity = crate_volume / unit_volume
    return max(0, int(raw_capacity * crate.packing_efficiency))


@dataclass
class _CrateState:
    index: int
    crate: Crate
    assigned_variety_name: str | None = None


def assign_crate_layout(
    crates: list[Crate],
    orders: list[VarietyOrder],
) -> list[VarietyOrder]:
    """
    Two passes: first give every variety with min_facings>=1 a crate if
    one's free (biggest orders first), then hand out whatever's left to
    whoever still needs the most.
    """
    if not crates or not orders:
        for o in orders:
            o.crate_assignment = {}
            o.display_units = 0
            o.backroom_units = o.order_units
        return orders

    crate_states = [_CrateState(i, c) for i, c in enumerate(crates)]
    for o in orders:
        o.crate_assignment = {}

    def unassigned_crates():
        return [cs for cs in crate_states if cs.assigned_variety_name is None]

    def remaining_need(order: VarietyOrder) -> int:
        assigned = sum(order.crate_assignment.values())
        return order.order_units - assigned

    priority = sorted(orders, key=lambda o: o.order_units, reverse=True)

    # pass 1 - floor guarantee
    for order in priority:
        if order.variety.min_facings < 1:
            continue
        pool = unassigned_crates()
        if not pool or remaining_need(order) <= 0:
            continue
        crate_state = pool[0]
        crate_state.assigned_variety_name = order.variety.name
        order.crate_assignment[crate_state.index] = crate_capacity_units(
            crate_state.crate, order.variety
        )

    # pass 2 - give leftover crates to whoever needs them most
    progress = True
    while progress:
        progress = False
        pool = unassigned_crates()
        if not pool:
            break
        candidates = [o for o in priority if remaining_need(o) > 0]
        if not candidates:
            break
        candidates.sort(key=remaining_need, reverse=True)
        order = candidates[0]
        crate_state = pool[0]
        crate_state.assigned_variety_name = order.variety.name
        order.crate_assignment[crate_state.index] = crate_capacity_units(
            crate_state.crate, order.variety
        )
        progress = True

    for order in orders:
        capacity = sum(order.crate_assignment.values())
        order.display_units = min(order.order_units, capacity)
        order.backroom_units = order.order_units - order.display_units

    return orders


def summarize_crate_layout(orders: list[VarietyOrder]) -> str:
    name_width = max(20, max((len(o.variety.name) for o in orders), default=20) + 2)
    header = f"{'Variety':<{name_width}}{'Crates':>8}{'On Display':>12}{'Backroom':>10}"
    lines = [header, "-" * len(header)]
    for o in orders:
        crate_count = len(o.crate_assignment)
        lines.append(
            f"{o.variety.name:<{name_width}}{crate_count:>8}"
            f"{o.display_units:>12}{o.backroom_units:>10}"
        )
    total_backroom = sum(o.backroom_units for o in orders)
    lines.append("-" * len(header))
    if total_backroom > 0:
        lines.append(
            f"Note: {total_backroom} units won't fit in the crates initially "
            "-- plan for a mid-run restock."
        )
    else:
        lines.append("Full order fits in the crates at once.")
    return "\n".join(lines)
