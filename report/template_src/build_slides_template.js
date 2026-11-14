// Builds report/presentation_template.pptx (13 slides, ~12 min). Filled by scripts/08_build_report.py.
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";               // 13.33 x 7.5 in
const NAVY = "1F3864", BLUE = "2A78D6", ORANGE = "EB6834", GREEN = "1BAF7A", INK = "222222", MUTED = "5F5E5A", LIGHT = "F3F5F9";
const F = "Calibri";

function base(title, notes) {
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.12, fill: { color: NAVY }, line: { color: NAVY } });
  s.addText(title, { x: 0.5, y: 0.3, w: 12.3, h: 0.75, fontFace: F, fontSize: 28, bold: true, color: NAVY, margin: 0 });
  s.addText("AI508 – Reproduction of Wan et al. (2021)", { x: 0.5, y: 7.05, w: 8, h: 0.3, fontFace: F, fontSize: 10, color: MUTED, margin: 0 });
  if (notes) s.addNotes(notes);
  return s;
}
function bullets(s, items, opts = {}) {
  const runs = [];
  items.forEach((t, i) => {
    const sub = t.startsWith("- ");
    runs.push({ text: sub ? t.slice(2) : t, options: { bullet: sub ? { indent: 18 } : true, indentLevel: sub ? 1 : 0,
      fontSize: sub ? 15 : 18, color: sub ? MUTED : INK, breakLine: i < items.length - 1, paraSpaceAfter: 6 } });
  });
  s.addText(runs, { x: opts.x ?? 0.6, y: opts.y ?? 1.3, w: opts.w ?? 12.1, h: opts.h ?? 5.5, fontFace: F, valign: "top", margin: 4 });
}
function fig(s, name, x, y, w, ratio) {
  s.addImage({ path: path.join(HERE, "placeholders", name), x, y, w, h: w * ratio, altText: `FIG:${name}` });
}
function table(s, rows, opts) {
  const data = rows.map((r, i) => r.map((c) => ({ text: String(c), options: {
    bold: i === 0, color: i === 0 ? "FFFFFF" : INK, fill: { color: i === 0 ? NAVY : (i % 2 ? "FFFFFF" : LIGHT) },
    fontFace: F, fontSize: opts.fontSize || 13, align: "center", valign: "middle" } })));
  s.addTable(data, { x: opts.x, y: opts.y, w: opts.w, colW: opts.colW, border: { type: "solid", pt: 0.5, color: "BFBFBF" }, rowH: opts.rowH || 0.4 });
}
function callout(s, big, label, x, y, color) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.9, h: 1.35, fill: { color: LIGHT }, line: { color: LIGHT } });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.08, h: 1.35, fill: { color }, line: { color } });
  s.addText(big, { x: x + 0.2, y: y + 0.1, w: 2.6, h: 0.7, fontFace: F, fontSize: 28, bold: true, color: INK, margin: 0 });
  s.addText(label, { x: x + 0.2, y: y + 0.8, w: 2.6, h: 0.5, fontFace: F, fontSize: 12, color: MUTED, margin: 0 });
}

// 1 ---------------------------------------------------------------- title
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText("Reproducing Spark-Based Bearing Fault Diagnosis with an Improved Random Forest", {
    x: 0.8, y: 1.6, w: 11.7, h: 1.8, fontFace: F, fontSize: 36, bold: true, color: "FFFFFF", margin: 0 });
  s.addText("Reproduction of Wan et al., IEEE Access 9 (2021) 37866–37882", { x: 0.8, y: 3.5, w: 11.7, h: 0.5, fontFace: F, fontSize: 20, color: "C9D6EA", margin: 0 });
  s.addText("AI508 Big Data Technologies and Applications – Assignment 2\n{{AUTHOR}} – {{STUDENT_ID}}  |  Dr. Ghada Alsuhli", {
    x: 0.8, y: 5.2, w: 11.7, h: 1.0, fontFace: F, fontSize: 16, color: "FFFFFF", margin: 0 });
  s.addNotes("Introduce the paper, the reason for choosing it (link to Assignment 1 on IoT predictive maintenance) and that this is a single-student reproduction with a reduced scope.");
}

