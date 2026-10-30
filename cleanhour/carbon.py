"""Turn a generation mix into grid carbon intensity (gCO2 per kWh).

Only direct combustion emissions are counted. Factors are deliberately simple
and documented in docs/METHODOLOGY.md so anyone can swap them.
"""

# tCO2/MWh == kgCO2/kWh. Multiply by 1000 for g/kWh.
EMISSION_FACTORS = {
    # Grid-India's THERMAL column is coal + lignite. CEA CO2 Baseline Database
    # v16 puts India's operating margin (fossil fleet, FY2019-20) at 0.96.
    "thermal": 0.96,
    # Open-cycle/combined-cycle gas; IPCC default range for CCGT is ~0.40-0.49.
    "gas": 0.45,
    "nuclear": 0.0,
    "wind": 0.0,
    "solar": 0.0,
    "hydro": 0.0,
    # Discharged storage was charged from the grid earlier; counting it again
    # would double count, so it carries zero direct emissions here.
    "storage": 0.0,
    # "Others" in the PSP report is mostly small hydro, biomass and captive
    # injections. Treated as zero-direct (biomass is conventionally neutral).
    "others": 0.0,
}

FUELS = list(EMISSION_FACTORS)
CLEAN_FUELS = ["nuclear", "wind", "solar", "hydro"]


def intensity_g_per_kwh(mix: dict, factors: dict = EMISSION_FACTORS) -> float:
    """Generation-weighted carbon intensity for one interval of MW values."""
    total = sum(max(mix.get(f, 0.0), 0.0) for f in factors)
    if total <= 0:
        raise ValueError("generation mix sums to zero")
    tonnes_per_mwh = sum(max(mix.get(f, 0.0), 0.0) * ef for f, ef in factors.items()) / total
    return tonnes_per_mwh * 1000.0


def clean_share(mix: dict) -> float:
    """Fraction of generation from zero-carbon sources (excludes storage/others)."""
    total = sum(max(mix.get(f, 0.0), 0.0) for f in FUELS)
    return sum(max(mix.get(f, 0.0), 0.0) for f in CLEAN_FUELS) / total
