"""
TBEL Assistant -- proof of concept (indirect dischargers + Combined Wastestream Formula).

Shiny for Python. The ui/server split maps 1:1 onto R Shiny, so it should feel
familiar. All regulatory math is in cwf.py; all data is in elg_data.py (mock).

Run locally:      shiny run --reload app.py
Export static:    shinylive export . site
"""

from shiny import App, ui, render, reactive
import cwf
import elg_data

CATS = dict(elg_data.get_categories())

CSS = """
.tbl { border-collapse: collapse; width: 100%; margin: .5rem 0; font-size: .95rem; }
.tbl th, .tbl td { border: 1px solid #d9d9d9; padding: 6px 10px; text-align: left; }
.tbl th { background: #f3f5f7; }
.cite { color: #555; font-size: .85rem; margin: .35rem 0; }
.warn { background: #fff4e5; border: 1px solid #f0c36d; border-radius: 6px;
        padding: .6rem .8rem; margin: .6rem 0; font-size: .9rem; }
.banner { background: #eef4fb; border: 1px solid #b9d3ef; border-radius: 6px;
          padding: .5rem .8rem; font-size: .82rem; color: #33475b; margin-bottom: .6rem; }
"""

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h5("Facility"),
        ui.input_select("psc", "Point source category (40 CFR Part)", CATS),
        ui.output_ui("subpart_ui"),
        ui.input_radio_buttons(
            "discharge", "Discharge type",
            {"indirect": "Indirect (to a POTW)", "direct": "Direct (to surface water)"},
        ),
        ui.input_radio_buttons(
            "status", "Source status",
            {"existing": "Existing source", "new": "New source"},
        ),
        ui.hr(),
        ui.output_ui("loc_badge"),
        width=330,
    ),
    ui.head_content(ui.tags.style(CSS)),
    ui.div(elg_data.DISCLAIMER, class_="banner"),
    ui.navset_card_tab(
        ui.nav_panel("Categorical limits", ui.output_ui("limits_card")),
        ui.nav_panel(
            "Combined Wastestream Formula",
            ui.markdown(
                "Use this when a regulated stream is **monitored after mixing** with other "
                "waters (40 CFR 403.6(e)). Enter each regulated stream's categorical limits "
                "and flow, then the total **unregulated** process flow and total **dilute** "
                "flow (cooling water, boiler blowdown, stormwater, demineralizer backwash, "
                "unregulated sanitary)."
            ),
            ui.input_numeric("n_streams", "Number of regulated streams", 2, min=1, max=6),
            ui.output_ui("streams_ui"),
            ui.layout_columns(
                ui.input_numeric("f_unreg", "Unregulated process flow (MGD)", 0.05, min=0, step=0.01),
                ui.input_numeric("f_dilute", "Dilute flow F_D (MGD)", 0.30, min=0, step=0.01),
                col_widths=(6, 6),
            ),
            ui.output_ui("cwf_results"),
        ),
        ui.nav_panel("About / provenance", ui.output_ui("provenance")),
    ),
    title="TBEL Assistant -- POC",
)


