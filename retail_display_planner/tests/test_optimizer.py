import pytest

from src.layout import _compute_facing_targets
from src.optimizer import marginal_value, optimize_facing_counts
from src.models import Shelf, Variety, VarietyOrder


def make_order(name, order_units, unit_width=2.5, unit_depth=2.5,
                unit_height=None, min_facings=1, case_pack=12):
    variety = Variety(
        name=name,
        prior_year_units=order_units,
        case_pack=case_pack,
        unit_width_in=unit_width,
        unit_depth_in=unit_depth,
        unit_height_in=unit_height,
        min_facings=min_facings,
    )
    return VarietyOrder(
        variety=variety,
        forecast_units=order_units,
        order_units=order_units,
        order_cases=order_units // case_pack,
    )


def test_marginal_value_decreases_with_facing_number():
    shelf = Shelf(width_in=36, depth_in=18)
    order = make_order("X", order_units=500)
    v1 = marginal_value(order, 1, shelf)
    v2 = marginal_value(order, 2, shelf)
    v5 = marginal_value(order, 5, shelf)
    assert v1 > v2 > v5 > 0


def test_marginal_value_is_positive_for_first_facing():
    shelf = Shelf(width_in=36, depth_in=18)
    order = make_order("X", order_units=100)
    assert marginal_value(order, 1, shelf) > 0


def test_optimizer_respects_total_shelf_width():
    shelves = [Shelf(width_in=20, depth_in=18)]
    orders = [make_order("A", 1000), make_order("B", 1000)]
    result = optimize_facing_counts(shelves, orders)
    total_width_used = sum(
        count * 2.5 for count in result.values()
    )
    assert total_width_used <= 20 + 1e-6


def test_optimizer_returns_zero_for_empty_inputs():
    assert optimize_facing_counts([], []) == {}
    assert optimize_facing_counts([Shelf(width_in=36, depth_in=18)], []) == {}


def test_optimizer_enforces_min_facings_when_physically_possible():
    shelves = [Shelf(width_in=100, depth_in=18)]  # plenty of room
    orders = [
        make_order("Big", 1000),
        make_order("TinyButRequired", 1, min_facings=2),
    ]
    result = optimize_facing_counts(shelves, orders)
    assert result["TinyButRequired"] >= 2


def test_optimizer_uses_more_capacity_than_proportional_heuristic_when_it_matters():
    # same order size, very different facings-needed (one stacks high, one can't).
    # proportional split wastes capacity here, LP shouldn't.
    shelf = Shelf(width_in=60, depth_in=18, max_stack_height_in=15)
    stacks_high = make_order("StacksHigh", 200, unit_width=2.0, unit_depth=2.0, unit_height=3.0)
    no_stack = make_order("NoStack", 200, unit_width=2.0, unit_depth=2.0, unit_height=None)

    prop_targets, _ = _compute_facing_targets([shelf], [stacks_high, no_stack])
    proportional_total = sum(prop_targets.values())

    lp_result = optimize_facing_counts([shelf], [stacks_high, no_stack])
    lp_total = sum(lp_result.values())

    assert lp_total > proportional_total
    # LP should use the full available capacity instead of leaving it idle
    assert lp_result["NoStack"] > prop_targets[id(no_stack)]


def test_optimizer_never_exceeds_facings_needed_to_display_full_order():
    # no point giving more facings than needed to show the whole order
    shelves = [Shelf(width_in=500, depth_in=18)]  # effectively unlimited
    order = make_order("Small", order_units=24, case_pack=12)  # needs few facings
    result = optimize_facing_counts(shelves, [order])
    # facings_needed works out to 24 here, shouldn't exceed that even with room to spare
    assert result["Small"] <= 24
