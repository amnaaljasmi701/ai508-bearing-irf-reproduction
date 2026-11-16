"""Fill the report and slide templates with the measured results.

  report/report_template.docx        -> report/AI508_A2_Report.docx

{{TOKENS}} in the text are replaced by values computed from results/*.csv|json
(src/irf_repro/report_values.py), and every image whose alt-text is "FIG:<name>.png"
is replaced by figures/<name>.png.  Nothing is typed by hand.
"""
import _bootstrap  # noqa: F401
import argparse
import os
import posixpath
import re
import zipfile
from xml.sax.saxutils import escape

from irf_repro.config import REPO_ROOT, load_config
from irf_repro.report_values import DASH, add_verdicts, build_values

TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def _rels_path(part):
    d, f = posixpath.split(part)
    return posixpath.join(d, "_rels", f + ".rels")


def fill(template, out, values, fig_dir):
    missing, used_figs = set(), []
    with zipfile.ZipFile(template) as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}

    # images: alt text FIG:<file> -> r:embed id -> media target
    replace_media = {}
    for part in names:
        if not part.endswith(".xml") or "_rels" in part:
            continue
        xml = data[part].decode("utf-8")
        figs = list(re.finditer(r'descr="FIG:([^"]+)"', xml))
        if not figs:
            continue
        rels = data.get(_rels_path(part), b"").decode("utf-8")
        for m in figs:
            emb = re.search(r'r:embed="([^"]+)"', xml[m.end():])
            if not emb:
                continue
            tgt = re.search(r'Id="%s"[^>]*Target="([^"]+)"' % re.escape(emb.group(1)), rels) or \
                re.search(r'Target="([^"]+)"[^>]*Id="%s"' % re.escape(emb.group(1)), rels)
            if not tgt:
                continue
            media = posixpath.normpath(posixpath.join(posixpath.dirname(part), tgt.group(1)))
            fig = os.path.join(fig_dir, m.group(1))
            if os.path.exists(fig):
                replace_media[media] = fig
                used_figs.append(m.group(1))

    def sub(match):
        key = match.group(1)
        if key not in values or values[key] in (None, ""):
            missing.add(key)
            return DASH
        return escape(str(values[key]), {'"': "&quot;"})

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            b = data[n]
            if n in replace_media:
                with open(replace_media[n], "rb") as fh:
                    b = fh.read()
            elif n.endswith(".xml") or n.endswith(".rels"):
                b = TOKEN.sub(sub, b.decode("utf-8")).encode("utf-8")
            zout.writestr(n, b)
    return sorted(missing), sorted(set(used_figs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join(REPO_ROOT, "report"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    cfg = load_config()
    values = add_verdicts(build_values(cfg))
    jobs = [("report_template.docx", "AI508_A2_Report.docx")]     # slides: scripts/09_build_slides.py
    for tpl, out in jobs:
        tpl_path = os.path.join(REPO_ROOT, "report", tpl)
        if not os.path.exists(tpl_path):
            print("template missing:", tpl_path)
            continue
        out_path = os.path.join(a.outdir, out)
        missing, figs = fill(tpl_path, out_path, values, cfg["paths"]["figures_dir"])
        print(f"wrote {out_path}  (figures inserted: {len(figs)})")
        if missing:
            print("  tokens without a value (shown as a dash):", ", ".join(missing))
    dashes = sorted(k for k, v in values.items() if v == DASH)
    if dashes:
        print(f"{len(dashes)} values are not available yet (experiment not run?): {', '.join(dashes[:25])}"
              + (" ..." if len(dashes) > 25 else ""))


if __name__ == "__main__":
    main()
