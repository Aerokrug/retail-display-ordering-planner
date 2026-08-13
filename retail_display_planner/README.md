# Retail Display Planner

Forecasts how much product to order for a retail display, splits the
order across varieties based on sales history, and lays out a mockup
of the display (shelf, crate, or side-stack).

Started as a way to combine learning Python with something actually
useful for planning displays at work. Grew from a plain forecasting
script into something with SQLite storage, an LP-based shelf optimizer,
and a basic feedback loop that learns from past runs.

## What it does

- **Forecast**: projects units needed from last year's sales, adjusted
  for how long the display's up, growth target, tie-in promos, and
  discount lift (via price elasticity).
- **Allocate**: rounds up to case-pack multiples, makes sure slow
  movers still get a minimum presence instead of getting zeroed out.
- **Layout**: figures out how the order actually fits on the display.
  Shelves get eye-level-priority facing placement with an LP optimizer
  behind it (`src/optimizer.py`). Crates and side-stacks use a simpler
  greedy allocation since there's not much to optimize with a handful
  of fixtures.
- **Mockup**: renders the layout as a PNG so you can actually look at
  it before ordering anything.
- **Learning**: log what actually happened after a display runs, and
  future forecasts get corrected based on that (bias correction +
  fitted elasticity, nothing fancy, just averages and a small
  regression).
- **Storage**: SQLite (`data/planner.db`). CSVs are still how you edit
  input data, they just get synced into the DB on each run.
- **Validation**: catches obviously bad input (negative units, a
  discount of `20` instead of `0.20`, zero case packs) before it
  quietly turns into a wrong order.

## Setup

```bash
pip install matplotlib pulp pytest --break-system-packages
```

SQLite doesn't need installing, it's stdlib.

```bash
python -m src.main                                # default display
python -m src.main --display-id produce_crate_2025  # a crate display
python -m src.main --list                             # see what's available
```

Sample data has one display per fixture type - `pudding_endcap_2025`
(shelf), `produce_crate_2025` (crate), `soda_stack_2025` (side stack).

Run tests with `pytest -v` from the project root.

## Editing your own data

Two CSVs, both keyed by `display_id`:

**`data/sales_history.csv`** - one row per variety. Columns:
`display_id, name, upc, prior_year_units, case_pack, unit_width_in,
unit_depth_in, unit_height_in, min_facings, stockout_last_year,
discount_pct, elasticity_coefficient, case_width_in, case_depth_in,
case_height_in`. Only the first few are required, rest have sane
defaults. Case dimensions only matter if you're doing a side-stack
display.

**`data/displays.csv`** - one row per display. Columns: `display_id,
fixture_type, duration_days_this_year, duration_days_prior_year,
growth_target_pct, tie_in, tie_in_bonus_pct, context_notes`.
`fixture_type` is `shelf` / `crate` / `side_stack`, defaults to shelf.
`duration_days_this_year` is the only required field - it directly
scales the forecast.

Fixture physical dimensions (how many shelves, crate size, etc) are
still hardcoded in `main.py`'s `_setup_fixtures()`. Might move that to
a CSV eventually, hasn't felt worth it yet.

## Project layout

```
src/
  models.py           dataclasses: Variety, Shelf, Crate, SideStack, DisplayConfig, VarietyOrder, ResultRecord
  forecasting.py       prior year sales -> this year's forecast
  allocation.py         forecast -> case-rounded order
  layout.py             shelf facing placement (eye-level priority)
  crate_layout.py        crate/bulk-bin allocation
  stack_layout.py         side-stack (case) allocation
  optimizer.py            LP facing optimizer, shelf displays only
  mockup.py                renders the layout as an image
  db.py                     SQLite storage
  learning.py                bias correction + elasticity fitting from logged results
  validation.py                input sanity checks
  io_utils.py                   CSV loading
  main.py                        CLI entry point
tests/                           one test file per module above
data/                            sample CSVs + generated db/images
```

## Known limitations / things I'd fix next

- No shopping-list export yet - would be nice to spit out a plain
  `variety, cases` CSV you could hand to a supplier.
- The eye-level shelf weighting (`shelf_visibility_weight` in
  `layout.py`) is just a merchandising rule of thumb, not real data.
  Same with the diminishing-returns curve the LP optimizer uses -
  total guess at the shape. Both would be worth fitting from real
  numbers once there's enough logged history.
- Forecasting only looks at one prior year. Blending 2-3 years with
  recency weighting would probably be more stable.
- No uncertainty range on the forecast - it's a single point estimate
  even though there are several stacked assumptions (growth target,
  elasticity, bias correction) behind it. A conservative/expected/
  aggressive range would be more honest.
- Real ML forecasting isn't worth it yet - not enough logged displays
  to train anything on. The bias correction + elasticity fitting
  that's there now (plain averages + a small regression) is doing
  fine for the amount of data available.
