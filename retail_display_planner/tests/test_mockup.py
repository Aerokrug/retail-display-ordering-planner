import os

import pytest

from src.layout import assign_layout
from src.mockup import draw_planogram
from src.models import Shelf, Variety, VarietyOrder


def make_order(name, order_units, unit_width=3.0, unit_depth=3.0, min_facings=1):
    variety = Variety(
        name=name,
        prior_year_units=order_units,
        case_pack=12,
        unit_width_in=unit_width,
        unit_depth_in=unit_depth,
        min_facings=min_facings,
    )
    return VarietyOrder(
        variety=variety,
        forecast_units=order_units,
        order_units=order_units,
        order_cases=order_units // 12,
    )


def test_draw_planogram_creates_file(tmp_path):
    shelves = [Shelf(width_in=36, depth_in=18)]
    orders = [make_order("Chocolate", 120), make_order("Vanilla", 60)]
    assign_layout(shelves, orders)

    output_path = str(tmp_path / "test_planogram.png")
    result = draw_planogram(shelves, orders, output_path=output_path)

    assert result == output_path
    assert os.path.isfile(output_path)
    assert os.path.getsize(output_path) > 0


def test_draw_planogram_raises_without_shelves():
    orders = [make_order("Chocolate", 120)]
    with pytest.raises(ValueError):
        draw_planogram([], orders)


def test_draw_planogram_raises_if_layout_not_assigned_first(tmp_path):
    # orders with facings but no shelf_breakdown populated -- forgot to
    # call assign_layout() first
    shelves = [Shelf(width_in=36, depth_in=18)]
    order = make_order("Chocolate", 120)
    order.facings = 5  # simulate a forgotten assign_layout call
    with pytest.raises(ValueError):
        draw_planogram(shelves, [order], output_path=str(tmp_path / "x.png"))


def test_draw_planogram_handles_multiple_shelves(tmp_path):
    shelves = [Shelf(width_in=36, depth_in=18) for _ in range(4)]
    orders = [
        make_order("Chocolate", 600),
        make_order("Vanilla", 400),
        make_order("Butterscotch", 150),
    ]
    assign_layout(shelves, orders)
    output_path = str(tmp_path / "multi_shelf.png")
    draw_planogram(shelves, orders, output_path=output_path)
    assert os.path.isfile(output_path)


def test_draw_planogram_handles_backroom_overflow_without_crashing(tmp_path):
    # Deliberately too-small fixture so some units can't fit -- should
    # still render, not raise.
    shelves = [Shelf(width_in=6, depth_in=6)]
    order = make_order("Big", 5000, unit_width=3.0, unit_depth=3.0)
    assign_layout(shelves, [order])
    output_path = str(tmp_path / "overflow.png")
    draw_planogram(shelves, [order], output_path=output_path)
    assert os.path.isfile(output_path)
    assert order.backroom_units > 0
