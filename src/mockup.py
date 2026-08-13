# call assign_layout / assign_crate_layout / assign_stack_layout first,
# then draw_mockup() picks the right one of these based on fixture_type

import matplotlib.patches as patches
import matplotlib.pyplot as plt

from src.models import Crate, DisplayConfig, Shelf, SideStack, VarietyOrder

_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]


def _make_color_picker():
    palette_index: dict[str, str] = {}

    def color_for(name: str) -> str:
        if name not in palette_index:
            palette_index[name] = _PALETTE[len(palette_index) % len(_PALETTE)]
        return palette_index[name]

    return color_for, palette_index


def _add_legend(ax, palette_index: dict[str, str]):
    handles = [
        patches.Patch(color=color, label=name) for name, color in palette_index.items()
    ]
    ax.legend(
        handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.05),
        ncol=min(len(handles), 4) or 1, fontsize=8, frameon=False,
    )


def draw_planogram(
    shelves: list[Shelf],
    orders: list[VarietyOrder],
    title: str = "Display Planogram",
    output_path: str = "planogram.png",
) -> str:
    if not shelves:
        raise ValueError("No shelves to draw")
    if any(not o.shelf_breakdown and o.facings > 0 for o in orders):
        raise ValueError(
            "orders are missing shelf_breakdown - call "
            "src.layout.assign_layout(shelves, orders) before drawing"
        )

    max_width = max(s.width_in for s in shelves)
    num_shelves = len(shelves)
    fig_height = max(3.0, 1.3 * num_shelves + 2.0)
    fig, ax = plt.subplots(figsize=(10, fig_height))

    color_for, palette_index = _make_color_picker()

    margin = 0.3  # frame around the whole thing
    ax.add_patch(
        patches.Rectangle(
            (-margin, -margin), max_width + 2 * margin, num_shelves + 2 * margin,
            linewidth=2, edgecolor="#333333", facecolor="#EDEDED", zorder=0,
        )
    )

    for shelf_idx, shelf in enumerate(shelves):
        y = num_shelves - 1 - shelf_idx  # shelf 0 drawn at the top

        ax.add_patch(
            patches.Rectangle(
                (0, y), shelf.width_in, 0.9,
                linewidth=1, edgecolor="#666666", facecolor="white", zorder=1,
            )
        )
        ax.text(-0.4, y + 0.45, f"Shelf {shelf_idx + 1}",
                 ha="right", va="center", fontsize=8)

        x_cursor = 0.0
        for order in orders:
            facings_here = order.shelf_breakdown.get(shelf_idx, 0)
            if facings_here <= 0:
                continue
            unit_width = order.variety.unit_width_in or 3.0
            block_width = facings_here * unit_width
            color = color_for(order.variety.name)

            ax.add_patch(
                patches.Rectangle(
                    (x_cursor, y), block_width, 0.9,
                    linewidth=1, edgecolor="white", facecolor=color, zorder=2,
                )
            )
            label = f"{order.variety.name}\n{facings_here}f"
            fontsize = 7 if block_width > 3 else 5.5
            if block_width > 1.2:
                ax.text(
                    x_cursor + block_width / 2, y + 0.45, label,
                    ha="center", va="center", fontsize=fontsize, color="white",
                    zorder=3,
                )
            x_cursor += block_width

    ax.set_xlim(-2.2, max_width + margin + 0.5)
    ax.set_ylim(-margin - 0.9, num_shelves + margin)
    ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    _add_legend(ax, palette_index)

    backroom_total = sum(o.backroom_units for o in orders)
    if backroom_total > 0:
        ax.text(
            0, -margin - 0.75,
            f"Note: {backroom_total} units won't fit initially - plan a mid-run restock.",
            fontsize=8, color="#B00020",
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def draw_crate_mockup(
    crates: list[Crate],
    orders: list[VarietyOrder],
    title: str = "Crate Display",
    output_path: str = "crate_mockup.png",
) -> str:
    if not crates:
        raise ValueError("No crates to draw")

    variety_by_crate: dict[int, str] = {}
    units_by_crate: dict[int, int] = {}
    for order in orders:
        for crate_idx, units in order.crate_assignment.items():
            variety_by_crate[crate_idx] = order.variety.name
            units_by_crate[crate_idx] = units

    color_for, palette_index = _make_color_picker()

    num_crates = len(crates)
    box_w, gap = 2.4, 0.4
    total_width = num_crates * box_w + (num_crates - 1) * gap
    fig, ax = plt.subplots(figsize=(max(6, total_width + 2), 4.5))

    x = 0.0
    for idx, crate in enumerate(crates):
        variety_name = variety_by_crate.get(idx)
        color = color_for(variety_name) if variety_name else "#D8D8D8"
        ax.add_patch(
            patches.Rectangle(
                (x, 0), box_w, 2.4,
                linewidth=1.5, edgecolor="#666666", facecolor=color, zorder=1,
            )
        )
        label = f"Crate {idx + 1}"
        if variety_name:
            label += f"\n{variety_name}\n{units_by_crate.get(idx, 0)} units"
        else:
            label += "\n(unassigned)"
        ax.text(
            x + box_w / 2, 1.2, label,
            ha="center", va="center", fontsize=8,
            color="white" if variety_name else "#666666", zorder=2,
        )
        x += box_w + gap

    ax.set_xlim(-0.3, total_width + 0.3)
    ax.set_ylim(-1.6, 2.8)
    ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    _add_legend(ax, palette_index)

    backroom_total = sum(o.backroom_units for o in orders)
    if backroom_total > 0:
        ax.text(
            0, -1.3,
            f"Note: {backroom_total} units won't fit initially - plan a mid-run restock.",
            fontsize=8, color="#B00020",
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def draw_stack_mockup(
    stacks: list[SideStack],
    orders: list[VarietyOrder],
    title: str = "Side Stack Display",
    output_path: str = "stack_mockup.png",
) -> str:
    if not stacks:
        raise ValueError("No stacks to draw")

    variety_by_stack: dict[int, str] = {}
    cases_by_stack: dict[int, int] = {}
    for order in orders:
        for stack_idx, cases in order.stack_assignment.items():
            variety_by_stack[stack_idx] = order.variety.name
            cases_by_stack[stack_idx] = cases

    color_for, palette_index = _make_color_picker()

    max_cases = max(cases_by_stack.values(), default=1) or 1
    num_stacks = len(stacks)
    box_w, gap = 2.0, 0.6
    total_width = num_stacks * box_w + (num_stacks - 1) * gap
    fig, ax = plt.subplots(figsize=(max(6, total_width + 2), 5.5))

    x = 0.0
    for idx, stack in enumerate(stacks):
        variety_name = variety_by_stack.get(idx)
        cases = cases_by_stack.get(idx, 0)
        color = color_for(variety_name) if variety_name else "#D8D8D8"
        height = 1.0 + 3.0 * (cases / max_cases) if cases else 0.6  # scale to fullest stack, floor so empty ones still show

        ax.add_patch(
            patches.Rectangle(
                (x, 0), box_w, height,
                linewidth=1.5, edgecolor="#666666", facecolor=color, zorder=1,
            )
        )
        label = f"Stack {idx + 1}"
        if variety_name:
            label += f"\n{variety_name}\n{cases} cases"
        else:
            label += "\n(unassigned)"
        ax.text(
            x + box_w / 2, height / 2, label,
            ha="center", va="center", fontsize=8,
            color="white" if variety_name else "#666666", zorder=2,
        )
        x += box_w + gap

    ax.set_xlim(-0.3, total_width + 0.3)
    ax.set_ylim(-1.4, 4.5)
    ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    _add_legend(ax, palette_index)

    backroom_total = sum(o.backroom_units for o in orders)
    if backroom_total > 0:
        ax.text(
            0, -1.1,
            f"Note: {backroom_total} units won't fit initially - plan a mid-run restock.",
            fontsize=8, color="#B00020",
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def draw_mockup(
    config: DisplayConfig,
    orders: list[VarietyOrder],
    title: str = "Display Planogram",
    output_path: str = "planogram.png",
) -> str:
    if config.fixture_type == "shelf":
        return draw_planogram(config.shelves, orders, title, output_path)
    elif config.fixture_type == "crate":
        return draw_crate_mockup(config.crates, orders, title, output_path)
    elif config.fixture_type == "side_stack":
        return draw_stack_mockup(config.side_stacks, orders, title, output_path)
    else:
        raise ValueError(f"Unknown fixture_type: {config.fixture_type!r}")