// 2 ---------------------------------------------------------------- problem
{
  const s = base("The original research problem", "Explain the two problems the paper attacks: slow RF on massive data and redundant/weak trees. Then the two answers: IRF + Spark.");
  bullets(s, [
    "Bearing faults are detected from high-rate vibration signals – data volume grows fast",
    "Classic random forest on massive data: slow training and slow diagnosis",
    "Many trees are weak or vote the same way – computation without new information",
    "Proposal: Improved RF (IRF) keeps only accurate and mutually dissimilar trees",
    "Every stage parallelised on Apache Spark (cluster: 1 master + 4 workers)",
    "Paper's headline: 97.22% (IRF) vs 96.51% (Spark RF) with 200 trees; up to 73.26% shorter training with 4 workers",
  ], { w: 12.1 });
}

// 3 ---------------------------------------------------------------- IRF steps
{
  const s = base("The improved random forest in seven steps", "Walk through the boxes left to right. Stress that Steps 2-6 run after normal RF training and are the 'sub-forest optimisation'.");
  const steps = [["1", "Train RF", "k CART trees, bootstrap + random features"], ["2", "Filter", "drop trees with low validation accuracy → w trees"],
    ["3", "Paths", "extract every root-to-leaf path"], ["4", "Similarity", "w × w treeSim matrix (Eq. 1–3)"],
    ["5", "Group", "trees with treeSim > threshold form one class"], ["6", "Select", "best tree per class, not too similar to kept ones"], ["7", "Vote", "kept trees = IRF model"]];
  steps.forEach(([n, t, d], i) => {
    const x = 0.5 + i * 1.78;
    const col = i === 0 || i === 6 ? BLUE : GREEN;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.6, w: 1.62, h: 2.9, fill: { color: LIGHT }, line: { color: col, width: 1.5 } });
    s.addText(n, { x, y: 1.7, w: 1.62, h: 0.6, fontFace: F, fontSize: 26, bold: true, color: col, align: "center", margin: 0 });
    s.addText(t, { x, y: 2.35, w: 1.62, h: 0.5, fontFace: F, fontSize: 16, bold: true, color: INK, align: "center", margin: 0 });
    s.addText(d, { x: x + 0.08, y: 2.9, w: 1.46, h: 1.5, fontFace: F, fontSize: 12, color: MUTED, align: "center", valign: "top", margin: 0 });
  });
  s.addText("nodeSim = 1 if same feature and |nᵣ − nₛ| / nᵣ ≤ α (α = 0.2)     pathSim = matched nodes / φ × length     treeSim = Σ best pathSim / Σ path length", {
    x: 0.5, y: 4.9, w: 12.3, h: 0.6, fontFace: F, fontSize: 14, italic: true, color: INK, margin: 0 });
  s.addText("Two paths are compared only when their leaves give the same diagnosis; trees with dissimilar roots get similarity 0.", {
    x: 0.5, y: 5.5, w: 12.3, h: 0.5, fontFace: F, fontSize: 14, color: MUTED, margin: 0 });
}

// 4 ---------------------------------------------------------------- pipeline
{
  const s = base("Reproduction approach and Big Data pipeline", "Each box is a numbered script in the repository. Point out what runs in Spark and why the trees are exported via Parquet.");
  const boxes = [["CWRU .mat", "40 files, 10 classes × 4 loads"], ["Overlapping sampling", "Spark job → {{N_WINDOWS}} windows, {{RAW_GB}} GB"],
    ["Wavelet packet", "Spark mapInPandas, db4 level 3 → 8 energies"], ["Spark MLlib RF", "entropy, 6:2:2 split"], ["IRF Steps 2–7", "broadcast trees, row-parallel similarity"], ["Evaluation", "accuracy, F1, train / diagnosis time"]];
  boxes.forEach(([t, d], i) => {
    const x = 0.45 + i * 2.1;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.7, w: 1.85, h: 1.7, fill: { color: i === 4 ? "E3F5EE" : LIGHT }, line: { color: i === 4 ? GREEN : BLUE, width: 1.2 } });
    s.addText(t, { x, y: 1.8, w: 1.85, h: 0.6, fontFace: F, fontSize: 15, bold: true, color: INK, align: "center", margin: 2 });
    s.addText(d, { x: x + 0.05, y: 2.4, w: 1.75, h: 0.95, fontFace: F, fontSize: 12, color: MUTED, align: "center", valign: "top", margin: 0 });
    if (i < boxes.length - 1) s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: x + 1.9, y: 2.42, w: 0.15, h: 0.26, rotate: 90, fill: { color: MUTED }, line: { color: MUTED } });
  });
  bullets(s, [
    "Original code not published – every step re-implemented in PySpark from the paper",
    "MLlib trees exported from the saved Parquet node table; agreement with MLlib predictions: {{E1_AGREE}}%",
    "Kept trees rebuilt as a real MLlib model → Spark-RFA and Spark-IRFA diagnosed by the same engine",
    "Every setting runs in a fresh Spark JVM; data cached before timing",
  ], { y: 3.8, h: 3.0 });
}

