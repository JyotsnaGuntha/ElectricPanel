"""
BOM Generator
Core BOM data generation and item management.
"""

from collections import Counter


class BOMItem:
    """Represents a single BOM line item."""
    
    def __init__(self, description, rating, qty, uom):
        """
        Initialize BOM item.
        
        Args:
            description: Item description
            rating: Rating or specification
            qty: Quantity
            uom: Unit of measure (Nos, Set, Meters, etc.)
        """
        self.description = description
        self.rating = rating
        self.qty = qty
        self.uom = uom
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "Description": self.description,
            "Rating": self.rating,
            "Qty": self.qty,
            "UOM": self.uom,
        }


def generate_bom_items(
    solar_kw,
    grid_kw,
    num_dg,
    dg_mccbs,
    mccb_solar,
    mccb_grid,
    mccb_outputs,
    num_poles,
    busbar_spec,
    total_busbar_current,
    busbar_material,
    panel_h,
    panel_w,
    panel_d,
):
    """
    Generate complete BOM item list.
    
    Args:
        solar_kw: Solar capacity (kW)
        grid_kw: Grid capacity (kW)
        num_dg: Number of DGs
        dg_mccbs: List of DG MCCB ratings
        mccb_solar: Solar MCCB rating
        mccb_grid: Grid MCCB rating
        mccb_outputs: List of outgoing MCCB ratings
        num_poles: 3 or 4
        busbar_spec: Busbar specification string
        total_busbar_current: Total busbar current (A)
        busbar_material: "Copper" or "Aluminium"
        panel_h: Panel height (mm)
        panel_w: Panel width (mm)
        panel_d: Panel depth (mm)
    
    Returns:
        list of BOMItem objects
    """
    items = []
    
    # Solar incomer
    if solar_kw > 0:
        items.append(BOMItem(
            f"Solar Incomer MCCB {mccb_solar}A, {num_poles}P, 36kA",
            "36kA",
            1,
            "Nos"
        ))
    
    # Grid incomer
    if grid_kw > 0:
        items.append(BOMItem(
            f"Grid Incomer MCCB {mccb_grid}A, {num_poles}P, 36kA",
            "36kA",
            1,
            "Nos"
        ))
    
    # DG incomers (grouped by rating)
    if num_dg > 0:
        for r, count in Counter(dg_mccbs).items():
            items.append(BOMItem(
                f"DG Incomer MCCB {r}A, {num_poles}P, 36kA",
                "36kA",
                count,
                "Nos"
            ))
    
    # Outgoing feeders (grouped by rating)
    if mccb_outputs:
        for r, count in Counter(mccb_outputs).items():
            items.append(BOMItem(
                f"Outgoing Feeder MCCB {int(r)}A, {num_poles}P, 36kA",
                "36kA",
                count,
                "Nos"
            ))
    
    # Busbar
    busbar_details = busbar_spec.split('(')[1].replace(')', '') if '(' in busbar_spec else busbar_spec
    items.append(BOMItem(
        f"{busbar_material} Main Busbar ({busbar_details})",
        f"{total_busbar_current:.1f}A",
        1,
        "Set"
    ))
    
    # Microgrid Controller
    items.append(BOMItem(
        "Microgrid Controller (MGC)",
        "Standard",
        1,
        "Nos"
    ))
    
    # Control Cable
    items.append(BOMItem(
        "Control Cable 1.5 sqmm",
        "-",
        100,
        "Meters"
    ))
    
    # Power Cable
    items.append(BOMItem(
        "Power/Consumable Cable Varied",
        "-",
        50,
        "Meters"
    ))
    
    # Control Panel
    items.append(BOMItem(
        f"Control Panel, {panel_h}H x {panel_w} W x {panel_d} D mm with stand",
        "-",
        1,
        "Set"
    ))
    
    return items


def get_bom_dicts(bom_items):
    """
    Convert BOMItem list to list of dictionaries.
    
    Args:
        bom_items: List of BOMItem objects
    
    Returns:
        List of dictionaries with Sr No
    """
    dicts = []
    for i, item in enumerate(bom_items, 1):
        d = item.to_dict()
        d["Sr No"] = i
        dicts.append(d)
    return dicts
