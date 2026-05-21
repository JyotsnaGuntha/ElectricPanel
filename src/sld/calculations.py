"""
SLD Calculations
Electrical calculations for SLD generation.
"""

import math
from ..constants import NOMINAL_VOLTAGE, POWER_FACTOR, DG_POWER_FACTOR
from ..utils import (
    calculate_current_from_power,
    calculate_current_from_kva,
    get_mccb_rating,
)


class SystemCalculations:
    """
    Encapsulates all electrical calculations for SLD generation.
    """
    
    def __init__(self, solar_kw=0, grid_kw=0, dg_ratings_kva=None):
        """
        Initialize system with source specifications.
        
        Args:
            solar_kw: Solar PV capacity (kW)
            grid_kw: Grid supply capacity (kW)
            dg_ratings_kva: List of DG capacities (kVA)
        """
        self.solar_kw = solar_kw
        self.grid_kw = grid_kw
        self.dg_ratings_kva = dg_ratings_kva or []
        
        # Calculate currents
        self.i_solar = self._calculate_solar_current()
        self.i_grid = self._calculate_grid_current()
        self.dg_currents, self.dg_mccbs = self._calculate_dg_currents()
        
        # Calculate MCCB ratings
        self.mccb_solar = self._get_mccb_solar()
        self.mccb_grid = self._get_mccb_grid()
        
        # Total busbar current (using engineering method: I_base * 1.1 * 1.2)
        self.total_busbar_current = self.calculate_final_busbar_current()
    
    def _calculate_solar_current(self):
        """Calculate solar incomer current."""
        return calculate_current_from_power(self.solar_kw, NOMINAL_VOLTAGE, POWER_FACTOR)
    
    def _calculate_grid_current(self):
        """Calculate grid incomer current."""
        return calculate_current_from_power(self.grid_kw, NOMINAL_VOLTAGE, POWER_FACTOR)
    
    def _calculate_dg_currents(self):
        """Calculate DG incomer currents and MCCB ratings."""
        currents = []
        mccbs = []
        for dg_kva in self.dg_ratings_kva:
            i = calculate_current_from_kva(dg_kva, NOMINAL_VOLTAGE, is_dg=True)
            currents.append(i)
            mccbs.append(get_mccb_rating(i))
        return currents, mccbs
    
    def _get_mccb_solar(self):
        """Get solar MCCB rating or 0 if no solar."""
        if self.solar_kw > 0:
            return get_mccb_rating(self.i_solar)
        return 0
    
    def _get_mccb_grid(self):
        """Get grid MCCB rating or 0 if no grid."""
        if self.grid_kw > 0:
            return get_mccb_rating(self.i_grid)
        return 0
    
    def get_all_incomers(self):
        """Get list of all incomer MCCB ratings (DG, Grid, Solar)."""
        incomers = []
        incomers.extend(self.dg_mccbs)
        if self.grid_kw > 0:
            incomers.append(self.mccb_grid)
        if self.solar_kw > 0:
            incomers.append(self.mccb_solar)
        return incomers
    
    # ========================================================================
    # BUSBAR DIMENSION CALCULATIONS (Engineering Specification)
    # ========================================================================
    
    def calculate_base_busbar_current(self):
        """
        Step 1: Calculate Total Busbar Current Rating
        
        Divides incoming sources into two distinct parts:
        - Part A: Sum of all Diesel Generator (DG) calculated currents
        - Part B: Sum of Solar calculated current + Grid calculated current
        
        Determine the Base Current (I_base) by taking the maximum value:
        I_base = Max(Part A, Part B)
        
        Returns:
            I_base (A): Maximum value between Part A and Part B
        """
        # Part A: Sum of all DG calculated currents
        part_a = sum(self.dg_mccbs)
        
        # Part B: Sum of Solar + Grid calculated currents
        part_b = self.i_solar + self.i_grid
        
        # Base current is the maximum of the two
        i_base = max(part_a, part_b)
        return i_base
    
    def calculate_final_busbar_current(self, overload=1.1):
        """
        Calculate Final Total Busbar Current with safety and diversity factors.
        
        i_total = i_base * overload
        
        Args:
            safety_factor: Safety factor (default 1.1)
            diversity_factor: Diversity factor (default 1.2)
        
        Returns:
            I_total (A): Final total busbar current rating
        """
        i_base = self.calculate_base_busbar_current()
        i_total = i_base * overload
        return i_total
    
    def determine_busbar_thickness(self, i_total):
        """
        Step 2: Determine Busbar Thickness
        
        Based on calculated I_total, select thickness using standard lookup table:
        - 80A ≤ I_total ≤ 125A  → Thickness = 3 mm
        - 150A ≤ I_total ≤ 450A → Thickness = 5 mm
        - 450A < I_total ≤ 1000A → Thickness = 8 mm
        - 1000A < I_total ≤ 1500A → Thickness = 10 mm
        - I_total > 1500A → Thickness = 12 mm
        
        For currents in gap ranges (125A-150A), next higher standard is used.
        
        Args:
            i_total: Final total busbar current (A)
        
        Returns:
            thickness (mm): Recommended busbar thickness
        """
        if i_total <= 125:
            return 3
        elif i_total <= 450:
            # Covers gap from 125-150 and the 150-450 range
            return 5
        elif i_total <= 1000:
            return 8
        elif i_total <= 1500:
            return 10
        else:
            return 12
    
    def get_current_density(self, material="Copper"):
        """
        Step 3: Determine Current Density
        
        Based on material:
        - Copper (Cu): J = 1.6 A/mm²
        - Aluminum (Al): J = 1.2 A/mm²
        
        Args:
            material: Material type ("Copper" or "Aluminum")
        
        Returns:
            J (A/mm²): Current density for the material
        """
        material_lower = material.lower()
        if "alum" in material_lower:
            return 1.2
        else:  # Default to Copper
            return 1.6
    
    def calculate_cross_sectional_area(self, i_total, material="Copper"):
        """
        Step 4: Calculate Required Cross-Sectional Area
        
        Area (A) = I_total / Current Density (J)
        
        Args:
            i_total: Final total busbar current (A)
            material: Material type ("Copper" or "Aluminum")
        
        Returns:
            area (mm²): Required cross-sectional area
        """
        j = self.get_current_density(material)
        area = i_total / j
        return area
    
    def calculate_busbar_dimensions(self, material="Copper"):
        """
        Step 5: Calculate Busbar Dimensions (Thickness and Height)
        
        Using the Area (A) from Step 4 and Thickness (t) from Step 2:
        Height (h) = Area (A) / Thickness (t)
        
        Args:
            material: Material type ("Copper" or "Aluminum")
        
        Returns:
            dict: Dictionary containing:
                - i_base: Base current (A)
                - i_total: Final total busbar current (A)
                - thickness: Busbar thickness (mm)
                - current_density: Current density (A/mm²)
                - cross_sectional_area: Required cross-sectional area (mm²)
                - height: Calculated busbar height (mm)
                - material: Material type
        """
        # Step 1: Calculate base current
        i_base = self.calculate_base_busbar_current()
        
        # Step 1-2: Calculate final total busbar current
        i_total = self.calculate_final_busbar_current()
        
        # Step 2: Determine thickness
        thickness = self.determine_busbar_thickness(i_total)
        
        # Step 3: Get current density
        current_density = self.get_current_density(material)
        
        # Step 4: Calculate cross-sectional area
        cross_sectional_area = self.calculate_cross_sectional_area(i_total, material)
        
        # Step 5: Calculate height
        height = cross_sectional_area / thickness
        
        return {
            "i_base": i_base,
            "i_total": i_total,
            "thickness": thickness,
            "current_density": current_density,
            "cross_sectional_area": cross_sectional_area,
            "height": height,
            "material": material
        }
