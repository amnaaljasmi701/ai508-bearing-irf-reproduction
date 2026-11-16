"""Build the presentation in the themed slide template (report/template_src/slide_theme.pptx).

Every number comes from results/ (through irf_repro.report_values); the charts are redrawn from
results/*.csv in a dark style that matches the theme.  Minimum font size on the slides is 32 pt.
Output: report/AI508_A2_Presentation.pptx
"""
import _bootstrap  # noqa: F401
import copy
import os
import re

import pandas as pd

from irf_repro.config import REPO_ROOT, load_config
from irf_repro.paper_values import PAPER
from irf_repro.report_values import add_verdicts, build_values

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

THEME = os.path.join(REPO_ROOT, "report", "template_src", "slide_theme.pptx")
OUT = os.path.join(REPO_ROOT, "report", "AI508_A2_Presentation.pptx")
TITLE_FONT, BODY_FONT, BOLD_FONT = "Antonio Bold", "DM Sans", "DM Sans Bold"
YELLOW, NAVY, PANEL, WHITE, LIGHT = "FFAE10", "012047", "01445C", "FFFFFF", "7DD3FC"
MIN_PT = 32

# chart colours (names kept from the chart code): IRF = yellow, Spark RF = light blue, Python = white
TEAL, AMBER, SKY, MUTED = YELLOW, LIGHT, WHITE, "CBD5E1"
CH = {"Python-RFA": SKY, "Spark-RFA": AMBER, "Spark-IRFA": TEAL}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 30, "text.color": "white", "axes.labelcolor": "white",
    "xtick.color": "white", "ytick.color": "white", "axes.edgecolor": "#5B7BA6", "axes.facecolor": "none",
    "figure.facecolor": "none", "axes.grid": True, "grid.color": "#2C4F7C", "grid.linewidth": 1.2,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "lines.linewidth": 4,
    "lines.markersize": 16, "xtick.labelsize": 30, "ytick.labelsize": 30, "axes.labelsize": 32,
    "legend.fontsize": 30,
})


def _c(h):
    return "#" + h


def chart_e1(res, out):
    d = pd.read_csv(os.path.join(res, "e1_accuracy.csv")).groupby(["method", "n_trees"], as_index=False).accuracy.mean()
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    for m in ["Python-RFA", "Spark-RFA", "Spark-IRFA"]:
        x = d[d.method == m].sort_values("n_trees")
        ax.plot(x.n_trees, 100 * x.accuracy, marker="o", color=_c(CH[m]), label=f"{m}")
    for m in ["Spark-RFA", "Spark-IRFA"]:
        p = PAPER["e1_accuracy"][m]
        ax.plot(list(p), list(p.values()), marker="D", ls="--", lw=3, color=_c(CH[m]), alpha=0.6)
    ax.text(110, 96.0, "dashed = paper", color=_c(MUTED), fontsize=30)
    ax.set_xlabel("Number of trees")
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(95, 100.4)
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.62))
    fig.tight_layout()
    fig.savefig(out, dpi=150, transparent=True)
    plt.close(fig)


def chart_diag(res, out):
    d = pd.read_csv(os.path.join(res, "e1_accuracy.csv"))
    d = d[d.n_trees == 100].groupby("method", as_index=False).diag_s.mean()
    order = ["Python-RFA", "Spark-RFA", "Spark-IRFA"]
    d = d.set_index("method").reindex(order)
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    bars = ax.bar(["Python", "Spark RF", "Spark IRF"], d.diag_s, color=[_c(CH[m]) for m in order], width=0.6)
    for b, v in zip(bars, d.diag_s):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.08, f"{v:.2f} s", ha="center", fontsize=32, color="white")
    ax.set_ylabel("Diagnosis time (s)")
    ax.set_ylim(0, max(d.diag_s) * 1.25)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(out, dpi=150, transparent=True)
    plt.close(fig)


def chart_e2(res, out):
    d = pd.read_csv(os.path.join(res, "e2_scalability.csv")).groupby(["method", "cores"], as_index=False).train_s.mean()
    x = d[d.method == "Spark-IRFA"].sort_values("cores")
    red = 100 * (1 - x.train_s / x.train_s.iloc[0])
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    ax.plot(x.cores, red, marker="o", color=_c(TEAL), label="Ours (cores)")
    p = PAPER["e2_train_reduction_nodes"]
    ax.plot(list(p), list(p.values()), marker="D", ls="--", color=_c(MUTED), label="Paper (nodes)")
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("Cores (ours) / worker nodes (paper)")
    ax.set_ylabel("Training time saved (%)")
    ax.set_ylim(-3, 85)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=150, transparent=True)
    plt.close(fig)


