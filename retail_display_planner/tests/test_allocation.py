import pytest

from src.allocation import allocate_by_variety
from src.models import DisplayConfig, Shelf, Variety


def make_config(**overrides):
    defaults = dict(
        shelves=[Shelf(width_in=36, depth_in=18)],
        duration_days_this_year=14,
        duration_days_prior_year=14,
        growth_target_pct=0.0,
        tie_in=False,
        tie_in_bonus_pct=0.0,
    )
    defaults.update(overrides)
    return DisplayConfig(**defaults)


def test_empty_variety_list_returns_empty():
    config = make_config()
    assert allocate_by_variety(config, []) == []


def test_orders_round_up_to_case_pack():
    config = make_config()
    varieties = [Variety(name="Chocolate", prior_year_units=100, case_pack=12)]
    orders = allocate_by_variety(config, varieties)
    assert orders[0].order_units % 12 == 0
    assert orders[0].order_units >= orders[0].forecast_units


def test_min_facings_floor_is_enforced():
    config = make_config()
    # Tiny prior sales -> raw forecast rounds to less than one case pack,
    # but min_facings=2 should still guarantee at least 2 cases worth.
    varieties = [
        Variety(name="Tapioca", prior_year_units=1, case_pack=12, min_facings=2)
    ]
    orders = allocate_by_variety(config, varieties)
    assert orders[0].order_units >= 2 * 12


def test_higher_prior_sales_yields_higher_order():
    config = make_config()
    varieties = [
        Variety(name="Chocolate", prior_year_units=500, case_pack=12),
        Variety(name="Tapioca", prior_year_units=50, case_pack=12),
    ]
    orders = allocate_by_variety(config, varieties)
    choc_order = next(o for o in orders if o.variety.name == "Chocolate")
    tapioca_order = next(o for o in orders if o.variety.name == "Tapioca")
    assert choc_order.order_units > tapioca_order.order_units


def test_discounted_variety_gets_larger_order_than_undiscounted_twin():
    config = make_config()
    varieties = [
        Variety(
            name="Discounted", prior_year_units=200, case_pack=12,
            discount_pct=0.20, elasticity_coefficient=-1.5,
        ),
        Variety(
            name="FullPrice", prior_year_units=200, case_pack=12,
            discount_pct=0.0, elasticity_coefficient=-1.5,
        ),
    ]
    orders = allocate_by_variety(config, varieties)
    discounted = next(o for o in orders if o.variety.name == "Discounted")
    full_price = next(o for o in orders if o.variety.name == "FullPrice")
    assert discounted.forecast_units > full_price.forecast_units


def test_bias_correction_applied_per_variety():
    config = make_config()
    varieties = [
        Variety(name="Chocolate", prior_year_units=500, case_pack=12),
        Variety(name="Vanilla", prior_year_units=500, case_pack=12),
    ]
    corrections = {"Chocolate": 1.5, "Vanilla": 1.0}
    orders = allocate_by_variety(config, varieties, corrections)
    choc = next(o for o in orders if o.variety.name == "Chocolate")
    van = next(o for o in orders if o.variety.name == "Vanilla")
    assert choc.forecast_units == pytest.approx(van.forecast_units * 1.5)


def test_variety_with_zero_prior_sales_still_gets_min_facings():
    config = make_config()
    varieties = [
        Variety(name="NewFlavor", prior_year_units=0, case_pack=12, min_facings=1)
    ]
    orders = allocate_by_variety(config, varieties)
    assert orders[0].order_units == 12
