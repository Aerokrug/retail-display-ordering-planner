import pytest

from src.layout import (
    assign_layout,
    facing_capacity_units,
    max_facings_on_shelf,
    shelf_visibility_weight,
    summarize_layout,
    units_per_facing,
)
from src.models import Shelf, Variety, VarietyOrder


def make_order(name, order_units, unit_width=3.0, unit_depth=3.0, unit_height=3.0,
                min_facings=1, case_pack=12):
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


def test_units_per_facing_depth_only():
    shelf = Shelf(width_in=36, depth_in=12)  # no max_stack_height_in
    variety = Variety(name="X", unit_depth_in=3.0)
    # 12 // 3 = 4 deep, height unknown -> single layer
    assert units_per_facing(shelf, variety) == 4


def test_units_per_facing_with_stacking():
    shelf = Shelf(width_in=36, depth_in=12, max_stack_height_in=9)
    variety = Variety(name="X", unit_depth_in=3.0, unit_height_in=3.0)
    # 4 deep * 3 high = 12
    assert units_per_facing(shelf, variety) == 12


def test_max_facings_on_shelf():
    shelf = Shelf(width_in=36, depth_in=12)
    variety = Variety(name="X", unit_width_in=3.0)
    assert max_facings_on_shelf(shelf, variety) == 12


def test_facing_capacity_units_combines_both():
    shelf = Shelf(width_in=36, depth_in=12, max_stack_height_in=9)
    variety = Variety(name="X", unit_width_in=3.0, unit_depth_in=3.0, unit_height_in=3.0)
    # 12 facings * 12 units/facing = 144
    assert facing_capacity_units(shelf, variety) == 144


def test_missing_dimensions_fall_back_to_default_and_dont_crash():
    shelf = Shelf(width_in=36, depth_in=12)
    variety = Variety(name="NoDims")  # no dimensions on file
    assert units_per_facing(shelf, variety) >= 1
    assert max_facings_on_shelf(shelf, variety) >= 1


def test_small_order_fits_entirely_on_display():
    shelf = Shelf(width_in=36, depth_in=18, max_stack_height_in=9)
    order = make_order("Small", order_units=12, unit_width=3.0, unit_depth=3.0, unit_height=3.0)
    assign_layout([shelf], [order])
    assert order.backroom_units == 0
    assert order.display_units == order.order_units


def test_oversized_order_leaves_backroom_units():
    shelf = Shelf(width_in=12, depth_in=12)  # small fixture
    order = make_order("Big", order_units=10_000, unit_width=3.0, unit_depth=3.0)
    assign_layout([shelf], [order])
    assert order.backroom_units > 0
    assert order.display_units + order.backroom_units == order.order_units


def test_no_shelves_means_everything_is_backroom():
    order = make_order("Any", order_units=100)
    assign_layout([], [order])
    assert order.facings == 0
    assert order.display_units == 0
    assert order.backroom_units == 100


def test_min_facings_guaranteed_when_room_exists():
    shelf = Shelf(width_in=36, depth_in=12)
    small_order = make_order(
        "Slowmover", order_units=1, unit_width=3.0, unit_depth=3.0, min_facings=2
    )
    assign_layout([shelf], [small_order])
    assert small_order.facings >= 2


def test_larger_order_gets_more_facings_than_smaller_order():
    shelf = Shelf(width_in=72, depth_in=18, max_stack_height_in=9)
    big = make_order("Big", order_units=600, unit_width=2.5, unit_depth=2.5, unit_height=3.0)
    small = make_order("Small", order_units=100, unit_width=2.5, unit_depth=2.5, unit_height=3.0)
    assign_layout([shelf], [big, small])
    assert big.facings > small.facings


def test_facings_roughly_track_order_size_ratio():
    # 4x bigger order should get noticeably more facings, not just slightly more
    shelf = Shelf(width_in=200, depth_in=18, max_stack_height_in=9)
    big = make_order("Big", order_units=800, unit_width=2.5, unit_depth=2.5, unit_height=3.0)
    small = make_order("Small", order_units=200, unit_width=2.5, unit_depth=2.5, unit_height=3.0)
    assign_layout([shelf], [big, small])
    ratio = big.facings / small.facings
    assert ratio > 1.5  # meaningfully more, not flattened to ~equal by round-robin


