import pytest

from src.crate_layout import assign_crate_layout, crate_capacity_units, summarize_crate_layout
from src.models import Crate, Variety, VarietyOrder


def make_order(name, order_units, unit_width=3.0, unit_depth=3.0, unit_height=3.0,
                min_facings=1, case_pack=1):
    variety = Variety(
        name=name, prior_year_units=order_units, case_pack=case_pack,
        unit_width_in=unit_width, unit_depth_in=unit_depth, unit_height_in=unit_height,
        min_facings=min_facings,
    )
    return VarietyOrder(
        variety=variety, forecast_units=order_units,
        order_units=order_units, order_cases=order_units // case_pack,
    )


# --- capacity math -----------------------------------------------------

def test_crate_capacity_scales_with_volume():
    small_crate = Crate(width_in=12, depth_in=12, fill_height_in=6)
    large_crate = Crate(width_in=24, depth_in=24, fill_height_in=12)
    variety = Variety(name="X", unit_width_in=3, unit_depth_in=3, unit_height_in=3)
    assert crate_capacity_units(large_crate, variety) > crate_capacity_units(small_crate, variety)


def test_crate_capacity_reflects_packing_efficiency():
    crate_tight = Crate(width_in=24, depth_in=18, fill_height_in=8, packing_efficiency=1.0)
    crate_loose = Crate(width_in=24, depth_in=18, fill_height_in=8, packing_efficiency=0.5)
    variety = Variety(name="X", unit_width_in=3, unit_depth_in=3, unit_height_in=3)
    assert crate_capacity_units(crate_tight, variety) > crate_capacity_units(crate_loose, variety)


def test_crate_capacity_missing_dimensions_falls_back_and_does_not_crash():
    crate = Crate(width_in=24, depth_in=18, fill_height_in=8)
    variety = Variety(name="NoDims")  # no unit dimensions
    assert crate_capacity_units(crate, variety) >= 0


def test_crate_capacity_negative_unit_volume_returns_zero():
    # using -1 not 0 here since `x or DEFAULT` treats 0 as "missing" too (falsy in Python)
    crate = Crate(width_in=24, depth_in=18, fill_height_in=8)
    variety = Variety(name="Negative", unit_width_in=-1, unit_depth_in=3, unit_height_in=3)
    assert crate_capacity_units(crate, variety) == 0


# --- allocation ----------------------------------------------------------

def test_no_crates_means_everything_is_backroom():
    order = make_order("Apples", 300)
    assign_crate_layout([], [order])
    assert order.crate_assignment == {}
    assert order.display_units == 0
    assert order.backroom_units == 300


def test_single_crate_single_variety_gets_assigned():
    crate = Crate(width_in=24, depth_in=18, fill_height_in=8)
    order = make_order("Apples", 50)
    assign_crate_layout([crate], [order])
    assert len(order.crate_assignment) == 1
    assert order.display_units > 0


def test_larger_order_gets_priority_for_crates():
    crates = [Crate(width_in=24, depth_in=18, fill_height_in=8) for _ in range(1)]
    big = make_order("Big", 1000)
    small = make_order("Small", 10)
    assign_crate_layout(crates, [big, small])
    # only one crate - bigger order should get it
    assert len(big.crate_assignment) == 1
    assert len(small.crate_assignment) == 0


def test_leftover_crates_stay_unassigned_once_orders_are_satisfied():
    # shouldn't hand out crates nobody needs just because they exist
    crates = [Crate(width_in=24, depth_in=18, fill_height_in=8) for _ in range(4)]
    a = make_order("A", 50)
    b = make_order("B", 30)
    assign_crate_layout(crates, [a, b])
    assert len(a.crate_assignment) >= 1
    assert len(b.crate_assignment) >= 1
    assert a.backroom_units == 0
    assert b.backroom_units == 0
    # both orders satisfied already, shouldn't need all 4
    all_indices = set(a.crate_assignment) | set(b.crate_assignment)
    assert len(all_indices) < 4


def test_crates_keep_getting_assigned_while_demand_exceeds_capacity():
    # same setup, but now demand actually exceeds capacity
    crates = [Crate(width_in=24, depth_in=18, fill_height_in=8) for _ in range(4)]
    a = make_order("A", 1000)
    b = make_order("B", 1000)
    assign_crate_layout(crates, [a, b])
    all_indices = set(a.crate_assignment) | set(b.crate_assignment)
    assert len(all_indices) == 4  # demand still exceeds capacity -- use everything


def test_min_facings_floor_not_guaranteed_when_physically_impossible():
    # only 1 crate for 2 varieties, only one can get its floor
    crates = [Crate(width_in=24, depth_in=18, fill_height_in=8)]
    a = make_order("A", 500, min_facings=1)
    b = make_order("B", 400, min_facings=1)
    assign_crate_layout(crates, [a, b])
    assigned_count = sum(1 for o in (a, b) if o.crate_assignment)
    assert assigned_count == 1  # only one variety could physically get a crate


def test_summarize_crate_layout_notes_backroom():
    crate = Crate(width_in=6, depth_in=6, fill_height_in=2)
    order = make_order("Tiny", 5000)
    assign_crate_layout([crate], [order])
    output = summarize_crate_layout([order])
    assert "restock" in output.lower()


def test_summarize_crate_layout_confirms_full_fit():
    crate = Crate(width_in=24, depth_in=18, fill_height_in=8)
    order = make_order("Small", 10)
    assign_crate_layout([crate], [order])
    output = summarize_crate_layout([order])
    assert "fits" in output.lower()