def chart_e3(res, out):
    d = pd.read_csv(os.path.join(res, "e3_datasize.csv")).groupby(["method", "raw_gb"], as_index=False)[["accuracy", "train_s"]].mean()
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    for m in ["Spark-RFA", "Spark-IRFA"]:
        x = d[d.method == m].sort_values("raw_gb")
        ax.plot(x.raw_gb, x.train_s, marker="o", color=_c(CH[m]), label=m)
        if m == "Spark-IRFA":
            for gx, gy, a in zip(x.raw_gb, x.train_s, x.accuracy):
                ax.annotate(f"{100 * a:.2f}%", (gx, gy), textcoords="offset points", xytext=(0, 22),
                            ha="center", fontsize=30, color=_c(TEAL))
    ticks = sorted(d.raw_gb.unique())
    ax.set_xticks(ticks, [f"{t:.1f}" for t in ticks])
    ax.set_xlabel("Dataset size (GB)")
    ax.set_ylabel("Training time (s)")
    ax.set_ylim(0, d.train_s.max() * 1.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=150, transparent=True)
    plt.close(fig)


def chart_sweep(res, out):
    d = pd.read_csv(os.path.join(res, "e1_threshold_sweep.csv"))
    d = d[d.n_trees == 100].groupby("threshold", as_index=False).final_trees.mean()
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    ax.plot(d.threshold, d.final_trees, marker="o", color=_c(TEAL))
    ax.axvline(0.5, color=_c(AMBER), ls="--", lw=3)
    ax.text(0.52, d.final_trees.max() * 0.15, "used: 0.5", color=_c(AMBER), fontsize=30)
    ax.set_xlabel("Similarity threshold")
    ax.set_ylabel("Trees kept (of 100)")
    ax.set_ylim(0, d.final_trees.max() * 1.15)
    fig.tight_layout()
    fig.savefig(out, dpi=150, transparent=True)
    plt.close(fig)


# ------------------------------------------------------------------ pptx helpers
def duplicate_slide(prs, src):
    """Append a copy of `src` (shapes and their image relationships)."""
    new = prs.slides.add_slide(src.slide_layout)
    for shp in list(new.shapes):
        shp._element.getparent().remove(shp._element)
    rid_map = {}
    for rid, rel in src.part.rels.items():
        if rel.is_external or "notesSlide" in rel.reltype or "slideLayout" in rel.reltype:
            continue
        rid_map[rid] = new.part.relate_to(rel._target, rel.reltype)
    tree = new.shapes._spTree
    for el in src.shapes._spTree.iterchildren():
        if el.tag.endswith("}nvGrpSpPr") or el.tag.endswith("}grpSpPr"):
            continue
        tree.append(copy.deepcopy(el))
    xml_attrs = [qn("r:embed"), qn("r:link"), qn("r:id")]
    for node in tree.iter():
        for a in xml_attrs:
            v = node.get(a)
            if v in rid_map:
                node.set(a, rid_map[v])
    bg = src._element.find(qn("p:cSld")).find(qn("p:bg"))
    if bg is not None:
        new._element.find(qn("p:cSld")).insert(0, copy.deepcopy(bg))
    return new


def move_slide(prs, slide, index):
    lst = prs.slides._sldIdLst
    el = [e for e in lst if prs.slides.part.related_part(e.get(qn("r:id"))) is slide.part][0]
    lst.remove(el)
    lst.insert(index, el)


def delete_slide(prs, slide):
    lst = prs.slides._sldIdLst
    for e in list(lst):
        if prs.slides.part.related_part(e.get(qn("r:id"))) is slide.part:
            prs.part.drop_rel(e.get(qn("r:id")))
            lst.remove(e)


def remove(slide, *names):
    for shp in list(slide.shapes):
        if shp.name in names:
            shp._element.getparent().remove(shp._element)


def keep_only(slide, *names):
    for shp in list(slide.shapes):
        if shp.name not in names:
            shp._element.getparent().remove(shp._element)