def test_summarize_layout_notes_backroom_when_present():
    shelf = Shelf(width_in=6, depth_in=6)
    order = make_order("Tiny Shelf", order_units=1000, unit_width=3.0, unit_depth=3.0)
    assign_layout([shelf], [order])
    output = summarize_layout([order])
    assert "restock" in output.lower()


def test_summarize_layout_confirms_full_fit_when_no_backroom():
    shelf = Shelf(width_in=36, depth_in=18, max_stack_height_in=9)
    order = make_order("Fits", order_units=12, unit_width=3.0, unit_depth=3.0, unit_height=3.0)
    assign_layout([shelf], [order])
    output = summarize_layout([order])
    assert "fits" in output.lower()


def test_summarize_layout_shelves_column_does_not_overflow_for_wide_spans():
    # regression test - facings count used to run into the shelf list with no space
    import re

    shelves = [Shelf(width_in=10, depth_in=18) for _ in range(5)]
    order = make_order("SpreadThin", order_units=5000, unit_width=2.5, unit_depth=2.5, min_facings=1)
    assign_layout(shelves, [order])
    output = summarize_layout([order])

    for line in output.splitlines():
        if "SpreadThin" in line:
            assert not re.search(r"\d#", line), f"digit ran into '#' with no space: {line!r}"


# --- Eye-level / visibility weighting -------------------------------------

def test_middle_upper_shelf_outweighs_top_and_bottom():
    # ~30% down from the top should score highest
    shelves = [Shelf(width_in=36, depth_in=18) for _ in range(4)]
    weights = [shelf_visibility_weight(s, i, 4) for i, s in enumerate(shelves)]
    eye_level_idx = weights.index(max(weights))
    assert eye_level_idx not in (0, 3)  # not the very top or very bottom shelf


def test_manual_visibility_weight_overrides_default():
    shelf = Shelf(width_in=36, depth_in=18, visibility_weight=99.0)
    assert shelf_visibility_weight(shelf, 3, 4) == 99.0  # ignores position heuristic


def test_best_seller_claims_the_highest_visibility_shelf():
    # top seller should land on whichever shelf scores highest, not just shelf 0
    shelves = [Shelf(width_in=36, depth_in=18) for _ in range(3)]
    weights = [shelf_visibility_weight(s, i, 3) for i, s in enumerate(shelves)]
    best_shelf_idx = weights.index(max(weights))

    top_seller = make_order("BestSeller", order_units=100, unit_width=3.0, unit_depth=3.0)
    assign_layout(shelves, [top_seller])

    # best-visibility shelf should hold the most facings
    assert top_seller.shelf_breakdown.get(best_shelf_idx, 0) == max(
        top_seller.shelf_breakdown.values()
    )


def test_facings_stay_on_one_shelf_when_they_fit():
    # shouldn't scatter across shelves if it fits on one
    shelves = [Shelf(width_in=36, depth_in=18) for _ in range(4)]
    small_order = make_order("Compact", order_units=24, unit_width=3.0, unit_depth=3.0, case_pack=12)
    assign_layout(shelves, [small_order])
    assert len(small_order.shelf_breakdown) == 1


def test_variety_spills_to_next_shelf_only_when_first_is_full():
    # too big for one shelf - should still use as few shelves as possible
    shelves = [Shelf(width_in=36, depth_in=18) for _ in range(4)]
    big_order = make_order(
        "BigSeller", order_units=1200, unit_width=2.5, unit_depth=2.5, case_pack=12
    )
    assign_layout(shelves, [big_order])
    # should fill whole shelves before spilling to the next one
    facings_per_shelf = list(big_order.shelf_breakdown.values())
    # each shelf used should be near capacity, not just a token few facings
    assert all(count >= 10 for count in facings_per_shelf[:-1]) or len(facings_per_shelf) <= 1
