"""
Mock ELG data layer.

Shaped to mirror the EPA Effluent Guidelines (ELG) database hierarchy:

    Point Source Category (40 CFR Part)
      -> subpart / subcategory
      -> limits by level of control (BPT/BCT/BAT/NSPS/PSES/PSNS)
           -> pollutant -> {daily_max, monthly_avg, units, basis, detection_limit}
      -> provenance (CFR cite, eCFR URL, FRN)

*** THE NUMERIC LIMITS BELOW ARE ILLUSTRATIVE PLACEHOLDERS, NOT AUTHORITATIVE. ***

Replace this module with your colleague's real ELG database copy, or wire it to
the ELG API at https://owapps.epa.gov/elg/api/ . Keep the four accessor
functions (get_categories / get_subparts / get_limits / get_provenance /
get_detection_limits) and the Shiny app will not need to change.
"""

_ELG = {
    "433": {
        "part": "40 CFR 433",
        "title": "Metal Finishing",
        "ecfr_url": "https://www.ecfr.gov/current/title-40/part-433",
        "frn": "48 FR 32485 (Jul 15, 1983) [illustrative citation]",
        "subparts": {"A": "Subpart A -- Metal finishing (illustrative)"},
        "limits": {
            # daily_max / monthly_avg in mg/L. Placeholder values -- verify.
            "PSES": {
                "Cyanide": dict(daily_max=1.20, monthly_avg=0.65, units="mg/L",
                                basis="concentration", detection_limit=0.02),
                "Copper":  dict(daily_max=3.38, monthly_avg=2.07, units="mg/L",
                                basis="concentration", detection_limit=0.02),
                "Nickel":  dict(daily_max=3.98, monthly_avg=2.38, units="mg/L",
                                basis="concentration", detection_limit=0.05),
                "Zinc":    dict(daily_max=2.61, monthly_avg=1.48, units="mg/L",
                                basis="concentration", detection_limit=0.05),
            },
            "PSNS": {
                "Cyanide": dict(daily_max=1.20, monthly_avg=0.65, units="mg/L",
                                basis="concentration", detection_limit=0.02),
                "Copper":  dict(daily_max=3.38, monthly_avg=2.07, units="mg/L",
                                basis="concentration", detection_limit=0.02),
                "Nickel":  dict(daily_max=3.98, monthly_avg=2.38, units="mg/L",
                                basis="concentration", detection_limit=0.05),
                "Zinc":    dict(daily_max=2.61, monthly_avg=1.48, units="mg/L",
                                basis="concentration", detection_limit=0.05),
            },
        },
    },
    "413": {
        "part": "40 CFR 413",
        "title": "Electroplating",
        "ecfr_url": "https://www.ecfr.gov/current/title-40/part-413",
        "frn": "46 FR 9467 (Jan 28, 1981) [illustrative citation]",
        "subparts": {"A": "Subpart A -- Copper, nickel, chromium & zinc (illustrative)"},
        "limits": {
            "PSES": {
                "Copper":  dict(daily_max=4.5, monthly_avg=2.7, units="mg/L",
                                basis="concentration", detection_limit=0.02),
                "Zinc":    dict(daily_max=4.2, monthly_avg=2.6, units="mg/L",
                                basis="concentration", detection_limit=0.05),
                "Cyanide": dict(daily_max=1.9, monthly_avg=1.0, units="mg/L",
                                basis="concentration", detection_limit=0.02),
            },
            "PSNS": {
                "Copper":  dict(daily_max=4.5, monthly_avg=2.7, units="mg/L",
                                basis="concentration", detection_limit=0.02),
                "Zinc":    dict(daily_max=4.2, monthly_avg=2.6, units="mg/L",
                                basis="concentration", detection_limit=0.05),
                "Cyanide": dict(daily_max=1.9, monthly_avg=1.0, units="mg/L",
                                basis="concentration", detection_limit=0.02),
            },
        },
    },
}

DISCLAIMER = ("Illustrative placeholder data -- NOT an official edition of the CFR. "
              "The Code of Federal Regulations is the authoritative source. Replace "
              "elg_data.py with the real ELG database or the ELG API before any real use.")


def get_categories() -> list:
    """[(part_key, 'Label'), ...] for the category picker."""
    return [(k, f"{v['part']} -- {v['title']}") for k, v in _ELG.items()]


def get_subparts(part_key: str) -> dict:
    """{subpart_key: 'Label'} for the selected category."""
    return _ELG.get(part_key, {}).get("subparts", {})


def get_limits(part_key: str, level_of_control: str) -> dict:
    """{pollutant: {daily_max, monthly_avg, units, basis, detection_limit}}
    for a category + level of control, or {} if none in the mock data."""
    return _ELG.get(part_key, {}).get("limits", {}).get(level_of_control, {})


def get_detection_limits(part_key: str, level_of_control: str) -> dict:
    """{pollutant: detection_limit} for the CWF below-detection check."""
    lim = get_limits(part_key, level_of_control)
    return {p: d.get("detection_limit") for p, d in lim.items()}


def get_provenance(part_key: str) -> dict:
    v = _ELG.get(part_key, {})
    return {"part": v.get("part", ""), "ecfr_url": v.get("ecfr_url", ""),
            "frn": v.get("frn", "")}
