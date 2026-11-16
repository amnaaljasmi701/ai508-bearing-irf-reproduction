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
FONT = "Red Hat Display"
WHITE, TEAL, AMBER, SKY, MUTED = "FFFFFF", "14B8A6", "F59E0B", "60A5FA", "CBD5E1"
MIN_PT = 32

# ------------------------------------------------------------------ dark charts
CH = {"Python-RFA": SKY, "Spark-RFA": AMBER, "Spark-IRFA": TEAL}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 30, "text.color": "white", "axes.labelcolor": "white",
    "xtick.color": "white", "ytick.color": "white", "axes.edgecolor": "#64748B", "axes.facecolor": "none",
    "figure.facecolor": "none", "axes.grid": True, "grid.color": "#334155", "grid.linewidth": 1.2,
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


def remove(slide, *names):
    for shp in list(slide.shapes):
        if shp.name in names or (names == ("ALLTEXT",) and shp.shape_type == 17):
            shp._element.getparent().remove(shp._element)


def remove_text(slide):
    for shp in list(slide.shapes):
        if shp.has_text_frame and shp.text_frame.text.strip():
            shp._element.getparent().remove(shp._element)


def text(slide, x, y, w, h, paras, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, bullets=False, spacing=6, size=MIN_PT):
    """paras: list of (text, size_pt, bold, color) tuples or plain strings (32 pt white)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, Emu(0))
    first = True
    for item in paras:
        if isinstance(item, str):
            item = (item, size, False, WHITE)
        t, size, bold, color = item
        assert size >= MIN_PT, f"font {size} < {MIN_PT}: {t}"
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.space_after = Pt(spacing)
        if bullets:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.5)))
            pPr.set("indent", str(-Inches(0.5)))
            for tag in ("a:buFont", "a:buChar"):
                pass
            bf = pPr.makeelement(qn("a:buFont"), {"typeface": "Arial"})
            bc = pPr.makeelement(qn("a:buChar"), {"char": "•"})
            clr = pPr.makeelement(qn("a:buClr"), {})
            clr.append(clr.makeelement(qn("a:srgbClr"), {"val": TEAL}))
            pPr.append(clr)
            pPr.append(bf)
            pPr.append(bc)
        for k, part in enumerate(re.split(r"(\*\*[^*]+\*\*)", t)):
            if not part:
                continue
            r = p.add_run()
            r.text = part.strip("*") if part.startswith("**") else part
            r.font.name = FONT
            r.font.size = Pt(size)
            r.font.bold = bold or part.startswith("**")
            r.font.color.rgb = RGBColor.from_string(AMBER if part.startswith("**") and not bold else color)
    return tb


def pill(slide, x, y, w, h, t, size=32, outline=AMBER, fill=None, color=WHITE):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.3
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = RGBColor.from_string(fill)
    else:
        s.fill.background()
    s.line.color.rgb = RGBColor.from_string(outline)
    s.line.width = Pt(2.5)
    s.shadow.inherit = False
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Inches(0.25))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    for part in re.split(r"(\*\*[^*]+\*\*)", t):
        if not part:
            continue
        r = p.add_run()
        r.text = part.strip("*")
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = part.startswith("**")
        r.font.color.rgb = RGBColor.from_string(AMBER if part.startswith("**") else color)
    return s


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def title(slide, t, x, y, w, h, size=80, align=PP_ALIGN.LEFT):
    return text(slide, x, y, w, h, [(t, size, False, WHITE)], align=align, anchor=MSO_ANCHOR.MIDDLE, spacing=0)


def chart_slide(slide, img, heading, points, note):
    remove_text(slide)
    remove(slide, "Group 6", "Freeform 8", "Freeform 9")
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.3), Inches(1.4), Inches(10.6), Inches(7.7))
    panel.adjustments[0] = 0.04
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor.from_string("0B1220")
    sf = panel.fill._xPr.find(qn("a:solidFill"))[0]
    sf.append(sf.makeelement(qn("a:alpha"), {"val": "78000"}))
    panel.line.fill.background()
    panel.shadow.inherit = False
    slide.shapes.add_picture(img, Inches(1.35), Inches(1.45), Inches(10.5), Inches(7.6))
    title(slide, heading, 12.2, 1.45, 6.5, 1.3, size=54)
    text(slide, 12.2, 3.0, 6.45, 6.9, points, bullets=True, spacing=14)
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
    T = list(prs.slides)                      # 15 template slides
    vis = T[11]
    extra = [duplicate_slide(prs, vis) for _ in range(4)]

    # 1 title -------------------------------------------------------------
    s = T[0]
    remove_text(s)
    text(s, 1.3, 1.0, 9, 0.7, [("AI508 Big Data Technologies", 32, False, MUTED)])
    text(s, 10.7, 1.0, 8.0, 0.7, [(f"{V['AUTHOR']} – {V['STUDENT_ID']}", 32, False, MUTED)], align=PP_ALIGN.RIGHT)
    text(s, 1.5, 2.3, 17.0, 4.8, [("Reproducing Spark-Based Bearing Fault Diagnosis", 72, True, WHITE)],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.6, 7.62, 16.8, 1.2, [("Improved Random Forest • Wan et al. (2021) • IEEE Access", 36, False, WHITE)],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.5, 9.35, 17.0, 0.8, [("Assignment 2 – Reproduction Study", 32, False, TEAL)], align=PP_ALIGN.CENTER)
    notes(s, "Introduce the paper and the aim: rebuild the method from scratch, run the experiments, and compare with the original results.")

    # 2 agenda --------------------------------------------------------------
    s = T[1]
    remove_text(s)
    title(s, "Agenda", 1.86, 1.7, 9.5, 1.8, size=96)
    text(s, 1.86, 3.9, 9.8, 5.6, ["The original study", "Data and Big Data pipeline", "The improved random forest",
                                   "Results: E1, E2, E3", "Comparison and lessons"], bullets=True, spacing=16, size=40)
    notes(s, "Five parts: the paper, how the data were prepared with Spark, the algorithm, the three experiments, and what was and was not reproduced.")

    # 3 original study --------------------------------------------------------
    s = T[2]
    remove_text(s)
    title(s, "The Original Study", 5.0, 2.3, 10.0, 1.6, size=72, align=PP_ALIGN.CENTER)
    text(s, 5.2, 4.3, 9.6, 5.3, [("Wan et al., IEEE Access 9 (2021)", 36, True, AMBER),
                                  "Q2 journal, pages 37866–37882",
                                  "Spark + Improved Random Forest (IRF)",
                                  "Bearing faults from CWRU vibration data",
                                  "No code published"], align=PP_ALIGN.CENTER, spacing=12)
    notes(s, "The paper diagnoses rolling-bearing faults with a random forest on Apache Spark. Its code is not public, so everything was rebuilt from the text.")

    # 4 problem -----------------------------------------------------------------
    s = T[3]
    remove_text(s)
    title(s, "The Problem", 7.93, 1.7, 10.5, 1.7, size=80)
    text(s, 7.93, 3.7, 10.4, 6.0, ["Random forests on big vibration data are slow to train and apply",
                                    "Many trees are weak or vote the same way",
                                    "Idea: keep only accurate, different trees and run every step on Spark"],
         bullets=True, spacing=20, size=40)
    notes(s, "Two problems: speed on big data, and redundant trees. The paper's answer is the improved random forest plus Spark.")

    # 5 objectives -----------------------------------------------------------------
    s = T[4]
    remove_text(s)
    remove(s, "Freeform 9", "Freeform 10", "Freeform 11")
    title(s, "Objectives of the Reproduction", 1.6, 1.6, 16.8, 1.7, size=72, align=PP_ALIGN.CENTER)
    text(s, 9.7, 3.9, 8.8, 0.8, [("Rebuilt from scratch, then measured:", 32, True, AMBER)])
    for k, (lab, d) in enumerate([("E1", "Accuracy vs number of trees"), ("E2", "Speed with 1–4 cores"),
                                   ("E3", "Effect of data size")]):
        pill(s, 9.7, 4.9 + k * 1.55, 8.7, 1.25, f"**{lab}**  {d}")
    notes(s, "Three experiments agreed in the proposal: accuracy with 20, 100 and 200 trees; scalability with 1 to 4 cores; and data size from 1.4 to 5.6 GB.")

    # 6 data -------------------------------------------------------------------------
    s = T[5]
    remove_text(s)
    title(s, "The Data", 1.12, 1.4, 8.5, 1.9, size=96)
    text(s, 1.12, 3.6, 8.6, 6.4, ["CWRU bearing data, 12 kHz", "10 classes × 4 motor loads",
                                   "Overlapping windows of 2,048 samples",
                                   f"{V['N_WINDOWS']} windows = **{V['RAW_GB']} GB**"], bullets=True, spacing=16, size=36)
    notes(s, "Forty public files: normal and nine fault types under four loads. Overlapping sampling enlarges them to the size of the paper's first dataset.")

    # 7 pipeline ----------------------------------------------------------------------
    s = T[6]
    remove_text(s)
    title(s, "Big Data Pipeline", 9.49, 1.4, 10.0, 1.6, size=80)
    text(s, 9.49, 3.3, 9.3, 6.8, ["Spark: cut signals into windows", "Spark: wavelet-packet features",
                                   "Spark MLlib: train the forest", "Spark: improved-forest steps",
                                   "Evaluate on the test set"], bullets=True, spacing=16, size=36)
    notes(s, "Every heavy step runs in Spark: window generation and feature extraction with mapInPandas, training with MLlib, and the IRF steps with broadcast trees.")

    # 8 IRF ---------------------------------------------------------------------------
    s = T[7]
    remove_text(s)
    title(s, "Improved Random Forest", 1.5, 1.5, 17.0, 1.7, size=80, align=PP_ALIGN.CENTER)
    text(s, 6.6, 3.92, 6.8, 1.1, [("How it works", 32, True, "0F172A")], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 5.1, 5.1, 10.0, 4.3, ["Train a normal forest", "Drop low-accuracy trees", "Compare trees by their paths",
                                   "Keep the best tree of each similar group"], bullets=True, spacing=8, size=36)
    notes(s, "Steps: train RF; score each tree on validation data and drop weak ones; extract root-to-leaf paths; compute tree similarity from matching nodes; group similar trees and keep the most accurate one per group.")

    # 9 measures ----------------------------------------------------------------------
    s = T[8]
    remove_text(s)
    remove(s, "Freeform 11")
    title(s, "What We Measured", 1.12, 1.6, 10.5, 1.8, size=80)
    text(s, 1.12, 3.8, 9.5, 6.0, ["Test accuracy", "Training time", "Diagnosis time", "Time saved with more cores"],
         bullets=True, spacing=18, size=40)
    text(s, 11.3, 3.8, 7.2, 5.8, [("Run on", 32, True, AMBER), "GitHub Actions runner",
                                   f"4 vCPUs, {V['ENV_RAM']} GB RAM", "Spark 3.5 local mode"], spacing=16, size=36)
    notes(s, "Same measures as the paper. All runs were executed by the GitHub Actions workflow on a 4-vCPU machine; the results are in the repository.")

    # 10 setup differences ------------------------------------------------------------
    s = T[9]
    remove_text(s)
    title(s, "Paper vs Our Setup", 9.2, 1.5, 9.5, 1.7, size=72)
    text(s, 9.2, 3.5, 9.4, 6.5, ["5-node cluster → one 4-core machine", "Worker nodes → executor cores",
                                  "HDFS → Parquet on disk", "Missing settings → documented assumptions"],
         bullets=True, spacing=18, size=36)
    notes(s, "Main discrepancies, all listed in the report's discrepancy table: single machine, cores instead of nodes, no HDFS, and assumed window length, wavelet, depth and threshold.")

    # 11-15 charts ----------------------------------------------------------------------
    chart_slide(vis, F["e1"], "E1 – Accuracy", [
        f"All forests ≈ **{V['E1_RF_200_ACC']}%**",
        "Paper: 96.4–97.2%",
        f"IRF keeps only **{V['E1_IRF_200_NTREES']} of 200** trees",
        "Near-perfect accuracy leaves no room for an IRF gain"],
        "Solid lines are our runs, dashed lines the paper. Our forests are about 3 points more accurate, and IRF equals Spark RF while using far fewer trees.")
    chart_slide(extra[0], F["diag"], "Faster Diagnosis", [
        f"IRF: **−{V['E1_DIAGRED_100']}%** time vs Spark RF",
        "Paper: −74.3%",
        "Fewer trees = fewer predictions",
        "At this size, plain Python is fastest (Spark start-up cost)"],
        "100 trees, whole test set. The smaller forest diagnoses about four times faster than Spark RF, close to the paper. Python is faster here because the data fit in memory and Spark has fixed job overhead.")
    chart_slide(extra[1], F["sweep"], "Threshold Matters", [
        f"Threshold 0.3 → {V['SW_N_3']} trees",
        f"Threshold 0.5 → {V['SW_N_5']} trees",
        f"Threshold 0.9 → {V['SW_N_9']} trees",
        "Paper does not give its value"],
        "The similarity threshold decides how many trees survive. The paper only says a small value was chosen, so this is a key source of difference.")
    chart_slide(extra[2], F["e2"], "E2 – Scalability", [
        f"**−{V['E2_RED_4']}%** training time with 4 cores",
        "Paper: −73.3% with 4 nodes",
        "Cores share one memory bus",
        f"IRF costs **+{V['E2_OVERHEAD_MAX']}%** training (paper +86%)"],
        "Same trend as the paper but a smaller gain, because extra cores of one machine are weaker than extra machines. The optimisation step adds training cost, as in the paper.")
    chart_slide(extra[3], F["e3"], "E3 – Data Size", [
        f"Accuracy flat: **{V['E3_IRF_ACC_100']}%**",
        "Paper: +1.0 point from 5.6 to 20.4 GB",
        f"Training time {V['E3_IRF_TRAIN_25']} → {V['E3_IRF_TRAIN_100']} s",
        "Overlapping windows add volume, not information"],
        "Labels show IRF accuracy at each size. Accuracy does not change; training time grows roughly with the number of rows.")

    # 16 claims -----------------------------------------------------------------------
    s = T[12]
    remove_text(s)
    for g in ("Group 6", "Group 9", "Group 12", "Group 15", "Freeform 18", "Freeform 19", "Freeform 20", "Freeform 21"):
        remove(s, g)
    title(s, "Claims vs Our Results", 2.0, 1.35, 16.0, 1.6, size=72, align=PP_ALIGN.CENTER)
    text(s, 2.0, 3.0, 16.0, 0.8, [(f"{V['V_COUNT']} of 6 claims reproduced", 36, True, TEAL)], align=PP_ALIGN.CENTER)
    items = [f"✓ Faster diagnosis **−{V['E1_DIAGRED_100']}%**", f"✗ IRF accuracy gain **{V['E1_D_IRF_RF_200']}**",
             f"✓ Scales with cores **−{V['E2_RED_4']}%**", f"✗ Accuracy level **{V['E1_GAP_RF_200']} pts**",
             f"✓ IRF costs more **+{V['E2_OVERHEAD_MAX']}%**", "✗ Gain with data size **0.00**"]
    for k, t in enumerate(items):
        pill(s, 1.6 + (k % 2) * 8.6, 4.15 + (k // 2) * 1.95, 8.2, 1.5, t, outline=TEAL if t.startswith("✓") else AMBER)
    notes(s, "Left column: claims reproduced. Right column: not reproduced. The accuracy claims fail mainly because every forest is already above 99.7%.")

    # 17 why differ ----------------------------------------------------------------------
    s = T[10]
    remove_text(s)
    remove(s, "Group 6", "Group 9")
    title(s, "Why Results Differ", 1.5, 2.2, 7.2, 5.5, size=80)
    text(s, 9.1, 2.0, 9.4, 7.8, ["Easier task: 10 classes, 12 kHz data only",
                                  "Accuracy ceiling above 99.7%",
                                  f"Not leakage: time-split test still {V['B_RF_200_ACC']}%",
                                  "Missing settings in the paper",
                                  "Cores are not cluster nodes"], bullets=True, spacing=18, size=36, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "The extra check E1b split every recording by time; accuracy stayed above 99.6%, so overlapping windows do not explain the high accuracy.")

    # 18 conclusion -------------------------------------------------------------------------
    s = T[13]
    remove_text(s)
    title(s, "Conclusion", 1.5, 1.6, 13.0, 1.7, size=80)
    text(s, 1.5, 3.6, 14.5, 6.3, ["Efficiency claims reproduced",
                                   "IRF accuracy gain not observable here",
                                   "Paper only partly reproducible: missing settings, no code",
                                   "All code, results and figures on GitHub"], bullets=True, spacing=20, size=40)
    notes(s, "Key message: the method works as described for speed, but its accuracy advantage could not be tested on such an easy task. Next step: a real cluster and a harder task.")

    # 19 thank you -----------------------------------------------------------------------------
    s = T[14]
    remove_text(s)
    text(s, 1.3, 1.0, 9, 0.7, [("AI508 Big Data Technologies", 32, False, MUTED)])
    text(s, 10.7, 1.0, 8.0, 0.7, [(f"{V['AUTHOR']} – {V['STUDENT_ID']}", 32, False, MUTED)], align=PP_ALIGN.RIGHT)
    title(s, "Thank You", 3.0, 3.0, 14.0, 2.2, size=110, align=PP_ALIGN.CENTER)
    text(s, 3.0, 5.4, 14.0, 0.9, [("Questions?", 44, True, WHITE)], align=PP_ALIGN.CENTER)
    text(s, 1.6, 7.62, 16.8, 1.2, [("github.com/amnaaljasmi701/ai508-bearing-irf-reproduction", 32, False, WHITE)],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "Invite questions.")

    order = [T[0], T[1], T[2], T[3], T[4], T[5], T[6], T[7], T[8], T[9], vis, extra[0], extra[1], extra[2], extra[3],
             T[12], T[10], T[13], T[14]]
    for i, sl in enumerate(order):
        move_slide(prs, sl, i)
    prs.save(OUT)
    print("wrote", OUT, "slides:", len(prs.slides))


if __name__ == "__main__":
    main()