def remove_text(slide):
    for shp in list(slide.shapes):
        if shp.has_text_frame and shp.text_frame.text.strip():
            shp._element.getparent().remove(shp._element)


def group(slide, name):
    return [s for s in slide.shapes if s.name == name][0]


def _runs(p, t, size, color, bold, font=None):
    """**text** is highlighted (bold, yellow on dark / navy on yellow handled by caller colour)."""
    for part in re.split(r"(\*\*[^*]+\*\*)", t):
        if not part:
            continue
        hi = part.startswith("**")
        r = p.add_run()
        r.text = part[2:-2] if hi else part
        r.font.name = font or (BOLD_FONT if (bold or hi) else BODY_FONT)
        r.font.size = Pt(size)
        r.font.color.rgb = RGBColor.from_string((YELLOW if color == WHITE else color) if hi else color)


def _fill_tf(tf, paras, size, color, bold, align, bullets, spacing, font=None):
    first = True
    for item in paras:
        t, sz, c, b = (item, size, color, bold) if isinstance(item, str) else (list(item) + [size, color, bold][len(item) - 1:])[:4]
        assert sz >= MIN_PT, f"font {sz} < {MIN_PT}: {t}"
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.space_after = Pt(spacing)
        if bullets:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.45)))
            pPr.set("indent", str(-Inches(0.45)))
            clr = pPr.makeelement(qn("a:buClr"), {})
            clr.append(clr.makeelement(qn("a:srgbClr"), {"val": YELLOW if color == WHITE else NAVY}))
            pPr.append(clr)
            pPr.append(pPr.makeelement(qn("a:buFont"), {"typeface": "Arial"}))
            pPr.append(pPr.makeelement(qn("a:buChar"), {"char": "■"}))
        _runs(p, t, sz, c, b, font)


def text(slide, x, y, w, h, paras, size=MIN_PT, color=WHITE, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, bullets=False, spacing=8, font=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, Emu(0))
    _fill_tf(tf, paras, size, color, bold, align, bullets, spacing, font)
    return tb


def title(slide, t, x, y, w, h, size=80, color=YELLOW, align=PP_ALIGN.LEFT):
    return text(slide, x, y, w, h, [(t, size, color)], font=TITLE_FONT, align=align, anchor=MSO_ANCHOR.MIDDLE, spacing=0)


def box(slide, x, y, w, h, paras, style="panel", size=MIN_PT, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE,
        bullets=False, spacing=8, pad=0.3, radius=0.12, bold=False):
    """Coloured text box. style: panel (navy-teal + yellow border), yellow (filled), outline (navy + yellow border)."""
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = radius
    fill, line, color = {"panel": (PANEL, YELLOW, WHITE), "yellow": (YELLOW, YELLOW, NAVY),
                         "outline": (NAVY, YELLOW, WHITE), "white": (WHITE, WHITE, NAVY)}[style]
    s.fill.solid()
    s.fill.fore_color.rgb = RGBColor.from_string(fill)
    s.line.color.rgb = RGBColor.from_string(line)
    s.line.width = Pt(2.5)
    s.shadow.inherit = False
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Inches(pad))
    for m in ("margin_top", "margin_bottom"):
        setattr(tf, m, Inches(min(pad, 0.15)))
    _fill_tf(tf, paras, size, color, bold, align, bullets, spacing)
    return s


def label(slide, x, y, w, h, t, size=MIN_PT, color=NAVY, align=PP_ALIGN.LEFT):
    """Text placed on an existing template bar/pill."""
    return text(slide, x, y, w, h, [t], size=size, color=color, bold=True, align=align, anchor=MSO_ANCHOR.MIDDLE, spacing=0)


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def chart_slide(slide, img, heading, points, note):
    keep_only(slide, "Freeform 42", "Group 43", "Group 46")
    title(slide, heading, 1.12, 0.75, 13.0, 1.35, size=72)
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.12), Inches(2.45), Inches(10.2), Inches(7.75))
    panel.adjustments[0] = 0.05
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor.from_string("001735")
    panel.line.color.rgb = RGBColor.from_string(YELLOW)
    panel.line.width = Pt(1.5)
    panel.shadow.inherit = False
    slide.shapes.add_picture(img, Inches(1.22), Inches(2.70), Inches(10.0), Inches(10.0 * 7.6 / 10.5))
    box(slide, 11.75, 3.65, 7.0, 6.55, points, style="panel", bullets=True, spacing=14, anchor=MSO_ANCHOR.MIDDLE)
    notes(slide, note)