// 5 ---------------------------------------------------------------- setup
{
  const s = base("Experimental setup: paper vs reproduction", "Emphasise the structural difference: cores of one machine replace worker nodes. List the assumptions you had to make.");
  table(s, [
    ["", "Original study", "This reproduction"],
    ["Hardware", "1 master + 4 workers (i7-9700K, 32 GB)", "1 GitHub Actions runner, {{ENV_CORES}} vCPUs, {{ENV_RAM}} GB"],
    ["Software", "CentOS 8.1, Hadoop 3.2, Spark 3.0, Python 3.7", "Ubuntu, Spark {{ENV_SPARK}} (local mode), Python {{ENV_PY}}"],
    ["Storage", "HDFS", "Parquet on local SSD"],
    ["Data", "5.6 / 11.2 / 20.4 GB", "{{RAW_GB}} GB (Dataset 1) + 1.4 / 2.8 GB subsets"],
    ["Parallelism", "1–4 worker nodes", "1, 2, 3, 4 executor cores (local[c])"],
    ["Unspecified → assumed", "–", "window 2,048; db4 level 3; depth 10; mean-accuracy filter; threshold {{IRF_THRESHOLD}}"],
  ], { x: 0.5, y: 1.35, w: 12.3, colW: [2.3, 4.5, 5.5], fontSize: 14, rowH: 0.62 });
  s.addText("Experiments: E1 accuracy (20/100/200 trees)  •  E2 scalability (1–4 cores)  •  E3 data size (1.4–5.6 GB)", {
    x: 0.5, y: 6.2, w: 12.3, h: 0.5, fontFace: F, fontSize: 15, bold: true, color: NAVY, margin: 0 });
}

// 6 ---------------------------------------------------------------- E1
{
  const s = base("E1 – Accuracy vs number of trees", "Read the solid lines (ours) against the dashed (paper). Then give the 200-tree comparison and how many trees the IRF kept.");
  fig(s, "e1_accuracy.png", 0.4, 1.2, 7.6, 3.8 / 6.4);
  callout(s, "{{E1_IRF_200_ACC}}%", "Spark-IRFA, 200 trees (paper 97.22%)", 8.4, 1.3, GREEN);
  callout(s, "{{E1_RF_200_ACC}}%", "Spark-RFA, 200 trees (paper 96.51%)", 8.4, 2.85, ORANGE);
  callout(s, "{{E1_IRF_200_NTREES}} / 200", "trees kept by the IRF", 8.4, 4.4, BLUE);
  s.addText("IRF vs Spark RF at 200 trees: {{E1_D_IRF_RF_200}} pp (paper +0.71 pp)  •  Python-RFA {{E1_PY_200_ACC}}%", {
    x: 0.5, y: 6.2, w: 12.3, h: 0.5, fontFace: F, fontSize: 15, color: INK, margin: 0 });
}

