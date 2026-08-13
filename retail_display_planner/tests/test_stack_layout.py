import pytest

from src.models import SideStack, Variety, VarietyOrder
from src.stack_layout import (
    assign_stack_layout,
    estimate_case_dimensions,
    stack_capacity_cases,
    summarize_stack_layout,
)


def make_order(name, order_units, case_pack=24, case_width=16, case_depth=12,
                case_height=10, min_facings=1):
    variety = Variety(
        name=name, prior_year_units=order_units, case_pack=case_pack,
        case_width_in=case_width, case_depth_in=case_depth, case_height_in=case_height,
        min_facings=min_facings,
    )
    return VarietyOrder(
        variety=variety, forecast_units=order_units,
        order_units=order_units, order_cases=order_units // case_pack,
    )


# --- case dimension estimation -----------------------------------------

def test_estimate_case_dimensions_uses_explicit_values():
    variety = Variety(name="X", case_width_in=20, case_depth_in=15, case_height_in=12)
    assert estimate_case_dimensions(variety) == (20, 15, 12)


def test_estimate_case_dimensions_falls_back_when_missing():
    variety = Variety(name="X")  # no case dimensions provided
    w, d, h = estimate_case_dimensions(variety)
    assert w > 0 and d > 0 and h > 0  # some sane default, not zero/crash


# --- capacity math -----------------------------------------------------

def test_stack_capacity_scales_with_base_area():
    small_stack = SideStack(base_width_in=20, base_depth_in=20, max_height_in=60)
    large_stack = SideStack(base_width_in=60, base_depth_in=60, max_height_in=60)
    variety = Variety(name="X", case_width_in=16, case_depth_in=12, case_height_in=10)
    assert stack_capacity_cases(large_stack, variety) > stack_capacity_cases(small_stack, variety)


def test_stack_capacity_scales_with_height():
    short_stack = SideStack(base_width_in=40, base_depth_in=40, max_height_in=20)
    tall_stack = SideStack(base_width_in=40, base_depth_in=40, max_height_in=80)
    variety = Variety(name="X", case_width_in=16, case_depth_in=12, case_height_in=10)
    assert stack_capacity_cases(tall_stack, variety) > stack_capacity_cases(short_stack, variety)


def test_stack_capacity_zero_when_case_too_big_for_base():
    stack = SideStack(base_width_in=10, base_depth_in=10, max_height_in=60)
    variety = Variety(name="X", case_width_in=16, case_depth_in=12, case_height_in=10)
    assert stack_capacity_cases(stack, variety) == 0


def test_stack_capacity_missing_case_dims_falls_back_and_does_not_crash():
    stack = SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)
    variety = Variety(name="NoDims")
    assert stack_capacity_cases(stack, variety) >= 0


# --- allocation ----------------------------------------------------------

def test_no_stacks_means_everything_is_backroom():
    order = make_order("Soda", 1000)
    assign_stack_layout([], [order])
    assert order.stack_assignment == {}
    assert order.backroom_units == 1000


def test_single_stack_single_variety_gets_assigned():
    stack = SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)
    order = make_order("Soda", 500)
    assign_stack_layout([stack], [order])
    assert len(order.stack_assignment) == 1
    assert order.display_units > 0


def test_larger_order_gets_priority_for_stacks():
    stacks = [SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)]
    big = make_order("Big", 5000)
    small = make_order("Small", 100)
    assign_stack_layout(stacks, [big, small])
    assert len(big.stack_assignment) == 1
    assert len(small.stack_assignment) == 0


def test_display_units_reflect_cases_times_case_pack():
    stack = SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)
    order = make_order("Soda", 100000, case_pack=24)  # deliberately huge order
    assign_stack_layout([stack], [order])
    cases = sum(order.stack_assignment.values())
    assert order.display_units == cases * 24


def test_min_facings_floor_not_guaranteed_when_physically_impossible():
    stacks = [SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)]
    a = make_order("A", 5000, min_facings=1)
    b = make_order("B", 4000, min_facings=1)
    assign_stack_layout(stacks, [a, b])
    assigned_count = sum(1 for o in (a, b) if o.stack_assignment)
    assert assigned_count == 1  # only 1 stack exists for 2 varieties


def test_summarize_stack_layout_notes_backroom():
    stack = SideStack(base_width_in=10, base_depth_in=10, max_height_in=10)
    order = make_order("Tiny", 100000)
    assign_stack_layout([stack], [order])
    output = summarize_stack_layout([order])
    assert "restock" in output.lower()


def test_summarize_stack_layout_confirms_full_fit():
    stack = SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)
    order = make_order("Small", 100)
    assign_stack_layout([stack], [order])
    output = summarize_stack_layout([order])
    assert "fits" in output.lower()