# ------------------------------------------------------------------ build
def main():
    cfg = load_config()
    res = cfg["paths"]["results_dir"]
    V = add_verdicts(build_values(cfg))
    fig_dir = os.path.join(cfg["paths"]["figures_dir"], "slides")
    os.makedirs(fig_dir, exist_ok=True)
    F = {k: os.path.join(fig_dir, f"{k}.png") for k in ("e1", "diag", "e2", "e3", "sweep")}
    chart_e1(res, F["e1"]); chart_diag(res, F["diag"]); chart_e2(res, F["e2"]); chart_e3(res, F["e3"]); chart_sweep(res, F["sweep"])

    prs = Presentation(THEME)
    T = list(prs.slides)                                   # 14 template slides
    copies = [duplicate_slide(prs, T[12]) for _ in range(6)]   # 5 chart slides + claims slide

    # 1 title -------------------------------------------------------------------
    s = T[0]
    remove_text(s)
    text(s, 2.0, 1.33, 9.5, 0.65, ["AI508 BIG DATA TECHNOLOGIES"], bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.12, 2.35, 10.3, 4.3, [("REPRODUCING", 96, YELLOW), ("SPARK-BASED BEARING", 80, WHITE),
                                    ("FAULT DIAGNOSIS", 96, YELLOW)], font=TITLE_FONT, spacing=0, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.12, 6.95, 9.9, 1.6, ["Improved Random Forest \u2022 Wan et al. (2021)", "IEEE Access, vol. 9"], size=34, spacing=4)
    label(s, 1.12, 9.45, 4.27, 0.9, f"{V['AUTHOR']} – {V['STUDENT_ID']}", align=PP_ALIGN.CENTER)
    label(s, 4.90, 9.45, 4.56, 0.9, "Assignment 2", align=PP_ALIGN.CENTER)
    notes(s, "Introduce the paper and the aim: rebuild the method from scratch, run the experiments, and compare with the original results.")

    # 2 agenda (table of contents) ------------------------------------------------
    s = T[2]
    remove_text(s)
    title(s, "AGENDA", 2.73, 1.95, 14.54, 1.6, size=96, align=PP_ALIGN.CENTER)
    for (x, y), t in zip([(1.90, 5.01), (4.62, 6.97), (7.35, 5.01), (10.07, 6.97), (12.79, 5.01)],
                         ["Original Study", "Data & Pipeline", "Improved Forest", "Results E1–E3", "Comparison"]):
        label(s, x, y, 5.31, 1.18, t, align=PP_ALIGN.CENTER)
    notes(s, "Five parts: the paper, how the data were prepared with Spark, the algorithm, the three experiments, and what was and was not reproduced.")

    # 3 original study --------------------------------------------------------------
    s = T[3]
    remove_text(s)
    title(s, "THE ORIGINAL STUDY", 1.12, 3.0, 10.5, 1.45, size=80)
    box(s, 1.12, 4.65, 10.2, 3.55, [("Wan et al., IEEE Access 9 (2021)", 34, YELLOW, True),
                                    ("Q2 journal • pp. 37866–37882", 34),
                                    ("Spark + Improved Random Forest", 34),
                                    ("CWRU bearing data • no code published", 34)], style="outline", spacing=6)
    notes(s, "The paper diagnoses rolling-bearing faults with a random forest on Apache Spark. Its code is not public, so everything was rebuilt from the text.")

    # 4 problem -----------------------------------------------------------------------
    s = T[5]
    remove_text(s)
    remove(s, "Freeform 10")
    title(s, "THE PROBLEM", 1.12, 1.35, 14.0, 1.6, size=88)
    box(s, 1.12, 3.45, 14.8, 2.25, ["Random forests on big vibration data are **slow** to train and to apply"],
        style="yellow", size=38)
    box(s, 1.12, 6.05, 14.8, 3.6, ["Many trees are **weak** or vote **the same way**",
                                   "Idea: keep only accurate, different trees and run every step on Spark"],
        style="outline", size=36, bullets=True, spacing=14)
    notes(s, "Two problems: speed on big data, and redundant trees. The paper's answer is the improved random forest plus Spark.")

    # 5 objectives (three cards) -----------------------------------------------------------
    s = T[11]
    remove_text(s)
    title(s, "OBJECTIVES", 3.0, 1.1, 14.0, 1.6, size=88, align=PP_ALIGN.CENTER)
    text(s, 3.0, 2.85, 14.0, 0.9, ["Rebuild the method from scratch, then measure:"], size=36, align=PP_ALIGN.CENTER)
    for x, (h, b) in zip([2.28, 7.76, 13.24], [("E1 • ACCURACY", "Accuracy vs number of trees"),
                                               ("E2 • SCALING", "Speed with 1–4 cores"),
                                               ("E3 • DATA SIZE", "Effect of data size")]):
        label(s, x, 6.85, 4.48, 1.2, h, size=34, color=WHITE, align=PP_ALIGN.CENTER)
        text(s, x, 8.2, 4.48, 1.75, [b], color=NAVY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=0)
    notes(s, "Three experiments agreed in the proposal: accuracy with 20, 100 and 200 trees; scalability with 1 to 4 cores; and data size from 1.4 to 5.6 GB.")

    # 6 data ------------------------------------------------------------------------------------
    s = T[4]
    remove_text(s)
    title(s, "THE DATA", 1.12, 1.6, 10.0, 1.5, size=88)
    box(s, 1.12, 3.45, 9.95, 4.75, ["CWRU bearing data, 12 kHz", "10 classes × 4 motor loads",
                                    "Windows of 2,048 samples", f"{V['N_WINDOWS']} windows = **{V['RAW_GB']} GB**"],
        style="panel", size=36, bullets=True, spacing=14)
    notes(s, "Forty public files: normal and nine fault types under four loads. Overlapping sampling enlarges them to the size of the paper's first dataset.")

    # 7 pipeline (three bars) -------------------------------------------------------------------
    s = T[6]
    remove_text(s)
    title(s, "BIG DATA PIPELINE", 1.12, 0.35, 11.0, 1.3, size=72)
    rows = [("1 • SPARK: WINDOWS + FEATURES", f"{V['N_WINDOWS']} windows → 8 wavelet-packet energies"),
            ("2 • SPARK MLLIB: TRAINING", "Random forests with 20, 100 and 200 trees"),
            ("3 • SPARK: IRF STEPS + TESTING", "Broadcast trees, parallel similarity, timing")]
    for g, y, (h, d) in zip(["Group 3", "Group 8", "Group 13"], [1.85, 4.6, 7.35], rows):
        group(s, g).top = Inches(y)
        label(s, 1.45, y, 10.4, 0.93, h)
        text(s, 1.12, y + 1.05, 10.94, 1.4, [d], size=34)
    notes(s, "Every heavy step runs in Spark: window generation and feature extraction with mapInPandas, training with MLlib, and the IRF steps with broadcast trees.")

    # 8 improved random forest (three rows) ---------------------------------------------------------
    s = T[8]
    remove_text(s)
    title(s, "IMPROVED RANDOM FOREST", 1.12, 1.75, 16.8, 1.55, size=84)
    rows = [("1 • TRAIN + FILTER", "Train k trees, drop trees below the mean validation accuracy"),
            ("2 • COMPARE PATHS", "Tree similarity from matching nodes on root-to-leaf paths"),
            ("3 • KEEP THE BEST", "Keep the most accurate tree of each group of similar trees")]
    for y, (h, d) in zip([4.05, 6.04, 8.04], rows):
        label(s, 2.10, y, 5.6, 0.76, h)
        text(s, 1.98, y + 0.86, 15.5, 0.8, [d], size=32)
    notes(s, "Train RF; score each tree on validation data and drop weak ones; extract root-to-leaf paths; compute tree similarity from matching nodes; group similar trees and keep the most accurate one per group.")

    # 9 measures ---------------------------------------------------------------------------------------
    s = T[1]
    remove_text(s)
    title(s, "WHAT WE MEASURED", 4.3, 1.45, 11.6, 1.5, size=84, align=PP_ALIGN.CENTER)
    box(s, 3.9, 3.5, 6.0, 5.6, ["Test accuracy", "Training time", "Diagnosis time", "Speed-up with cores"],
        style="yellow", size=36, bullets=True, spacing=16)
    box(s, 10.2, 3.5, 5.9, 5.6, [("Run on", 36, YELLOW, True), "GitHub Actions", f"4 vCPUs, {V['ENV_RAM']} GB RAM",
                                 "Spark 3.5, local mode"], style="outline", size=34, spacing=14)
    notes(s, "Same measures as the paper. All runs were executed by the GitHub Actions workflow on a 4-vCPU machine; the results are in the repository.")

    # 10 setup differences (three label rows) -----------------------------------------------------------
    s = T[10]
    remove_text(s)
    title(s, "PAPER VS OUR SETUP", 1.12, 1.5, 10.5, 2.75, size=84)
    for y, (h, d) in zip([5.02, 6.68, 8.35], [("PLATFORM", "5-node cluster → one 4-core machine"),
                                              ("PARALLELISM", "Worker nodes → executor cores"),
                                              ("SETTINGS", "Missing in paper → documented assumptions")]):
        label(s, 1.30, y + 0.1, 3.9, 1.23, h, color=YELLOW, align=PP_ALIGN.CENTER)
        text(s, 5.55, y + 0.08, 6.25, 1.27, [d], anchor=MSO_ANCHOR.MIDDLE, spacing=0)
    notes(s, "Main discrepancies, all listed in the report's discrepancy table: single machine, cores instead of nodes, no HDFS, and assumed window length, wavelet, depth and threshold.")

    # 11-15 charts -------------------------------------------------------------------------------------------
    chart_slide(copies[0], F["e1"], "E1 – ACCURACY", [
        f"All forests ≈ **{V['E1_RF_200_ACC']}%**", "Paper: 96.4–97.2%",
        f"IRF keeps only **{V['E1_IRF_200_NTREES']} of 200** trees", "Near-perfect accuracy leaves no room for an IRF gain"],
        "Solid lines are our runs, dashed lines the paper. Our forests are about 3 points more accurate, and IRF equals Spark RF while using far fewer trees.")
    chart_slide(copies[1], F["diag"], "FASTER DIAGNOSIS", [
        f"IRF: **−{V['E1_DIAGRED_100']}%** time vs Spark RF", "Paper: −74.3%", "Fewer trees = fewer predictions",
        "Plain Python is fastest at this size (Spark start-up cost)"],
        "100 trees, whole test set. The smaller forest diagnoses about four times faster than Spark RF, close to the paper. Python is faster here because the data fit in memory and Spark has fixed job overhead.")
    chart_slide(copies[2], F["sweep"], "THRESHOLD MATTERS", [
        f"Threshold 0.3 → **{V['SW_N_3']}** trees", f"Threshold 0.5 → **{V['SW_N_5']}** trees",
        f"Threshold 0.9 → **{V['SW_N_9']}** trees", "The paper does not give its value"],
        "The similarity threshold decides how many trees survive. The paper only says a small value was chosen, so this is a key source of difference.")
    chart_slide(copies[3], F["e2"], "E2 – SCALABILITY", [
        f"**−{V['E2_RED_4']}%** training time with 4 cores", "Paper: −73.3% with 4 nodes",
        "Cores share one memory bus", f"IRF costs **+{V['E2_OVERHEAD_MAX']}%** training (paper +86%)"],
        "Same trend as the paper but a smaller gain, because extra cores of one machine are weaker than extra machines. The optimisation step adds training cost, as in the paper.")
    chart_slide(copies[4], F["e3"], "E3 – DATA SIZE", [
        f"Accuracy flat: **{V['E3_IRF_ACC_100']}%**", "Paper: +1.0 point from 5.6 to 20.4 GB",
        f"Training time {V['E3_IRF_TRAIN_25']} → {V['E3_IRF_TRAIN_100']} s", "Overlapping windows add volume, not information"],
        "Labels show IRF accuracy at each size. Accuracy does not change; training time grows roughly with the number of rows.")

    # 16 claims ----------------------------------------------------------------------------------------------
    s = copies[5]
    keep_only(s, "Freeform 42", "Group 43", "Group 46")
    title(s, "CLAIMS VS OUR RESULTS", 1.12, 0.75, 13.0, 1.35, size=72)
    text(s, 1.12, 2.3, 13.0, 0.8, [(f"{V['V_COUNT']} of 6 claims reproduced", 38, WHITE, True)], anchor=MSO_ANCHOR.MIDDLE)
    items = [("✓ Faster diagnosis", f"−{V['E1_DIAGRED_100']}%", True),
             ("✗ IRF accuracy gain", f"{V['E1_D_IRF_RF_200']} pts", False),
             ("✓ Scales with cores", f"−{V['E2_RED_4']}%", True),
             ("✗ Accuracy level", f"{V['E1_GAP_RF_200']} pts", False),
             ("✓ IRF costs more", f"+{V['E2_OVERHEAD_MAX']}%", True),
             ("✗ Gain with data size", "0.00 pts", False)]
    for k, (a, b, ok) in enumerate(items):
        x, y = 1.12 + (k % 2) * 8.95, 3.55 + (k // 2) * 2.05
        box(s, x, y, 8.6, 1.6, [f"{a}  **{b}**" if not ok else f"{a}  {b}"], style="yellow" if ok else "outline",
            size=36, bold=ok)
    text(s, 1.12, 9.75, 17.5, 0.8, ["Yellow = reproduced • Dark = not reproduced"], size=32, color=WHITE)
    notes(s, "Left column: claims reproduced. Right column: not reproduced. The accuracy claims fail mainly because every forest is already above 99.7%.")

    # 17 why results differ (three columns) ------------------------------------------------------------------
    s = T[7]
    remove_text(s)
    title(s, "WHY RESULTS DIFFER", 1.17, 1.8, 17.65, 1.6, size=88, align=PP_ALIGN.CENTER)
    for x, (h, b) in zip([2.40, 8.23, 14.05], [("EASIER TASK", "10 classes, 12 kHz data only; paper's class list differs"),
                                               ("CEILING", f"Every forest above 99.7%; time-split test still {V['B_RF_200_ACC']}%"),
                                               ("SETUP", "Cores are not cluster nodes; key settings missing")]):
        label(s, x + 0.25, 5.30, 4.15, 0.79, h)
        text(s, x, 6.3, 4.45, 3.4, [b], size=32)
    notes(s, "The extra check E1b split every recording by time; accuracy stayed above 99.6%, so overlapping windows do not explain the high accuracy.")

    # 18 conclusion (three wide rows) ----------------------------------------------------------------------------
    s = T[12]
    remove_text(s)
    title(s, "CONCLUSION", 1.12, 1.6, 15.0, 1.6, size=88)
    for y, (h, d) in zip([4.61, 6.60, 8.60], [("REPRODUCED", "Faster diagnosis, scaling with cores, extra training cost"),
                                              ("NOT OBSERVABLE", "IRF accuracy gain: every forest is above 99.7%"),
                                              ("LESSON", "Paper only partly reproducible: missing settings, no code")]):
        label(s, 2.27, y, 14.0, 0.76, h)
        text(s, 1.98, y + 0.86, 15.8, 0.8, [d], size=32)
    notes(s, "Key message: the method works as described for speed, but its accuracy advantage could not be tested on such an easy task. Next step: a real cluster and a harder task.")

    # 19 thank you -----------------------------------------------------------------------------------------------
    s = T[13]
    remove_text(s)
    remove(s, "Freeform 18", "Group 25", "Group 28", "Freeform 33", "Freeform 35", "Freeform 37", "Freeform 39")
    title(s, "THANK YOU", 1.12, 2.75, 12.0, 2.3, size=130)
    label(s, 1.12, 5.51, 5.35, 0.82, "AI508 – Assignment 2", align=PP_ALIGN.CENTER)
    label(s, 6.67, 5.52, 5.35, 0.82, f"{V['AUTHOR']} – {V['STUDENT_ID']}", align=PP_ALIGN.CENTER)
    box(s, 1.12, 6.62, 14.0, 1.0, ["github.com/amnaaljasmi701/ai508-bearing-irf-reproduction"], style="outline",
        size=32, pad=0.25)
    notes(s, "Invite questions.")

    # order ------------------------------------------------------------------------------------------------------
    delete_slide(prs, T[9])
    order = [T[0], T[2], T[3], T[5], T[11], T[4], T[6], T[8], T[1], T[10], *copies[:5], copies[5], T[7], T[12], T[13]]
    for i, sl in enumerate(order):
        move_slide(prs, sl, i)
    prs.save(OUT)
    print("wrote", OUT, "slides:", len(prs.slides))


if __name__ == "__main__":
    main()
