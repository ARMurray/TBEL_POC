"""
Combined Wastestream Formula (CWF) engine -- 40 CFR 403.6(e).

Pure Python, no third-party dependencies, so the regulatory logic can be unit
tested and reused independently of the Shiny UI. All of the compliance-relevant
math lives here on purpose: the UI is disposable, this file is the part that has
to be right.

Regulatory references:
  40 CFR 403.6(c)      production-based -> mass / concentration conversion
  40 CFR 403.6(d)      dilution prohibited as a substitute for treatment
  40 CFR 403.6(e)(1)(i)  alternative concentration limit
  40 CFR 403.6(e)(1)(ii) alternative mass limit
  40 CFR 403.6(e)(2)   alternative limit may not be used below detection

Run `python cwf.py` to execute the self-test at the bottom.
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Level-of-control resolution (direct/indirect x new/existing)
# ---------------------------------------------------------------------------

def resolve_levels_of_control(discharge_type: str, source_status: str) -> list:
    """Map discharger characteristics to the applicable technology standard(s).

    discharge_type: 'direct' or 'indirect'
    source_status : 'existing' or 'new'

    Mirrors Table A-2 of the ELG database.
    """
    dt = discharge_type.lower().strip()
    ss = source_status.lower().strip()
    if dt == "direct":
        return ["BPT", "BCT", "BAT"] if ss == "existing" else ["NSPS"]
    if dt == "indirect":
        return ["PSES"] if ss == "existing" else ["PSNS"]
    raise ValueError("discharge_type must be 'direct' or 'indirect'")


# ---------------------------------------------------------------------------
# Stream / input model
# ---------------------------------------------------------------------------

@dataclass
class RegulatedStream:
    """One regulated process wastestream carrying one regulated pollutant.

    POC simplification: one pollutant per row. A single physical stream that
    carries several regulated pollutants would, in the production tool, be
    defined once (label + flow) with multiple pollutant limits attached. Here
    you enter one row per (stream, pollutant); flows are de-duplicated by
    ``label`` when totalling F_T so a multi-row stream is not double counted.
    """
    label: str
    pollutant: str
    flow_mgd: float          # F_i  -- avg daily flow (>= 30-day average)
    c_daily: float           # categorical daily-maximum concentration limit
    c_monthly: float         # categorical monthly-average concentration limit
    units: str = "mg/L"


@dataclass
class CWFInputs:
    regulated: list = field(default_factory=list)   # list[RegulatedStream]
    unregulated_flow_mgd: float = 0.0   # process water, no categorical standard
    dilute_flow_mgd: float = 0.0        # F_D: cooling, blowdown, stormwater, ...


@dataclass
class CWFResult:
    pollutant: str
    units: str
    alt_daily_max: float
    alt_monthly_avg: float
    f_total: float           # F_T
    f_dilute: float          # F_D
    f_nondilute: float       # F_T - F_D
    below_detection: bool
    detection_limit: Optional[float]


# ---------------------------------------------------------------------------
# Core formulas
# ---------------------------------------------------------------------------

def total_flow(inp: CWFInputs) -> float:
    """F_T = regulated flows + unregulated flow + dilute flow.

    Each physical regulated stream is counted once (keyed by label) so entering
    a multi-pollutant stream on several rows does not inflate F_T.
    """
    seen = {}
    for s in inp.regulated:
        seen.setdefault(s.label, s.flow_mgd)
    return sum(seen.values()) + inp.unregulated_flow_mgd + inp.dilute_flow_mgd


def alternative_concentration_limits(inp: CWFInputs, detection_limits: dict = None):
    """Alternative concentration limits per pollutant -- 40 CFR 403.6(e)(1)(i):

        C_T = sum_i (C_i * F_i) / (F_T - F_D)

    Returns one CWFResult per distinct regulated pollutant. Both the daily-max
    and monthly-average alternative limits are computed, as 403.6(e) requires.
    """
    detection_limits = detection_limits or {}
    f_t = total_flow(inp)
    f_d = inp.dilute_flow_mgd
    denom = f_t - f_d                       # non-dilute flow
    if denom <= 0:
        raise ValueError("F_T - F_D must be > 0: there must be non-dilute flow.")

    agg = {}
    for s in inp.regulated:
        a = agg.setdefault(s.pollutant, {"units": s.units, "num_d": 0.0, "num_m": 0.0})
        a["num_d"] += s.c_daily * s.flow_mgd
        a["num_m"] += s.c_monthly * s.flow_mgd

    results = []
    for pol, a in agg.items():
        ct_daily = a["num_d"] / denom
        ct_monthly = a["num_m"] / denom
        dl = detection_limits.get(pol)
        # 403.6(e)(2): alt limit may not be used if below detection for a pollutant
        below = dl is not None and (ct_daily < dl or ct_monthly < dl)
        results.append(CWFResult(
            pollutant=pol, units=a["units"],
            alt_daily_max=ct_daily, alt_monthly_avg=ct_monthly,
            f_total=f_t, f_dilute=f_d, f_nondilute=denom,
            below_detection=below, detection_limit=dl,
        ))
    return results


def alternative_mass_limits(mass_by_pollutant: dict, f_total: float, f_dilute: float) -> dict:
    """Alternative mass limits -- 40 CFR 403.6(e)(1)(ii):

        M_T = sum_i (M_i) * (F_T - F_D) / F_T

    mass_by_pollutant: {pollutant: [M_i, ...]} where each M_i is a categorical
    mass limit (categorical mass standard * production measure) for a regulated
    stream. Returned per pollutant. Not wired into the POC UI yet; provided so
    the mass-based path is available and correct.
    """
    if f_total <= 0:
        raise ValueError("F_T must be > 0.")
    factor = (f_total - f_dilute) / f_total
    return {pol: sum(mis) * factor for pol, mis in mass_by_pollutant.items()}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Worked example: zinc, two regulated streams + unregulated + cooling water.
    inp = CWFInputs(
        regulated=[
            RegulatedStream("Electroplating line", "Zinc", 0.10, 2.0, 1.0),
            RegulatedStream("Process line 2",      "Zinc", 0.05, 1.0, 0.5),
        ],
        unregulated_flow_mgd=0.05,
        dilute_flow_mgd=0.30,
    )
    (r,) = alternative_concentration_limits(inp, detection_limits={"Zinc": 0.05})
    assert abs(r.f_total - 0.50) < 1e-9, r.f_total
    assert abs(r.f_nondilute - 0.20) < 1e-9, r.f_nondilute
    assert abs(r.alt_daily_max - 1.25) < 1e-9, r.alt_daily_max        # 0.25 / 0.20
    assert abs(r.alt_monthly_avg - 0.625) < 1e-9, r.alt_monthly_avg   # 0.125 / 0.20
    assert r.below_detection is False

    # Anti-dilution: adding dilute flow must NOT change the limit.
    inp.dilute_flow_mgd += 0.20
    (r2,) = alternative_concentration_limits(inp, detection_limits={"Zinc": 0.05})
    assert abs(r2.alt_daily_max - 1.25) < 1e-9, r2.alt_daily_max

    # Detection-limit guard trips when the alt limit is tiny.
    (r3,) = alternative_concentration_limits(inp, detection_limits={"Zinc": 2.0})
    assert r3.below_detection is True

    print("cwf.py self-test passed.")
    print(f"  C_T daily max   = {r.alt_daily_max:.3f} mg/L")
    print(f"  C_T monthly avg = {r.alt_monthly_avg:.3f} mg/L")
    print(f"  dilution-invariant daily max after +0.20 MGD cooling = {r2.alt_daily_max:.3f} mg/L")