def server(input, output, session):

    @reactive.calc
    def levels():
        return cwf.resolve_levels_of_control(input.discharge(), input.status())

    @reactive.calc
    def selection():
        """(level_of_control, {pollutant: limitrow}) -- first level with data."""
        for lvl in levels():
            lim = elg_data.get_limits(input.psc(), lvl)
            if lim:
                return lvl, lim
        return (levels()[0] if levels() else None), {}

    @render.ui
    def subpart_ui():
        return ui.input_select("subpart", "Subcategory / subpart",
                               elg_data.get_subparts(input.psc()))

    @render.ui
    def loc_badge():
        return ui.TagList(
            ui.tags.strong("Applicable level(s) of control: "),
            ui.span(", ".join(levels())),
        )

    @render.ui
    def limits_card():
        lvl, lim = selection()
        if not lim:
            return ui.markdown(
                f"*No categorical limits in the mock data for level **{lvl}**. In the real "
                f"tool this is the point to flag a Best Professional Judgment determination.*"
            )
        prov = elg_data.get_provenance(input.psc())
        rows = "".join(
            f"<tr><td>{p}</td><td>{d['daily_max']}</td><td>{d['monthly_avg']}</td>"
            f"<td>{d['units']}</td><td>{d['basis']}</td></tr>"
            for p, d in lim.items()
        )
        table = (
            "<table class='tbl'><thead><tr><th>Pollutant</th><th>Daily max</th>"
            "<th>Monthly avg</th><th>Units</th><th>Basis</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
        cite = (
            f"<p class='cite'>Level of control: <b>{lvl}</b> &nbsp;&middot;&nbsp; {prov['part']} "
            f"&nbsp;&middot;&nbsp; <a href='{prov['ecfr_url']}' target='_blank'>eCFR</a> "
            f"&nbsp;&middot;&nbsp; {prov['frn']}</p>"
        )
        return ui.HTML(table + cite)

    @render.ui
    def streams_ui():
        _lvl, lim = selection()
        pol_choices = list(lim.keys()) or ["(pollutant)"]
        n = int(input.n_streams() or 1)
        blocks = []
        for i in range(n):
            pol_default = pol_choices[min(i, len(pol_choices) - 1)]
            flow_default = 0.10 if i == 0 else (0.05 if i == 1 else 0.0)
            blocks.append(ui.card(
                ui.layout_columns(
                    ui.input_text(f"s{i}_label", "Stream label", f"Stream {i + 1}"),
                    ui.input_select(f"s{i}_pol", "Regulated pollutant", pol_choices,
                                    selected=pol_default),
                    ui.input_numeric(f"s{i}_flow", "Flow F_i (MGD)", flow_default, min=0, step=0.01),
                    col_widths=(4, 4, 4),
                ),
                ui.layout_columns(
                    ui.input_numeric(f"s{i}_cd", "Categorical daily max", 2.0, min=0, step=0.01),
                    ui.input_numeric(f"s{i}_cm", "Categorical monthly avg", 1.0, min=0, step=0.01),
                    col_widths=(6, 6),
                ),
            ))
        return ui.TagList(*blocks)

    @reactive.calc
    def cwf_inputs():
        n = int(input.n_streams() or 1)
        streams = []
        for i in range(n):
            try:
                flow = float(input[f"s{i}_flow"]() or 0)
                cd = float(input[f"s{i}_cd"]() or 0)
                cm = float(input[f"s{i}_cm"]() or 0)
                pol = input[f"s{i}_pol"]()
                lab = input[f"s{i}_label"]() or f"Stream {i + 1}"
            except Exception:
                continue
            if flow > 0:
                streams.append(cwf.RegulatedStream(lab, pol, flow, cd, cm))
        return cwf.CWFInputs(
            regulated=streams,
            unregulated_flow_mgd=float(input.f_unreg() or 0),
            dilute_flow_mgd=float(input.f_dilute() or 0),
        )

    @render.ui
    def cwf_results():
        inp = cwf_inputs()
        if not inp.regulated:
            return ui.markdown("*Enter at least one regulated stream with a positive flow.*")
        lvl, _lim = selection()
        dls = elg_data.get_detection_limits(input.psc(), lvl) if lvl else {}
        try:
            results = cwf.alternative_concentration_limits(inp, detection_limits=dls)
        except ValueError as e:
            return ui.div(ui.strong("Cannot compute: "), str(e), class_="warn")

        f_t, f_d, f_nd = results[0].f_total, results[0].f_dilute, results[0].f_nondilute
        head = (
            f"<p class='cite'>F_T (total) = <b>{f_t:.3f}</b> MGD &nbsp;&middot;&nbsp; "
            f"F_D (dilute) = <b>{f_d:.3f}</b> MGD &nbsp;&middot;&nbsp; "
            f"F_T &minus; F_D (non-dilute) = <b>{f_nd:.3f}</b> MGD</p>"
        )
        rows, warns = "", []
        for r in results:
            flag = " &#9888; below detection" if r.below_detection else ""
            rows += (
                f"<tr><td>{r.pollutant}</td><td>{r.alt_daily_max:.3f}</td>"
                f"<td>{r.alt_monthly_avg:.3f}</td><td>{r.units}</td><td>{flag}</td></tr>"
            )
            if r.below_detection:
                warns.append(
                    f"{r.pollutant}: alternative limit is below the analytical detection limit "
                    f"({r.detection_limit} {r.units}). Under 40 CFR 403.6(e)(2) the CWF "
                    f"alternative limit may not be used."
                )
        table = (
            "<table class='tbl'><thead><tr><th>Pollutant</th><th>Alt daily max (C_T)</th>"
            "<th>Alt monthly avg</th><th>Units</th><th></th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
        note = (
            "<p class='cite'>Dilute flow adds equally to F_T and F_D, so it cancels in "
            "F_T &minus; F_D: adding cooling / blowdown / stormwater does not change C_T. "
            "That is the CWF's anti-dilution safeguard (40 CFR 403.6(d)).</p>"
        )
        warn_html = ""
        if warns:
            warn_html = ("<div class='warn'><b>Detection-limit check:</b><ul>"
                         + "".join(f"<li>{w}</li>" for w in warns) + "</ul></div>")
        return ui.HTML(head + table + note + warn_html)

    @render.ui
    def provenance():
        prov = elg_data.get_provenance(input.psc())
        return ui.HTML(
            f"<p class='cite'><b>{prov['part']}</b><br>"
            f"eCFR (live text): <a href='{prov['ecfr_url']}' target='_blank'>{prov['ecfr_url']}</a><br>"
            f"Promulgating notice (FRN): {prov['frn']}</p>"
            f"<div class='warn'>{elg_data.DISCLAIMER}</div>"
        )


app = App(app_ui, server)