// 7 ---------------------------------------------------------------- E1 timing + threshold
{
  const s = base("E1 – Diagnosis time and the similarity threshold", "Smaller forest = faster diagnosis. The threshold sweep shows the IRF size depends on a parameter the paper does not report.");
  fig(s, "e1_threshold_sweep.png", 0.4, 1.3, 6.6, 3.6 / 6.4);
  table(s, [
    ["Trees", "Diag. Spark-RF (s)", "Diag. Spark-IRF (s)", "Reduction"],
    ["20", "{{E1_RF_20_DIAG}}", "{{E1_IRF_20_DIAG}}", "{{E1_DIAGRED_20}}%"],
    ["100", "{{E1_RF_100_DIAG}}", "{{E1_IRF_100_DIAG}}", "{{E1_DIAGRED_100}}%"],
    ["200", "{{E1_RF_200_DIAG}}", "{{E1_IRF_200_DIAG}}", "{{E1_DIAGRED_200}}%"],
  ], { x: 7.3, y: 1.5, w: 5.6, colW: [0.9, 1.6, 1.6, 1.5], fontSize: 13, rowH: 0.5 });
  bullets(s, [
    "Paper: −74.29% diagnosis time on Dataset 1",
    "Optimisation cost (100 trees): {{E1_IRF_100_OPT}} s, similarity {{E1_IRF_100_SIM}} s",
    "{{E1_SIM_ZERO_FRAC_100}}% of tree pairs have similarity 0 (dissimilar roots)",
  ], { x: 7.3, y: 4.3, w: 5.7, h: 2.4 });
}

// 8 ---------------------------------------------------------------- E2
{
  const s = base("E2 – Scalability: cores as a proxy for worker nodes", "Compare the green line (ours, cores) with the grey (paper, nodes). Explain why only the trend is comparable.");
  fig(s, "e2_reduction_vs_paper.png", 0.4, 1.2, 7.6, 3.8 / 6.4);
  table(s, [
    ["Cores", "Train IRF (s)", "Reduction", "Speed-up"],
    ["1", "{{E2_IRF_TRAIN_1}}", "{{E2_RED_1}}%", "{{E2_SPEEDUP_1}}"],
    ["2", "{{E2_IRF_TRAIN_2}}", "{{E2_RED_2}}%", "{{E2_SPEEDUP_2}}"],
    ["3", "{{E2_IRF_TRAIN_3}}", "{{E2_RED_3}}%", "{{E2_SPEEDUP_3}}"],
    ["4", "{{E2_IRF_TRAIN_4}}", "{{E2_RED_4}}%", "{{E2_SPEEDUP_4}}"],
  ], { x: 8.3, y: 1.4, w: 4.6, colW: [0.9, 1.3, 1.2, 1.2], fontSize: 13, rowH: 0.48 });
  bullets(s, [
    "Paper: −51.5 / −66.1 / −73.3% with 2 / 3 / 4 nodes",
    "IRF training costs {{E2_OVERHEAD_MAX}}% more than Spark RF (paper +85.98%)",
  ], { x: 8.3, y: 4.3, w: 4.7, h: 2.3 });
}

// 9 ---------------------------------------------------------------- E3
{
  const s = base("E3 – Effect of data size", "Accuracy trend vs size, and roughly linear growth of training time. Mention that overlapping windows add volume but little new information.");
  fig(s, "e3_datasize.png", 0.5, 1.3, 12.3, 3.5 / 8.6);
  s.addText("Spark-IRFA accuracy {{E3_TREND}} from 1.4 to 5.6 GB ({{E3_DIFF}} pp); paper: +1.03 pp from 5.6 to 20.4 GB. At 5.6 GB our IRF differs from the paper by {{E3_GAP_56}} pp.", {
    x: 0.5, y: 6.25, w: 12.3, h: 0.6, fontFace: F, fontSize: 15, color: INK, margin: 0 });
}

