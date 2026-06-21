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
    
    def __init__(self, solar_kw=0, grid_kw=0, dg_ratings_kva=None, mccb_db=None, bess_kw=0):
        """
        Initialize system with source specifications.
        
        Args:
            solar_kw: Solar PV capacity (kW)
            grid_kw: Grid supply capacity (kW)
            dg_ratings_kva: List of DG capacities (kVA)
            mccb_db: Dictionary of MCCB dimensions from Excel
            bess_kw: BESS capacity (kW)
        """
        self.solar_kw = solar_kw
        self.grid_kw = grid_kw
        self.bess_kw = bess_kw
        self.dg_ratings_kva = dg_ratings_kva or []
        self.mccb_db = mccb_db
        
        # Calculate currents
        self.i_solar = self._calculate_solar_current()
        self.i_grid = self._calculate_grid_current()
        self.i_bess = self._calculate_bess_current()
        self.dg_currents, self.dg_mccbs = self._calculate_dg_currents()
        
        # Calculate MCCB ratings
        self.mccb_solar = self._get_mccb_solar()
        self.mccb_grid = self._get_mccb_grid()
        self.mccb_bess = self._get_mccb_bess()
        
        # Total busbar current
        self.total_busbar_current = self.i_solar + self.i_grid + self.i_bess + sum(self.dg_currents)
    
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
            mccbs.append(get_mccb_rating(i, self.mccb_db))
        return currents, mccbs
    
    def _get_mccb_solar(self):
        """Get solar MCCB rating or 0 if no solar."""
        if self.solar_kw > 0:
            return get_mccb_rating(self.i_solar, self.mccb_db)
        return 0
    
    def _get_mccb_grid(self):
        """Get grid MCCB rating or 0 if no grid."""
        if self.grid_kw > 0:
            return get_mccb_rating(self.i_grid, self.mccb_db)
        return 0
    
    def _calculate_bess_current(self):
        """Calculate BESS incomer current."""
        return calculate_current_from_power(self.bess_kw, NOMINAL_VOLTAGE, POWER_FACTOR)

    def _get_mccb_bess(self):
        """Get BESS MCCB rating or 0 if no BESS."""
        if self.bess_kw > 0:
            return get_mccb_rating(self.i_bess, self.mccb_db)
        return 0

    def get_all_incomers(self):
        """Get list of all incomer MCCB ratings (DG, Grid, Solar, BESS)."""
        incomers = []
        incomers.extend(self.dg_mccbs)
        if self.grid_kw > 0:
            incomers.append(self.mccb_grid)
        if self.solar_kw > 0:
            incomers.append(self.mccb_solar)
        if self.bess_kw > 0:
            incomers.append(self.mccb_bess)
        return incomers
