"""
Freestanding case-stack displays (pallet displays, case pyramids).
Capacity is in whole cases - how many fit across the base times how
many layers fit in the height. Same greedy two-pass approach as
crate_layout.py, no LP.
"""

from dataclasses import dataclass

from src.models import SideStack, Variety, VarietyOrder

# generic case footprint if a variety doesn't have real case dims on file
DEFAULT_CASE_WIDTH_IN = 12.0
DEFAULT_CASE_DEPTH_IN = 12.0
DEFAULT_CASE_HEIGHT_IN = 10.0


def estimate_case_dimensions(variety: Variety) -> tuple[float, float, float]:
    return (
        variety.case_width_in or DEFAULT_CASE_WIDTH_IN,
        variety.case_depth_in or DEFAULT_CASE_DEPTH_IN,
        variety.case_height_in or DEFAULT_CASE_HEIGHT_IN,
    )


def stack_capacity_cases(stack: SideStack, variety: Variety) -> int:
    case_w, case_d, case_h = estimate_case_dimensions(variety)
    if case_w <= 0 or case_d <= 0 or case_h <= 0:
        return 0

    cases_per_layer = max(0, int(stack.base_width_in // case_w)) * max(
        0, int(stack.base_depth_in // case_d)
    )
    layers = max(0, int(stack.max_height_in // case_h))
    return cases_per_layer * layers


@dataclass
class _StackState:
    index: int
    stack: SideStack
    assigned_variety_name: str | None = None


def assign_stack_layout(
    stacks: list[SideStack],
    orders: list[VarietyOrder],
) -> list[VarietyOrder]:
    """Same two-pass floor-then-priority approach as assign_crate_layout."""
    if not stacks or not orders:
        for o in orders:
            o.stack_assignment = {}
            o.display_units = 0
            o.backroom_units = o.order_units
        return orders

    stack_states = [_StackState(i, s) for i, s in enumerate(stacks)]
    for o in orders:
        o.stack_assignment = {}

    def cases_assigned_units(order: VarietyOrder) -> int:
        cases = sum(order.stack_assignment.values())
        return cases * max(order.variety.case_pack, 1)

    def unassigned_stacks():
        return [ss for ss in stack_states if ss.assigned_variety_name is None]

    def remaining_need(order: VarietyOrder) -> int:
        return order.order_units - cases_assigned_units(order)

    priority = sorted(orders, key=lambda o: o.order_units, reverse=True)

    for order in priority:
        if order.variety.min_facings < 1:
            continue
        pool = unassigned_stacks()
        if not pool or remaining_need(order) <= 0:
            continue
        stack_state = pool[0]
        stack_state.assigned_variety_name = order.variety.name
        order.stack_assignment[stack_state.index] = stack_capacity_cases(
            stack_state.stack, order.variety
        )

    progress = True
    while progress:
        progress = False
        pool = unassigned_stacks()
        if not pool:
            break
        candidates = [o for o in priority if remaining_need(o) > 0]
        if not candidates:
            break
        candidates.sort(key=remaining_need, reverse=True)
        order = candidates[0]
        stack_state = pool[0]
        stack_state.assigned_variety_name = order.variety.name
        order.stack_assignment[stack_state.index] = stack_capacity_cases(
            stack_state.stack, order.variety
        )
        progress = True

    for order in orders:
        capacity_units = cases_assigned_units(order)
        order.display_units = min(order.order_units, capacity_units)
        order.backroom_units = order.order_units - order.display_units

    return orders


def summarize_stack_layout(orders: list[VarietyOrder]) -> str:
    name_width = max(20, max((len(o.variety.name) for o in orders), default=20) + 2)
    header = f"{'Variety':<{name_width}}{'Stacks':>8}{'Cases':>8}{'On Display':>12}{'Backroom':>10}"
    lines = [header, "-" * len(header)]
    for o in orders:
        stack_count = len(o.stack_assignment)
        case_count = sum(o.stack_assignment.values())
        lines.append(
            f"{o.variety.name:<{name_width}}{stack_count:>8}{case_count:>8}"
            f"{o.display_units:>12}{o.backroom_units:>10}"
        )
    total_backroom = sum(o.backroom_units for o in orders)
    lines.append("-" * len(header))
    if total_backroom > 0:
        lines.append(
            f"Note: {total_backroom} units won't fit on the stacks initially "
            "-- plan for a mid-run restock."
        )
    else:
        lines.append("Full order fits on the stacks at once.")
    return "\n".join(lines)
