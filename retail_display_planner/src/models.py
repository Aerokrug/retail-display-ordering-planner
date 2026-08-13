"""Data classes for displays, fixtures, and orders."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Variety:
    """One flavor/SKU within a product line being planned."""

    name: str
    upc: Optional[str] = None
    prior_year_units: float = 0.0
    case_pack: int = 1
    unit_width_in: Optional[float] = None
    unit_depth_in: Optional[float] = None
    unit_height_in: Optional[float] = None
    min_facings: int = 1
    stockout_last_year: bool = False

    discount_pct: float = 0.0
    elasticity_coefficient: float = -1.5  # gets replaced with a fitted value once
                                           # we have enough logged results (see learning.py)

    # only used for side-stack displays (stacking whole cases instead of units)
    case_width_in: Optional[float] = None
    case_depth_in: Optional[float] = None
    case_height_in: Optional[float] = None

    def footprint_sq_in(self) -> Optional[float]:
        if self.unit_width_in and self.unit_depth_in:
            return self.unit_width_in * self.unit_depth_in
        return None


@dataclass
class Shelf:
    width_in: float
    depth_in: float
    max_stack_height_in: Optional[float] = None
    # override the eye-level guess in layout.py if you actually know how a shelf performs
    visibility_weight: Optional[float] = None


@dataclass
class Crate:
    """Bulk bin display - produce bins, bulk candy, that kind of thing."""

    width_in: float
    depth_in: float
    fill_height_in: float
    packing_efficiency: float = 0.7  # dumped product doesn't pack tight, ~30% is air


@dataclass
class SideStack:
    """Freestanding stack of whole cases - pallet display, case pyramid, etc."""

    base_width_in: float
    base_depth_in: float
    max_height_in: float


@dataclass
class DisplayConfig:
    fixture_type: str = "shelf"  # shelf | crate | side_stack
    shelves: list[Shelf] = field(default_factory=list)
    crates: list[Crate] = field(default_factory=list)
    side_stacks: list[SideStack] = field(default_factory=list)
    duration_days_this_year: int = 14
    duration_days_prior_year: int = 14
    growth_target_pct: float = 0.0
    tie_in: bool = False
    tie_in_bonus_pct: float = 0.0
    context_notes: str = ""  # just for humans, not used anywhere in the math

    @property
    def num_shelves(self) -> int:
        return len(self.shelves)


@dataclass
class VarietyOrder:
    """How much of one variety to order, and where it ends up on the display."""

    variety: Variety
    forecast_units: float
    order_units: int
    order_cases: int
    facings: int = 0
    display_units: int = 0
    backroom_units: int = 0
    shelf_breakdown: dict = field(default_factory=dict)
    crate_assignment: dict = field(default_factory=dict)
    stack_assignment: dict = field(default_factory=dict)


@dataclass
class ResultRecord:
    """Forecast vs actual for one variety after a display ran."""

    display_id: str
    variety_name: str
    run_date: str
    forecast_units: float
    actual_units: float
    discount_pct: float = 0.0
    elasticity_coefficient: float = -1.5
    growth_target_pct: float = 0.0
    tie_in: bool = False
    notes: str = ""
