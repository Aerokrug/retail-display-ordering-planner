import os

import pytest

from src.crate_layout import assign_crate_layout
from src.mockup import draw_crate_mockup, draw_mockup, draw_stack_mockup
from src.models import Crate, DisplayConfig, Shelf, SideStack, Variety, VarietyOrder
from src.stack_layout import assign_stack_layout


def make_crate_order(name, order_units):
    variety = Variety(
        name=name, prior_year_units=order_units, case_pack=1,
        unit_width_in=3, unit_depth_in=3, unit_height_in=3,
    )
    return VarietyOrder(
        variety=variety, forecast_units=order_units,
        order_units=order_units, order_cases=order_units,
    )


def make_stack_order(name, order_units):
    variety = Variety(
        name=name, prior_year_units=order_units, case_pack=24,
        case_width_in=16, case_depth_in=12, case_height_in=10,
    )
    return VarietyOrder(
        variety=variety, forecast_units=order_units,
        order_units=order_units, order_cases=order_units // 24,
    )


# --- crate mockup --------------------------------------------------------

def test_draw_crate_mockup_creates_file(tmp_path):
    crates = [Crate(width_in=24, depth_in=18, fill_height_in=8) for _ in range(2)]
    orders = [make_crate_order("Apples", 300), make_crate_order("Limes", 150)]
    assign_crate_layout(crates, orders)

    output_path = str(tmp_path / "crate.png")
    result = draw_crate_mockup(crates, orders, output_path=output_path)
    assert result == output_path
    assert os.path.isfile(output_path)
    assert os.path.getsize(output_path) > 0


def test_draw_crate_mockup_raises_without_crates():
    orders = [make_crate_order("Apples", 300)]
    with pytest.raises(ValueError):
        draw_crate_mockup([], orders)


def test_draw_crate_mockup_handles_unassigned_crates(tmp_path):
    # More crates than needed -- some should stay unassigned, shouldn't crash.
    crates = [Crate(width_in=24, depth_in=18, fill_height_in=8) for _ in range(5)]
    orders = [make_crate_order("Apples", 10)]
    assign_crate_layout(crates, orders)
    output_path = str(tmp_path / "crate.png")
    draw_crate_mockup(crates, orders, output_path=output_path)
    assert os.path.isfile(output_path)


# --- stack mockup --------------------------------------------------------

def test_draw_stack_mockup_creates_file(tmp_path):
    stacks = [SideStack(base_width_in=40, base_depth_in=40, max_height_in=60) for _ in range(2)]
    orders = [make_stack_order("Cola", 3000), make_stack_order("RootBeer", 500)]
    assign_stack_layout(stacks, orders)

    output_path = str(tmp_path / "stack.png")
    result = draw_stack_mockup(stacks, orders, output_path=output_path)
    assert result == output_path
    assert os.path.isfile(output_path)
    assert os.path.getsize(output_path) > 0


def test_draw_stack_mockup_raises_without_stacks():
    orders = [make_stack_order("Cola", 3000)]
    with pytest.raises(ValueError):
        draw_stack_mockup([], orders)


def test_draw_stack_mockup_handles_zero_cases_assigned(tmp_path):
    # Not enough stacks for every variety -- one gets zero cases, shouldn't crash.
    stacks = [SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)]
    orders = [make_stack_order("Cola", 5000), make_stack_order("RootBeer", 4000)]
    assign_stack_layout(stacks, orders)
    output_path = str(tmp_path / "stack.png")
    draw_stack_mockup(stacks, orders, output_path=output_path)
    assert os.path.isfile(output_path)


# --- dispatcher ------------------------------------------------------------

def test_draw_mockup_dispatches_to_shelf_renderer(tmp_path):
    config = DisplayConfig(fixture_type="shelf", shelves=[Shelf(width_in=36, depth_in=18)])
    variety = Variety(name="X", case_pack=12, unit_width_in=3, unit_depth_in=3)
    order = VarietyOrder(variety=variety, forecast_units=50, order_units=50, order_cases=5)
    from src.layout import assign_layout
    assign_layout(config.shelves, [order])

    output_path = str(tmp_path / "dispatch_shelf.png")
    result = draw_mockup(config, [order], output_path=output_path)
    assert result == output_path
    assert os.path.isfile(output_path)


def test_draw_mockup_dispatches_to_crate_renderer(tmp_path):
    config = DisplayConfig(
        fixture_type="crate",
        crates=[Crate(width_in=24, depth_in=18, fill_height_in=8)],
    )
    order = make_crate_order("Apples", 100)
    assign_crate_layout(config.crates, [order])

    output_path = str(tmp_path / "dispatch_crate.png")
    result = draw_mockup(config, [order], output_path=output_path)
    assert result == output_path
    assert os.path.isfile(output_path)


def test_draw_mockup_dispatches_to_stack_renderer(tmp_path):
    config = DisplayConfig(
        fixture_type="side_stack",
        side_stacks=[SideStack(base_width_in=40, base_depth_in=40, max_height_in=60)],
    )
    order = make_stack_order("Cola", 500)
    assign_stack_layout(config.side_stacks, [order])

    output_path = str(tmp_path / "dispatch_stack.png")
    result = draw_mockup(config, [order], output_path=output_path)
    assert result == output_path
    assert os.path.isfile(output_path)


def test_draw_mockup_raises_for_unknown_fixture_type():
    config = DisplayConfig(fixture_type="not_a_real_type")
    with pytest.raises(ValueError):
        draw_mockup(config, [])