// 10 --------------------------------------------------------------- verdicts
{
  const s = base("Comparison with the original study", "Go claim by claim. Be explicit about which claims hold and which do not.");
  table(s, [
    ["Claim", "Paper", "Ours", "Verdict"],
    ["IRF more accurate than Spark RF (200 trees)", "+0.71 pp", "{{E1_D_IRF_RF_200}} pp", "{{V_A}}"],
    ["Accuracy level (200 trees)", "96.4–97.2%", "{{E1_PY_200_ACC}} / {{E1_RF_200_ACC}} / {{E1_IRF_200_ACC}}%", "{{V_B}}"],
    ["Training time falls with more resources", "−73.26%", "−{{E2_RED_MAX}}% ({{E2_MAXC}} cores)", "{{V_C}}"],
    ["IRF diagnoses faster than Spark RF", "−74.29%", "−{{E1_DIAGRED_100}}%", "{{V_D}}"],
    ["IRF training costs more", "+85.98%", "+{{E2_OVERHEAD_MAX}}%", "{{V_E}}"],
    ["Accuracy rises with data size", "+1.03 pp", "{{E3_DIFF}} pp", "{{V_F}}"],
  ], { x: 0.5, y: 1.35, w: 12.3, colW: [4.4, 1.8, 3.1, 3.0], fontSize: 14, rowH: 0.62 });
}

// 11 --------------------------------------------------------------- differences
{
  const s = base("Why the results differ", "These are the causes you must be able to defend in the viva.");
  bullets(s, [
    "Unspecified settings: window length, overlap, wavelet, depth, filter rule, similarity threshold",
    "Eq. (2) and Algorithm 1 disagree; we implemented Eq. (2) literally",
    "MLlib votes by averaging probabilities; paper describes majority voting",
    "Cores ≠ nodes: shared memory bus and cache, no network or HDFS overhead",
    "Accuracy ceiling: all forests > 99.7% → no room for the paper's +0.71 pp IRF gain",
    "Leakage tested (E1b, time-blocked split): Spark RF still {{B_RF_200_ACC}}% → not caused by overlap",
    "Likely an easier task: 10 classes, 12 kHz drive end only (paper's Table 1 differs)",
    "Paper's own summary ratios (6.84×, 3.55×) do not match its measured times (≈7.84×, ≈4.5×)",
  ]);
}

// 12 --------------------------------------------------------------- limitations
{
  const s = base("Challenges and limitations", "Mention concrete engineering problems you solved and what remains out of scope.");
  bullets(s, [
    "Challenges",
    "- No published code: IRF rebuilt from prose and equations",
    "- No Python access to MLlib tree internals: solved with the Parquet node table + verification",
    "- Limited RAM/disk of one runner: binary window storage, Arrow batches",
    "- Similarity matrix cost: vectorised NumPy, one Spark task per row",
    "Limitations",
    "- Only Dataset 1 (5.6 GB); no real multi-node cluster",
    "- {{NSEEDS}} seed(s) per setting; cloud timings depend on background load",
    "- Near-perfect accuracy leaves little room to compare the methods",
  ]);
}

// 13 --------------------------------------------------------------- conclusion
{
  const s = base("Key findings and lessons", "Close with the three findings and the lesson about missing information in papers. Then invite questions.");
  callout(s, "{{E1_IRF_200_ACC}}%", "IRF accuracy, 200 trees", 0.6, 1.4, GREEN);
  callout(s, "−{{E1_DIAGRED_100}}%", "diagnosis time vs Spark RF", 3.7, 1.4, BLUE);
  callout(s, "−{{E2_RED_MAX}}%", "training time, 1 → {{E2_MAXC}} cores", 6.8, 1.4, ORANGE);
  bullets(s, [
    "{{V_COUNT}} of 6 claims reproduced: faster diagnosis, extra training cost, scalability with cores",
    "IRF accuracy gain not observable: every forest > 99.7% (also with a time-blocked split)",
    "Reproducible in method, only partly in numbers: missing settings, inconsistent equations, no code",
    "Our repository fixes every setting and seed and regenerates all tables and figures from raw CSVs",
    "Next step: real cluster and a harder task (e.g. train on some loads, test on others)",
  ], { y: 3.1, h: 3.6 });
  s.addText("Code and results: {{GITHUB_URL}}", { x: 0.6, y: 6.5, w: 12, h: 0.4, fontFace: F, fontSize: 13, color: BLUE, margin: 0 });
}

pres.writeFile({ fileName: path.join(HERE, "..", "presentation_template.pptx") }).then((f) => console.log("wrote", f));
