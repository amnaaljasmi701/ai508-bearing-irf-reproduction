// Builds report/report_template.docx. {{TOKENS}} are filled from results/ by scripts/08_build_report.py.
// Run:  node report/template_src/build_report_template.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, ImageRun, FootnoteReferenceRun, ExternalHyperlink,
  LevelFormat, PageNumber, Footer, TableOfContents,
} = require("docx");

const HERE = __dirname;
const FONT = "Calibri";
const PAGE_W = 11906, MARGIN = 1300, CONTENT_W = PAGE_W - 2 * MARGIN;   // A4

// ------------------------------------------------------------------ footnotes
const W1 = 'Wan, Lanjun; Kun Gong; Gen Zhang; Xinpan Yuan; Changyun Li; and Xiaojun Deng, "An Efficient Rolling Bearing Fault Diagnosis Method Based on Spark and Improved Random Forest Algorithm", ';
const WS = 'Wan et al., "An Efficient Rolling Bearing Fault Diagnosis Method", ';
const DOI_W = "https://doi.org/10.1109/ACCESS.2021.3063929";
const FN = {};
let fnCount = 0;
function fn(parts) {             // parts: array of [text, style] or {link}
  fnCount += 1;
  FN[fnCount] = { children: [new Paragraph({ children: parts.map(runFromPart(18)) })] };
  return fnCount;
}
function runFromPart(size) {
  return (p) => {
    if (typeof p === "string") return new TextRun({ text: p, font: FONT, size });
    if (p.link) return new ExternalHyperlink({ link: p.link, children: [new TextRun({ text: p.link, style: "Hyperlink", font: FONT, size })] });
    return new TextRun({ text: p.t, italics: !!p.i, bold: !!p.b, font: FONT, size });
  };
}
const fnWanFull = (page) => fn([W1, { t: "IEEE Access", i: true }, ` vol. 9 (2021), p. ${page}. Available at: `, { link: DOI_W }, "."]);
const fnWan = (page) => fn([WS, { t: "IEEE Access", i: true }, `, p. ${page}.`]);

// ------------------------------------------------------------------ text helpers
// Inline markup: *italic*, **bold**, [[fn]] markers are passed as numbers in arrays.
function runs(text, size = 22) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, size }));
    const s = m[0];
    if (s.startsWith("**")) out.push(new TextRun({ text: s.slice(2, -2), bold: true, font: FONT, size }));
    else out.push(new TextRun({ text: s.slice(1, -1), italics: true, font: FONT, size }));
    last = m.index + s.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size }));
  return out;
}
function P(...items) {           // strings and footnote numbers
  const children = [];
  for (const it of items) {
    if (typeof it === "number") children.push(new FootnoteReferenceRun(it));
    else children.push(...runs(it));
  }
  return new Paragraph({ children, spacing: { after: 120, line: 288 }, alignment: AlignmentType.JUSTIFIED });
}
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });
const EQ = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 100 },
  children: [new TextRun({ text: t, font: "Cambria Math", size: 21, italics: true })] });
const BUL = (t) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 276 }, children: runs(t) });
const CAP = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 },
  children: [new TextRun({ text: t, font: FONT, size: 19, italics: true, color: "404040" })] });
const TCAP = (t) => new Paragraph({ keepNext: true, spacing: { before: 160, after: 80 },
  children: [new TextRun({ text: t, font: FONT, size: 20, bold: true })] });

// ------------------------------------------------------------------ tables
const border = { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" };
const borders = { top: border, bottom: border, left: border, right: border };
function T(header, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cols = widths.map((w) => Math.round((w / total) * CONTENT_W));
  cols[cols.length - 1] = CONTENT_W - cols.slice(0, -1).reduce((a, b) => a + b, 0);
  const cell = (text, i, head) => new TableCell({
    borders, width: { size: cols[i], type: WidthType.DXA },
    shading: head ? { fill: "DCE6F2", type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
      children: [new TextRun({ text: String(text), font: FONT, size: 18, bold: head })] })],
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: cols,
    rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, i, false)) }))],
  });
}

// ------------------------------------------------------------------ figures
function FIG(name, widthIn) {
  const file = path.join(HERE, "placeholders", name);
  const sizes = { "e1_accuracy.png": [6.4, 3.8], "e1_diagnosis_time.png": [6.4, 3.6], "e1_threshold_sweep.png": [6.4, 3.6],
    "e2_training_time.png": [6.4, 3.8], "e2_reduction_vs_paper.png": [6.4, 3.8], "e3_datasize.png": [8.6, 3.5] };
  const [w, h] = sizes[name];
  const wpx = Math.round(widthIn * 96), hpx = Math.round((widthIn * 96 * h) / w);
  return new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, children: [new ImageRun({
    type: "png", data: fs.readFileSync(file), transformation: { width: wpx, height: hpx },
    altText: { title: name, description: `FIG:${name}`, name: name } })] });
}

// ================================================================== CONTENT
const c = [];

// ---------------- title page block
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600, after: 120 },
  children: [new TextRun({ text: "AI508 Big Data Technologies and Applications – Assignment 2", font: FONT, size: 22, color: "404040" })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Reproducing Spark-Based Rolling-Bearing Fault Diagnosis with an Improved Random Forest: A Single-Machine Reproduction of Wan et al. (2021)", font: FONT, size: 34, bold: true })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: "{{AUTHOR}} – ID: {{STUDENT_ID}} | Single-student team", font: FONT, size: 22 })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: "Module Coordinator: Dr. Ghada Alsuhli", font: FONT, size: 22 })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 },
  children: [new TextRun({ text: "Repository: ", font: FONT, size: 22 }),
    new ExternalHyperlink({ link: "{{GITHUB_URL}}", children: [new TextRun({ text: "{{GITHUB_URL}}", style: "Hyperlink", font: FONT, size: 22 })] })] }));

// ---------------- abstract
c.push(H1("Abstract"));
c.push(P(
  "Wan et al. (2021) proposed an improved random forest (IRF) for rolling-bearing fault diagnosis that removes low-accuracy trees and trees that vote redundantly, and parallelised the whole method on Apache Spark. On a five-node cluster they reported 97.22% accuracy with 200 trees against 96.51% for the standard Spark random forest, training-time reductions of up to 73.26% with four worker nodes, and a much shorter diagnosis time. This report reproduces three parts of that study on a single machine, a four-core GitHub Actions runner. The Case Western Reserve University (CWRU) vibration signals were enlarged by overlapping sampling to a {{RAW_GB}} GB dataset of {{N_WINDOWS}} windows, wavelet-packet features were extracted with Spark, and the IRF steps (tree filtering, path extraction, tree-similarity matrix and tree selection) were re-implemented in PySpark because the original code is not published. With 200 trees our Spark-IRFA reached {{E1_IRF_200_ACC}}% test accuracy, {{E1_VERDICT_200}} Spark-RFA ({{E1_RF_200_ACC}}%), while keeping {{E1_IRF_200_NTREES}} of the 200 trees. Increasing Spark executor cores from 1 to {{E2_MAXC}}, used as a proxy for worker nodes, reduced Spark-IRFA training time by {{E2_RED_MAX}}%, and the smaller forest cut diagnosis time by {{E1_DIAGRED_100}}% at 100 trees. Exact values differ from the paper because the paper leaves the wavelet settings, tree depth and similarity threshold unspecified, and because one machine is not a cluster. The study is therefore only partially reproducible from its text alone."));

// ---------------- 1 introduction
c.push(H1("1. Introduction"));
c.push(P(
  "Rolling bearings are among the most failure-prone components of rotating machines, and vibration monitoring is the usual way to detect their faults early. Modern condition-monitoring systems sample accelerometers at kilohertz rates on many machines at once, so the data quickly reach a volume at which a single-threaded classifier becomes slow both to train and to apply. This is the setting addressed by the selected study, and it connects to my first assignment, a systematic literature review of drift-aware streaming analytics for IoT anomaly detection and predictive maintenance, in which scalable fault classifiers were a recurring building block."));
c.push(P(
  "The selected paper is Wan et al., “An Efficient Rolling Bearing Fault Diagnosis Method Based on Spark and Improved Random Forest Algorithm”, published in ", "*IEEE Access*", " (Q2) in 2021", fnWanFull(37866), ". It addresses two weaknesses of the classic random forest (RF) of Breiman", fn(['Breiman, Leo, "Random Forests", ', { t: "Machine Learning", i: true }, " vol. 45, no. 1 (2001), p. 5. Available at: ", { link: "https://doi.org/10.1023/A:1010933404324" }, "."]),
  " when it is used on large vibration datasets: training and diagnosis are slow, and many trees are weak or cast near-identical votes. The authors propose an improved random forest that keeps only accurate and mutually dissimilar trees, and they distribute every stage of the method on Apache Spark."));
c.push(P(
  "The objective of this assignment is to reproduce the methodology and selected experiments of the paper, compare the results with the original ones, and explain the differences. Because I worked alone, the scope agreed in the proposal is reduced to three experiments on the smallest of the paper's three datasets: E1 compares the accuracy of a serial scikit-learn RF, Spark MLlib RF and the Spark IRF with 20, 100 and 200 trees; E2 measures training and diagnosis time as the number of Spark executor cores grows from 1 to 4, as a single-machine stand-in for the paper's one to four worker nodes; and E3 measures accuracy and training time on 1.4, 2.8 and 5.6 GB subsets. All numbers in Sections 4 and 5 were produced by the scripts in the project repository, executed by the repository's GitHub Actions workflow; the values attributed to the paper are labelled as such."));

// ---------------- 2 original study
c.push(H1("2. The Original Study"));
c.push(H2("2.1 Research problem and contribution"));
c.push(P(
  "The paper observes that a standard random forest trained on massive bearing data contains trees whose individual accuracy is low and groups of trees that are structurally alike, so they vote the same way and add computation without adding information. Removing both kinds of tree should give a smaller forest that diagnoses faster and, ideally, at least as accurately. The second contribution is engineering: every expensive stage, from training to computing tree similarities, is expressed as Spark RDD operations so that it scales with the number of worker nodes."));
c.push(H2("2.2 Dataset and preprocessing"));
c.push(P(
  "The authors use the public CWRU bearing dataset, which contains drive-end and fan-end accelerometer signals sampled at 12 kHz and 48 kHz for a healthy bearing and for inner-race, ball and outer-race faults of several sizes under motor loads of 0–3 hp. A widely used benchmark study by Smith and Randall describes this dataset and its pitfalls", fn(['Smith, Wade A.; and Robert B. Randall, "Rolling Element Bearing Diagnostics Using the Case Western Reserve University Data: A Benchmark Study", ', { t: "Mechanical Systems and Signal Processing", i: true }, " vol. 64–65 (2015), pp. 100–101. Available at: ", { link: "https://doi.org/10.1016/j.ymssp.2015.04.021" }, "."]),
  ". To obtain big data, the paper enlarges the signals by overlapping sampling: consecutive windows share most of their samples, so the number of windows can be multiplied without new measurements. Three datasets of 5.6, 11.2 and 20.4 GB were produced, each window was standardised and decomposed by the wavelet packet transform, and the resulting feature vectors were stored in HDFS", fnWan(37874), ". The paper does not state the sample length, the overlap step, the wavelet basis, the decomposition level or the exact list of working conditions (its Table 1 is the only source of the latter)."));
c.push(H2("2.3 The improved random forest"));
c.push(P(
  "The IRF is built in seven steps", fnWan(37869), ". Step 1 trains an ordinary RF of k CART trees on bootstrap samples with random feature subspaces. Step 2 scores every tree on a validation set and discards the low-accuracy ones, leaving a sub-forest of w trees. Step 3 extracts every root-to-leaf path of these trees; the leaf of a path is a diagnosis and its length is the number of nodes. Step 4 computes a w × w tree-similarity matrix from three nested measures", fnWan(37870), ":"));
c.push(EQ("nodeSim(r, s) = 1  if feature(r) = feature(s) and |n_r − n_s| / n_r ≤ α,  otherwise 0          (1)"));
c.push(EQ("pathSim(i, j) = [1 + Σ_{m=2..φ−1} nodeSim(i.m, j.m) + 1] / φ × pathLength_i,   φ = min(pathLength_i, pathLength_j)          (2)"));
c.push(EQ("treeSim(a, b) = Σ_i pathMaxSim_i / Σ_i pathLength_i          (3)"));
c.push(P(
  "Here n is the split value of a node, α is a tolerance that the authors set to about 0.2, two paths are compared only if their leaves give the same diagnosis, pathMaxSim_i is the best match of path i of tree a among all paths of tree b, and the similarity of two trees is zero when their roots are not similar", fnWan(37871), ". Step 5 walks through the matrix row by row and places in one class every not-yet-classified tree whose similarity to the current tree exceeds the threshold similarityFilter. Step 6 keeps the most accurate tree of each class, unless it is too similar to a tree already kept, in which case the next most accurate tree is tried. Step 7 uses the kept trees as the final model, which votes like an ordinary RF."));
c.push(H2("2.4 Spark parallelisation"));
c.push(P(
  "The feature vectors are read from HDFS into an RDD and split 6:2:2 into training, validation and test RDDs. Bootstrap sampling and tree training run in parallel, validation scoring of the trees and path extraction are map operations followed by a collect, and the similarity matrix is filled row by row: for each row the pairs of trees are distributed to the workers and the results are collected", fnWan(37872), ". The authors compare four ways of distributing the similarity computation and choose the row-wise variant (Method D) because the alternatives create too many RDDs or use too much memory."));
c.push(H2("2.5 Experiments and key findings"));
c.push(P(
  "Experiments ran on one master and four workers (eight-core Intel i7-9700K, 32 GB each) with CentOS 8.1, Hadoop 3.2, Spark 3.0 and Python 3.7", fnWan(37874), ". The trees used entropy impurity, 100 trees in most comparisons and a sweep from 20 to 200 trees. Table 1 lists the results that this reproduction targets."));
c.push(TCAP("Table 1. Results reported by the original paper (not produced by this reproduction)."));
c.push(T(["Claim", "Reported value", "Page"], [
  ["Accuracy with 20 trees (Python-RFA / Spark-RFA / Spark-IRFA)", "95.85% / 95.69% / 95.66%", "37875"],
  ["Accuracy with 200 trees (Python-RFA / Spark-RFA / Spark-IRFA)", "96.43% / 96.51% / 97.22%", "37875"],
  ["Spark-IRFA accuracy, 100 trees, 5.6 / 11.2 / 20.4 GB", "97.09% / 97.38% / 98.12%", "37876"],
  ["Spark-IRFA training-time reduction with 2 / 3 / 4 workers vs 1", "51.48% / 66.08% / 73.26%", "37876"],
  ["Spark-IRFA diagnosis-time reduction vs Spark-RFA (datasets 1–3)", "74.29% / 76.00% / 78.01%", "37878"],
  ["Diagnosis time on 20.4 GB: Python-RFA vs Spark-IRFA", "24.3 min vs 3.1 min", "37878"],
  ["Training overhead of Spark-IRFA over Spark-RFA (4 workers, dataset 1)", "+85.98%", "37876"],
], [4.2, 2.6, 0.8]));
c.push(P(
  "The conclusion states that Spark-IRFA diagnoses 6.84 times faster than Python-RFA and 3.55 times faster than Spark-RFA", fnWan(37880),
  ". These ratios do not follow from the reported times: 24.3 / 3.1 gives about 7.84, and a 78.01% reduction corresponds to about 4.5 times. This internal inconsistency is one of the reproducibility issues discussed in Section 5."));

// ---------------- 3 methodology
c.push(H1("3. Reproduction Methodology"));
c.push(H2("3.1 Scope"));
c.push(P(
  "The reproduction covers the full pipeline (data enlargement, feature extraction, Spark RF, IRF construction and evaluation) on Dataset 1 only. The 11.2 and 20.4 GB datasets, the noise and imbalance experiments and the deep-learning comparison of the paper are out of scope. Since no cluster was available, Spark ran in local mode, where local[c] gives one JVM with c parallel task slots; this replaces worker nodes in E2 and is the main structural deviation from the original setup."));
c.push(H2("3.2 Dataset and preprocessing"));
c.push(P(
  "Forty CWRU files were downloaded from the Bearing Data Center: ten health states (normal; inner-race, ball and outer-race faults of 0.007, 0.014 and 0.021 inch, outer race at the 6 o'clock position) under the four motor loads, using the 12 kHz drive-end signal. Their lengths range from {{SIG_MIN}} to {{SIG_MAX}} samples. A Spark job cut every signal into {{WPF}} overlapping windows of 2,048 samples with evenly spaced start points, so that every file, and therefore every class, contributes the same number of windows. This gives {{N_WINDOWS}} windows, or {{RAW_GB}} GB when stored as 64-bit floats, the size of the paper's Dataset 1; the windows were written to Parquet ({{PARQUET_GB}} GB on disk) in {{GEN_S}} s. The smallest step between windows is {{MIN_STEP}} samples, an overlap of up to {{OVERLAP_PCT}}%."));
c.push(P(
  "A second Spark job read the windows, standardised each one to zero mean and unit variance, applied a three-level wavelet packet decomposition with the Daubechies-4 wavelet (periodisation mode, implemented with PyWavelets", fn(['Lee, Gregory R.; Ralf Gommers; Filip Waselewski; Kai Wohlfahrt; and Aaron O’Leary, "PyWavelets: A Python Package for Wavelet Analysis", ', { t: "Journal of Open Source Software", i: true }, " vol. 4, no. 36 (2019), p. 1237. Available at: ", { link: "https://doi.org/10.21105/joss.01237" }, "."]),
  ") and kept the relative energy of the {{N_FEATURES}} terminal nodes as the feature vector. The job took {{FEAT_S}} s. Rows were assigned to training, validation and test sets in the paper's 6:2:2 ratio by hashing the window identifier with a fixed seed, which gave {{N_TRAIN}}, {{N_VAL}} and {{N_TEST}} rows. The hash-based split guarantees that scikit-learn and Spark see exactly the same rows."));
c.push(H2("3.3 Computing environment"));
c.push(TCAP("Table 2. Computing environment of the original study and of this reproduction."));
c.push(T(["Item", "Original study", "This reproduction"], [
  ["Hardware", "1 master (Xeon E3-1225 v5, 32 GB) + 4 workers (i7-9700K, 8 cores, 32 GB)", "1 GitHub-hosted runner (virtual machine): {{ENV_CPU}}, {{ENV_CORES}} vCPUs, {{ENV_RAM}} GB RAM, SSD"],
  ["Operating system", "CentOS 8.1", "Ubuntu Linux ({{ENV_OS}})"],
  ["Big Data framework", "Hadoop 3.2 (HDFS), Spark 3.0 standalone cluster", "Spark {{ENV_SPARK}} local mode, Parquet on local disk, driver memory {{ENV_DRIVER_MEM}}"],
  ["Language and libraries", "Python 3.7", "Python {{ENV_PY}}, {{ENV_JAVA}}, NumPy {{ENV_NUMPY}}, pandas {{ENV_PANDAS}}, PyArrow {{ENV_PYARROW}}, PyWavelets {{ENV_PYWT}}, scikit-learn {{ENV_SKLEARN}}"],
], [1.6, 2.6, 3.4]));
c.push(H2("3.4 Implementation"));
c.push(P(
  "The original code is not published, so every step was implemented from the paper's description. The repository is organised as a Python package (src/irf_repro) and numbered scripts that run the pipeline end to end; configuration is kept in one YAML file. Spark", fn(['Zaharia, Matei et al., "Apache Spark: A Unified Engine for Big Data Processing", ', { t: "Communications of the ACM", i: true }, " vol. 59, no. 11 (2016), p. 56. Available at: ", { link: "https://doi.org/10.1145/2934664" }, "."]),
  " carries out all data-parallel work: generating windows, extracting features, training the forest through MLlib", fn(['Meng, Xiangrui et al., "MLlib: Machine Learning in Apache Spark", ', { t: "Journal of Machine Learning Research", i: true }, " vol. 17, no. 34 (2016), p. 1. Available at: ", { link: "https://jmlr.org/papers/v17/15-237.html" }, "."]),
  ", scoring trees, extracting paths, computing the similarity matrix and diagnosing the test set. The serial baseline uses scikit-learn", fn(['Pedregosa, Fabian et al., "Scikit-learn: Machine Learning in Python", ', { t: "Journal of Machine Learning Research", i: true }, " vol. 12 (2011), p. 2825. Available at: ", { link: "https://jmlr.org/papers/v12/pedregosa11a.html" }, "."]),
  " with n_jobs = 1, matching the paper's single-machine Python-RFA."));
c.push(P(
  "**Exporting the trees.** MLlib does not expose tree internals to Python, so the trained forest is saved and its Parquet node table (tree identifier, node identifier, prediction, children, split feature and threshold) is read back and converted into flat NumPy arrays per tree. A sample is sent to the left child when its feature value is at most the threshold, which is MLlib's rule for continuous features. To verify the conversion, the predictions of the exported trees were compared with MLlib's own per-tree predictions on 2,000 validation rows; the agreement was {{E1_AGREE}}%."));
c.push(P(
  "**Steps 2–7.** The flat trees are broadcast to the executors, and every partition of the validation set computes the number of correct predictions of every tree; a groupBy sums the counts (Step 2). Trees whose validation accuracy is at least the mean accuracy form the sub-forest, an explicit rule chosen because the paper does not give a numeric criterion. Path extraction runs as a map over the sub-forest (Step 3). For Step 4 the paths are broadcast and one Spark task computes one row of the matrix, i.e. treeSim(a, b) for all b; Equations (1)–(3) are vectorised with NumPy over all path pairs of two trees. Computing all rows in one job rather than launching one job per row, as in Method D, gives the same matrix with less scheduling overhead. Because treeSim is not symmetric, two trees are treated as too similar in Step 6 when either direction exceeds the threshold. The kept trees are finally rebuilt into a genuine MLlib RandomForestClassificationModel through the JVM, so that Spark-IRFA and Spark-RFA are diagnosed by the same engine and their diagnosis times differ only because of the number of trees."));
c.push(P(
  "**Timing.** All data sets are cached and counted before timing starts, so that reading Parquet is not part of training time. Training time of Spark-RFA is the duration of MLlib's fit; training time of Spark-IRFA is the same fit plus the sub-forest optimisation (export, filtering, paths, similarity and selection), which follows the paper's accounting. Diagnosis time is the time needed to predict the whole test set and compute its accuracy. Every setting runs in a fresh Spark JVM so that caches from earlier runs cannot affect timings."));
c.push(H2("3.5 Settings and assumptions"));
c.push(TCAP("Table 3. Parameter settings; entries marked “assumption” are not specified in the paper."));
c.push(T(["Parameter", "Value used", "Source"], [
  ["Working conditions", "10 classes × 4 loads, 12 kHz drive end", "assumption (paper Table 1 not reproducible)"],
  ["Window length / windows per file", "2,048 / {{WPF}}", "assumption"],
  ["Wavelet packet", "db4, 3 levels, relative energy of 8 nodes", "assumption"],
  ["Split (train / validation / test)", "6 : 2 : 2", "paper"],
  ["Impurity / feature subset", "entropy / √8 → 3 features per split", "paper / MLlib default"],
  ["Maximum depth / bins", "10 / 32", "assumption"],
  ["Low-accuracy filter", "keep trees with validation accuracy ≥ mean", "assumption"],
  ["α (node similarity tolerance)", "0.2", "paper"],
  ["similarityFilter threshold", "{{IRF_THRESHOLD}}", "paper range 0.5–0.9; low end, as the paper recommends for vibration data"],
  ["Random seeds", "42 (number of seeds: {{NSEEDS}})", "this study"],
], [2.3, 2.6, 2.7]));
c.push(H2("3.6 Experiments and evaluation measures"));
c.push(BUL("**E1 – accuracy.** Python-RFA, Spark-RFA and Spark-IRFA with 20, 100 and 200 trees on the full dataset, using all cores. Measures: test accuracy, weighted F1, training and diagnosis time, and the number of trees kept by the IRF. A sweep of similarityFilter from 0.3 to 0.9 reuses the similarity matrix of each run."));
c.push(BUL("**E2 – scalability.** Spark-RFA and Spark-IRFA with 100 trees and 1, 2, 3 and 4 executor cores, matching the paper's 1–4 worker nodes. Measures: training time, its reduction relative to one core, speed-up and diagnosis time."));
c.push(BUL("**E3 – data size.** Spark-RFA and Spark-IRFA with 100 trees on nested random subsets of 25%, 50% and 100% of the windows (about 1.4, 2.8 and 5.6 GB). Measures: accuracy and training time."));

c.push(H2("3.7 Discrepancies between the original and the reproduced setup"));
c.push(P("Table 4 lists every known difference between the experimental setup of the paper and ours, why it exists, and its expected effect on the comparison."));
c.push(TCAP("Table 4. Discrepancies between the original study and this reproduction."));
c.push(T(["Aspect", "Original study", "This reproduction", "Reason", "Expected effect"], [
  ["Compute platform", "5-node cluster (1 master, 4 workers)", "1 machine, Spark local mode", "no cluster available", "absolute times not comparable; only trends"],
  ["Parallel units in E2", "1–4 worker nodes (8 cores each)", "1–4 executor cores (vCPUs)", "single machine", "earlier flattening of speed-up; no network cost"],
  ["Storage", "HDFS", "Parquet on local disk", "no cluster", "no replication or network I/O"],
  ["Software versions", "Spark 3.0, Hadoop 3.2, Python 3.7", "Spark {{ENV_SPARK}}, Python {{ENV_PY}}, no Hadoop", "current stable versions", "minor; same MLlib algorithm"],
  ["Datasets", "5.6, 11.2, 20.4 GB", "5.6 GB and nested 1.4 / 2.8 GB subsets", "single-student scope, memory", "E3 covers a smaller size range"],
  ["Working conditions", "Table 1 of the paper", "10 classes × 4 loads, 12 kHz drive end", "class list not reproducible from text", "different difficulty of the task"],
  ["Window, overlap, wavelet", "not specified", "2,048 samples; even spacing; db4, 3 levels", "not specified", "different features and accuracy"],
  ["Tree depth, filter rule, threshold", "described qualitatively", "depth 10; mean-accuracy filter; 0.5", "not specified", "different IRF size"],
  ["IRF voting", "majority voting", "MLlib probability averaging (sub-model)", "same engine for fair timing", "small accuracy differences"],
  ["Similarity computation", "Method D, one job per row", "all rows in one Spark job", "less scheduling overhead", "same matrix, lower overhead"],
  ["Repetitions", "single runs", "{{NSEEDS}} seed(s) per setting", "time limits", "random variation not quantified"],
], [1.4, 1.5, 1.6, 1.4, 1.7]));

// ---------------- 4 results
c.push(H1("4. Results and Comparison"));
c.push(P("All values below come from the files in the results folder of the repository; times are in seconds and are means over {{NSEEDS}} seed(s)."));
c.push(H2("4.1 E1 – Accuracy against the number of trees"));
c.push(TCAP("Table 5. Test accuracy (%) of the three methods; paper values in the last column."));
c.push(T(["Trees", "Python-RFA (ours)", "Spark-RFA (ours)", "Spark-IRFA (ours)", "IRF trees kept", "Paper (Py / Spark / IRF)"], [
  ["20", "{{E1_PY_20_ACC}}", "{{E1_RF_20_ACC}}", "{{E1_IRF_20_ACC}}", "{{E1_IRF_20_NTREES}} of 20", "95.85 / 95.69 / 95.66"],
  ["100", "{{E1_PY_100_ACC}}", "{{E1_RF_100_ACC}}", "{{E1_IRF_100_ACC}}", "{{E1_IRF_100_NTREES}} of 100", "not reported"],
  ["200", "{{E1_PY_200_ACC}}", "{{E1_RF_200_ACC}}", "{{E1_IRF_200_ACC}}", "{{E1_IRF_200_NTREES}} of 200", "96.43 / 96.51 / 97.22"],
], [0.8, 1.3, 1.3, 1.3, 1.3, 2.0]));
c.push(FIG("e1_accuracy.png", 4.9));
c.push(CAP("Figure 1. E1 accuracy of our three implementations (solid) and the values reported by the paper (dashed; the paper gives exact values only for 20 and 200 trees)."));
c.push(P(
  "With 200 trees, Spark-IRFA reached {{E1_IRF_200_ACC}}%, which is {{E1_VERDICT_200}} Spark-RFA ({{E1_D_IRF_RF_200}} percentage points); at 100 and 20 trees it was {{E1_VERDICT_100}} and {{E1_VERDICT_20}} Spark-RFA respectively ({{E1_D_IRF_RF_100}} and {{E1_D_IRF_RF_20}} pp). Spark-IRFA was more accurate than Spark-RFA in {{E1_IRF_WINS}} of the three forest sizes. Spark-RFA was {{E1_VERDICT_PY_200}} the serial scikit-learn forest at 200 trees ({{E1_D_RF_PY_200}} pp). Small differences between the two are expected, because both implement the same algorithm but with different random streams and a different split search (MLlib bins every continuous feature into 32 candidate thresholds, scikit-learn tests every value). Compared with the paper, our accuracies at 200 trees differ by {{E1_GAP_PY_200}}, {{E1_GAP_RF_200}} and {{E1_GAP_IRF_200}} pp for Python-RFA, Spark-RFA and Spark-IRFA. Growing the forest from 20 to 200 trees changed Spark-RFA accuracy by {{E1_RF_GAIN_TREES}} pp and Spark-IRFA accuracy by {{E1_IRF_GAIN_TREES}} pp."));
c.push(TCAP("Table 6. E1 training and diagnosis times (s)."));
c.push(T(["Trees", "Train Py", "Train Spark-RF", "Train Spark-IRF (of which optimisation)", "Diagnose Py", "Diagnose Spark-RF", "Diagnose Spark-IRF"], [
  ["20", "{{E1_PY_20_TRAIN}}", "{{E1_RF_20_TRAIN}}", "{{E1_IRF_20_TRAIN}} ({{E1_IRF_20_OPT}})", "{{E1_PY_20_DIAG}}", "{{E1_RF_20_DIAG}}", "{{E1_IRF_20_DIAG}}"],
  ["100", "{{E1_PY_100_TRAIN}}", "{{E1_RF_100_TRAIN}}", "{{E1_IRF_100_TRAIN}} ({{E1_IRF_100_OPT}})", "{{E1_PY_100_DIAG}}", "{{E1_RF_100_DIAG}}", "{{E1_IRF_100_DIAG}}"],
  ["200", "{{E1_PY_200_TRAIN}}", "{{E1_RF_200_TRAIN}}", "{{E1_IRF_200_TRAIN}} ({{E1_IRF_200_OPT}})", "{{E1_PY_200_DIAG}}", "{{E1_RF_200_DIAG}}", "{{E1_IRF_200_DIAG}}"],
], [0.7, 1.0, 1.1, 1.9, 1.1, 1.2, 1.2]));
c.push(P(
  "Because the IRF keeps fewer trees, its diagnosis time was {{E1_DIAGRED_20}}%, {{E1_DIAGRED_100}}% and {{E1_DIAGRED_200}}% lower than that of Spark-RFA for 20, 100 and 200 trees, against 74.29% reported by the paper for Dataset 1 with 100 trees. Relative to the serial Python-RFA, Spark-IRFA diagnosed {{E1_SPEEDUP_PY_200}} times faster with 200 trees. The price is a longer training phase: the sub-forest optimisation added {{E1_IRF_100_OPT}} s at 100 trees, of which {{E1_IRF_100_SIM}} s were spent on the similarity matrix, whose trees had on average {{E1_IRF_100_PATHS}} root-to-leaf paths."));
c.push(H2("4.2 Sensitivity to the similarity threshold"));
c.push(P(
  "With 100 trees the low-accuracy filter kept {{SW_SUB}} trees. Of the off-diagonal entries of the similarity matrix, {{E1_SIM_ZERO_FRAC_100}}% were zero because the two roots used different features or distant thresholds; the non-zero entries had a median of {{E1_SIM_NZ_MEDIAN_100}} and a 90th percentile of {{E1_SIM_NZ_P90_100}}. Table 7 shows how many trees the IRF keeps for each value of similarityFilter, and the hard-vote accuracy of the resulting forest."));
c.push(TCAP("Table 7. Effect of similarityFilter (100 trees; accuracy by majority vote of the kept trees)."));
c.push(T(["Threshold", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"], [
  ["Groups", "{{SW_G_3}}", "{{SW_G_4}}", "{{SW_G_5}}", "{{SW_G_6}}", "{{SW_G_7}}", "{{SW_G_8}}", "{{SW_G_9}}"],
  ["Trees kept", "{{SW_N_3}}", "{{SW_N_4}}", "{{SW_N_5}}", "{{SW_N_6}}", "{{SW_N_7}}", "{{SW_N_8}}", "{{SW_N_9}}"],
  ["Accuracy (%)", "{{SW_A_3}}", "{{SW_A_4}}", "{{SW_A_5}}", "{{SW_A_6}}", "{{SW_A_7}}", "{{SW_A_8}}", "{{SW_A_9}}"],
], [1.4, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8]));
c.push(FIG("e1_threshold_sweep.png", 4.2));
c.push(CAP("Figure 2. Number of trees kept by the IRF as a function of similarityFilter."));
c.push(H2("4.3 E2 – Scalability with executor cores"));
c.push(TCAP("Table 8. E2 times (s) with 100 trees; reduction and speed-up of Spark-IRFA relative to one core."));
c.push(T(["Cores", "Train Spark-RF", "Train Spark-IRF", "IRF optimisation", "Reduction IRF (%)", "Speed-up IRF", "Diagnose Spark-RF", "Diagnose Spark-IRF"], [
  ["1", "{{E2_RF_TRAIN_1}}", "{{E2_IRF_TRAIN_1}}", "{{E2_IRF_OPT_1}}", "{{E2_RED_1}}", "{{E2_SPEEDUP_1}}", "{{E2_RF_DIAG_1}}", "{{E2_IRF_DIAG_1}}"],
  ["2", "{{E2_RF_TRAIN_2}}", "{{E2_IRF_TRAIN_2}}", "{{E2_IRF_OPT_2}}", "{{E2_RED_2}}", "{{E2_SPEEDUP_2}}", "{{E2_RF_DIAG_2}}", "{{E2_IRF_DIAG_2}}"],
  ["3", "{{E2_RF_TRAIN_3}}", "{{E2_IRF_TRAIN_3}}", "{{E2_IRF_OPT_3}}", "{{E2_RED_3}}", "{{E2_SPEEDUP_3}}", "{{E2_RF_DIAG_3}}", "{{E2_IRF_DIAG_3}}"],
  ["4", "{{E2_RF_TRAIN_4}}", "{{E2_IRF_TRAIN_4}}", "{{E2_IRF_OPT_4}}", "{{E2_RED_4}}", "{{E2_SPEEDUP_4}}", "{{E2_RF_DIAG_4}}", "{{E2_IRF_DIAG_4}}"],
], [0.7, 1.0, 1.0, 1.0, 1.0, 0.9, 1.0, 1.0]));
c.push(FIG("e2_reduction_vs_paper.png", 4.6));
c.push(CAP("Figure 3. Training-time reduction of Spark-IRFA relative to one core (ours) and to one worker node (paper)."));
c.push(P(
  "Spark-IRFA training time {{E2_TREND}} as cores were added. The reduction relative to one core was {{E2_RED_2}}%, {{E2_RED_3}}% and {{E2_RED_4}}% with 2, 3 and 4 cores, whereas the paper reports 51.48%, 66.08% and 73.26% with 2, 3 and 4 worker nodes. Parallel efficiency at 4 cores was {{E2_EFF_4}}%. Spark-RFA alone was reduced by {{E2_RFRED_4}}% at 4 cores. At {{E2_MAXC}} cores the IRF needed {{E2_OVERHEAD_MAX}}% more training time than the plain Spark-RFA, against 85.98% in the paper on Dataset 1 with four workers. The comparison is qualitative: one virtual CPU is not one eight-core node, and all cores share one memory bus and one disk."));
c.push(FIG("e2_training_time.png", 4.2));
c.push(CAP("Figure 4. E2 training time of Spark-RFA and Spark-IRFA against the number of executor cores."));
c.push(H2("4.4 E3 – Effect of data size"));
c.push(TCAP("Table 9. E3 results with 100 trees on nested subsets of the enlarged dataset."));
c.push(T(["Subset", "Raw size (GB)", "Training rows", "Spark-RF acc. (%)", "Spark-IRF acc. (%)", "IRF trees", "Train Spark-RF (s)", "Train Spark-IRF (s)"], [
  ["25%", "{{E3_GB_25}}", "{{E3_N_25}}", "{{E3_RF_ACC_25}}", "{{E3_IRF_ACC_25}}", "{{E3_IRF_NTREES_25}}", "{{E3_RF_TRAIN_25}}", "{{E3_IRF_TRAIN_25}}"],
  ["50%", "{{E3_GB_50}}", "{{E3_N_50}}", "{{E3_RF_ACC_50}}", "{{E3_IRF_ACC_50}}", "{{E3_IRF_NTREES_50}}", "{{E3_RF_TRAIN_50}}", "{{E3_IRF_TRAIN_50}}"],
  ["100%", "{{E3_GB_100}}", "{{E3_N_100}}", "{{E3_RF_ACC_100}}", "{{E3_IRF_ACC_100}}", "{{E3_IRF_NTREES_100}}", "{{E3_RF_TRAIN_100}}", "{{E3_IRF_TRAIN_100}}"],
], [0.7, 0.9, 1.0, 1.0, 1.0, 0.8, 1.0, 1.0]));
c.push(FIG("e3_datasize.png", 5.8));
c.push(CAP("Figure 5. E3 accuracy and training time against dataset size."));
c.push(P(
  "As the data grew from {{E3_GB_25}} to {{E3_GB_100}} GB, Spark-IRFA accuracy {{E3_TREND}} ({{E3_DIFF}} pp). The paper reports a rise from 97.09% to 98.12% between 5.6 and 20.4 GB; at 5.6 GB our value differs from the paper's by {{E3_GAP_56}} pp. Spark-IRFA training time went from {{E3_IRF_TRAIN_25}} s to {{E3_IRF_TRAIN_100}} s and Spark-RFA from {{E3_RF_TRAIN_25}} s to {{E3_RF_TRAIN_100}} s; for a fixed depth, the cost of tree induction is expected to grow roughly linearly with the number of training rows."));
c.push(H2("4.5 Summary of the comparison"));
c.push(TCAP("Table 10. Claim-by-claim comparison with the original study."));
c.push(T(["Claim of the paper", "Paper", "This reproduction", "Verdict"], [
  ["IRF is more accurate than Spark RF (200 trees)", "+0.71 pp", "{{E1_D_IRF_RF_200}} pp", "{{V_A}}"],
  ["Accuracy level of all methods (200 trees)", "96.4–97.2%", "{{E1_PY_200_ACC}} / {{E1_RF_200_ACC}} / {{E1_IRF_200_ACC}}%", "{{V_B}}"],
  ["Training time falls with more parallel resources", "−73.26% (4 nodes)", "−{{E2_RED_MAX}}% ({{E2_MAXC}} cores)", "{{V_C}}"],
  ["IRF diagnoses faster than Spark RF", "−74.29% (D1)", "−{{E1_DIAGRED_100}}% (100 trees)", "{{V_D}}"],
  ["IRF training costs more than Spark RF", "+85.98% (D1)", "+{{E2_OVERHEAD_MAX}}%", "{{V_E}}"],
  ["Accuracy rises with data size", "+1.03 pp (5.6→20.4 GB)", "{{E3_DIFF}} pp (1.4→5.6 GB)", "{{V_F}}"],
], [2.6, 1.4, 1.9, 1.7]));

// ---------------- 5 discussion
c.push(H1("5. Discussion"));
c.push(H2("5.1 Similarities"));
c.push(P(
  "The overall shape of the method could be rebuilt from the text, and the qualitative mechanisms behave as described. The low-accuracy filter and the similarity-based selection shrink the forest, and a smaller forest diagnoses proportionally faster, because prediction cost is linear in the number of trees. Spark spreads both training and the sub-forest optimisation over the available cores, and the optimisation is an extra cost paid once at training time, as the paper also reports. With 200 trees the three implementations reached {{E1_PY_200_ACC}}%, {{E1_RF_200_ACC}}% and {{E1_IRF_200_ACC}}%, against 96.43–97.22% in the paper (verdict: {{V_B}})."));
c.push(H2("5.2 Differences and their likely causes"));
c.push(P(
  "**Under-specified preprocessing.** The paper does not give the window length, the overlap step, the wavelet basis, the decomposition level or its exact class list, and its Table 3 describes the forest parameters only qualitatively. Each of these choices changes the feature space and therefore the absolute accuracy, so the gap of {{E1_GAP_RF_200}} pp between our Spark-RFA and the paper's at 200 trees cannot be attributed to the method alone."));
c.push(P(
  "**The size of the IRF gain.** The paper's main accuracy claim is a gain of 0.71 pp at 200 trees; ours is {{E1_D_IRF_RF_200}} pp. Differences of a few tenths of a point are close to the variation caused by the random seed alone, and the paper reports single runs without confidence intervals. Two implementation details matter here. First, MLlib forests vote by averaging the class probabilities of the trees, while the IRF of the paper is described with majority voting; we rebuilt the IRF as an MLlib model so that it is diagnosed by the same engine, which makes the timing comparison fair but means that our IRF also uses probability averaging. Second, the filter rule and similarityFilter are free parameters: Table 7 shows that the number of kept trees, and therefore both speed and accuracy, depend directly on the threshold. In our runs {{E1_SIM_ZERO_FRAC_100}}% of the tree pairs had zero similarity and the median of the remaining pairs was {{E1_SIM_NZ_MEDIAN_100}}, which can be compared with the paper's own remark that vibration-signal trees are not very similar and that a small threshold should be chosen", fnWan(37874), "."));
c.push(P(
  "**Equation inconsistencies.** Equation (2) and the line of Algorithm 1 that computes path similarity are written differently, and the text does not say whether the split direction matters when two nodes are compared. We implemented Equation (2) literally, counting the root and the matching leaf as similar and comparing nodes position by position, and documented this choice in the code. A different reading would change the similarity values and therefore the trees that survive."));
c.push(P(
  "**Cores versus nodes.** E2 replaces worker nodes by virtual CPUs of one machine. Additional cores share the memory bandwidth and the last-level cache of a single processor, and on a shared cloud host the vCPUs may be hyper-threads of the same physical cores, so speed-ups are expected to flatten earlier than on a cluster. On the other hand, local mode has no network shuffle and no HDFS replication, which removes the communication and serialisation overheads that the paper measured at 5.70% of training time", fnWan(37877), ". The two effects push in opposite directions, so only the trend, not the exact percentages, can be compared."));
c.push(P(
  "**Overlapping windows and data leakage.** With an overlap of up to {{OVERLAP_PCT}}%, neighbouring windows are almost identical. A random 6:2:2 split, as used in the paper, therefore places near-copies of test windows in the training set, which can inflate accuracy and is a known source of over-optimistic results in machine-learning studies", fn(['Kapoor, Sayash; and Arvind Narayanan, "Leakage and the Reproducibility Crisis in Machine-Learning-Based Science", ', { t: "Patterns", i: true }, " vol. 4, no. 9 (2023), p. 1. Available at: ", { link: "https://doi.org/10.1016/j.patter.2023.100804" }, "."]),
  ". We kept the paper's random split to stay faithful to it, but the reported accuracies, the paper's and ours alike, should be read as within-recording accuracy rather than generalisation to new bearings. The same argument explains why the enlarged dataset adds volume but little new information, which limits what E3 can show."));
c.push(P(
  "**Reported speed-ups.** The conclusion of the paper states speed-ups of 6.84 and 3.55 times, which do not match its own measurements (about 7.84 and about 4.5 times). Such inconsistencies make it unclear which numbers a reproduction should target; we compared against the measured percentages rather than the summary ratios."));
c.push(H2("5.3 Challenges"));
c.push(BUL("**Missing code and parameters.** The IRF had to be implemented from prose, pseudo-code and equations that do not fully agree; every gap was closed with an explicit, configurable assumption (Table 3)."));
c.push(BUL("**Access to MLlib trees.** PySpark gives no direct access to node structure. Reading the saved Parquet node table solved this, and the per-tree agreement check confirmed that the exported trees predict exactly like MLlib's."));
c.push(BUL("**Limited memory and disk.** The runner has about 16 GB of RAM and limited disk space; a 6 GB Spark driver, binary storage of the windows, Arrow batches of 1,000 rows and deleting the raw windows after feature extraction were needed to process the 5.6 GB dataset."));
c.push(BUL("**Cost of the similarity matrix.** Comparing every path of every tree with every path of every other tree grows with the square of both the number of trees and the number of paths. Vectorising the comparison with NumPy and distributing rows over the cores kept it to {{E1_IRF_100_SIM}} s for 100 trees."));
c.push(H2("5.4 Limitations"));
c.push(P(
  "The reproduction covers only Dataset 1; the 11.2 and 20.4 GB datasets would not fit comfortably in the memory and disk of one runner, and the cluster-level effects of the paper (network, HDFS, executor placement) are absent. Timings on a shared cloud machine depend on its background load, and were measured {{NSEEDS}} time(s) per setting, so small differences in time should not be over-interpreted. Several parameters had to be assumed, and the threshold sweep shows that the IRF is sensitive to at least one of them. Finally, the features and the split follow the paper, so the leakage concern raised above applies equally to our numbers."));
c.push(H2("5.5 Reproducibility assessment"));
c.push(P(
  "The data are public and the method is described in enough detail to rebuild it, so the study is reproducible at the level of methodology. It is only partially reproducible at the level of numbers, because essential settings are missing, the equations and the summary ratios contain inconsistencies, and the code is not available. Publishing the preprocessing parameters, the content of Tables 1 and 3, the split procedure and the code would have removed most of the uncertainty documented here. To avoid the same problem, our repository records every setting in one configuration file, fixes all random seeds, stores raw results as CSV files, and regenerates every table and figure of this report from them."));

// ---------------- 6 conclusion
c.push(H1("6. Conclusion"));
c.push(P(
  "This project reproduced the Spark-based improved random forest of Wan et al. (2021) on a single four-core machine: the CWRU signals were enlarged to {{RAW_GB}} GB by overlapping sampling, wavelet-packet features were extracted with Spark, and the four IRF stages were implemented in PySpark on top of MLlib. With 200 trees the IRF reached {{E1_IRF_200_ACC}}% accuracy, {{E1_VERDICT_200}} the standard Spark forest, while keeping {{E1_IRF_200_NTREES}} trees; diagnosis became {{E1_DIAGRED_100}}% faster at 100 trees, and training time fell by {{E2_RED_MAX}}% from 1 to {{E2_MAXC}} cores. Of the six claims compared in Table 10, {{V_COUNT}} were reproduced at least qualitatively: the accuracy gain of the IRF ({{V_A}}), the accuracy level ({{V_B}}), the scalability with parallel resources ({{V_C}}), the faster diagnosis ({{V_D}}), the extra training cost ({{V_E}}) and the effect of data size ({{V_F}})."));
c.push(P(
  "The main lessons are that a reproduction is only as good as the information published with the original work, that free parameters such as similarityFilter directly decide how many trees the IRF keeps and therefore its speed and accuracy, and that overlapping-window datasets need careful splitting before high accuracies can be trusted. A natural next step would be to repeat the experiments on a real multi-node cluster and with a split by recording, so that both the scalability and the generalisation claims can be tested more strictly."));

// ---------------- references
c.push(H1("References"));
const REFS = [
  ['Breiman, Leo, "Random Forests", ', { t: "Machine Learning", i: true }, " vol. 45, no. 1 (2001), pp. 5–32. Available at: ", { link: "https://doi.org/10.1023/A:1010933404324" }],
  ['Kapoor, Sayash; and Arvind Narayanan, "Leakage and the Reproducibility Crisis in Machine-Learning-Based Science", ', { t: "Patterns", i: true }, " vol. 4, no. 9 (2023), article 100804. Available at: ", { link: "https://doi.org/10.1016/j.patter.2023.100804" }],
  ['Lee, Gregory R.; Ralf Gommers; Filip Waselewski; Kai Wohlfahrt; and Aaron O’Leary, "PyWavelets: A Python Package for Wavelet Analysis", ', { t: "Journal of Open Source Software", i: true }, " vol. 4, no. 36 (2019), p. 1237. Available at: ", { link: "https://doi.org/10.21105/joss.01237" }],
  ['Meng, Xiangrui et al., "MLlib: Machine Learning in Apache Spark", ', { t: "Journal of Machine Learning Research", i: true }, " vol. 17, no. 34 (2016), pp. 1–7. Available at: ", { link: "https://jmlr.org/papers/v17/15-237.html" }],
  ['Pedregosa, Fabian et al., "Scikit-learn: Machine Learning in Python", ', { t: "Journal of Machine Learning Research", i: true }, " vol. 12 (2011), pp. 2825–2830. Available at: ", { link: "https://jmlr.org/papers/v12/pedregosa11a.html" }],
  ['Smith, Wade A.; and Robert B. Randall, "Rolling Element Bearing Diagnostics Using the Case Western Reserve University Data: A Benchmark Study", ', { t: "Mechanical Systems and Signal Processing", i: true }, " vol. 64–65 (2015), pp. 100–131. Available at: ", { link: "https://doi.org/10.1016/j.ymssp.2015.04.021" }],
  [W1, { t: "IEEE Access", i: true }, " vol. 9 (2021), pp. 37866–37882. Available at: ", { link: DOI_W }],
  ['Zaharia, Matei et al., "Apache Spark: A Unified Engine for Big Data Processing", ', { t: "Communications of the ACM", i: true }, " vol. 59, no. 11 (2016), pp. 56–65. Available at: ", { link: "https://doi.org/10.1145/2934664" }],
];
for (const r of REFS) c.push(new Paragraph({ indent: { left: 400, hanging: 400 }, spacing: { after: 100 }, children: r.map(runFromPart(20)) }));

// ---------------- supporting material, division of work, reflection
c.push(H1("Appendix A. Supporting Materials"));
c.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Repository (code, setup instructions, configuration, experiment scripts, raw results and figures): ", font: FONT, size: 22 }),
  new ExternalHyperlink({ link: "{{GITHUB_URL}}", children: [new TextRun({ text: "{{GITHUB_URL}}", style: "Hyperlink", font: FONT, size: 22 })] })] }));
c.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Dataset: CWRU Bearing Data Center, ", font: FONT, size: 22 }),
  new ExternalHyperlink({ link: "https://engineering.case.edu/bearingdatacenter", children: [new TextRun({ text: "https://engineering.case.edu/bearingdatacenter", style: "Hyperlink", font: FONT, size: 22 })] }),
  new TextRun({ text: " (file numbers listed in src/irf_repro/cwru.py).", font: FONT, size: 22 })] }));
c.push(P("External software used and acknowledged: Apache Spark / PySpark (Apache License 2.0), NumPy, pandas, PyArrow, SciPy, PyWavelets, scikit-learn, Matplotlib, python-docx and python-pptx. No code from the original authors was used, as none is published."));
c.push(H1("Appendix B. Division of Work"));
c.push(T(["Student (name / ID)", "Assigned responsibility", "Tasks completed", "Individual outputs"], [
  ["{{AUTHOR}} / {{STUDENT_ID}}", "All roles (single-student team, approved reduced scope)",
    "Paper analysis; Spark environment and GitHub Actions workflow; CWRU download; overlapping sampling; wavelet-packet features; Spark RF; IRF implementation (Steps 2–7); experiments E1–E3; comparison and analysis; testing; documentation",
    "GitHub repository; proposal; this report; presentation slides"],
], [1.5, 1.6, 2.9, 1.6]));
c.push(H1("Appendix C. Reflection"));
c.push(P(
  "Working alone on a task designed for a team forced me to own every layer of the reproduction, from configuring Java and Spark to translating the paper's equations into vectorised code. The most valuable lesson was how much a published result depends on details that are easy to leave out of a paper: the similarity threshold and the way overlapping windows are split both affect what can be observed. I also learned to treat timings with care, since local-mode Spark on one machine behaves differently from a cluster, and to verify each component separately, for example by checking that the exported trees predict exactly like MLlib's, before trusting end-to-end numbers."));

c.push(H1("Appendix D. Code Structure and How to Reproduce"));
c.push(P("The repository is a Python package with numbered scripts; every setting is in config.yaml and every result is written to results/ as CSV or JSON. The GitHub Actions workflow .github/workflows/experiments.yml runs the complete pipeline on a clean machine and commits the results, figures and this report back to the repository."));
c.push(T(["File", "Purpose"], [
  ["config.yaml", "all parameters of the reproduction; assumptions are marked"],
  ["src/irf_repro/cwru.py", "CWRU file catalogue, .mat loading, overlapping-window positions"],
  ["src/irf_repro/wpd.py", "vectorised wavelet-packet relative-energy features"],
  ["src/irf_repro/trees.py", "export of MLlib trees from Parquet, NumPy prediction, path extraction"],
  ["src/irf_repro/irf.py", "IRF Steps 2–7: filter, Equations (1)–(3), grouping, selection, voting"],
  ["src/irf_repro/spark_jobs.py", "Spark session, splits, Spark RF, distributed IRF, sub-model rebuild"],
  ["src/irf_repro/experiment.py", "one experimental run of the three methods with timings"],
  ["scripts/00–03", "environment record, download, overlapping sampling, feature extraction"],
  ["scripts/04–06", "experiments E1, E2 and E3"],
  ["scripts/07–08", "figures and generation of the report and slides from the results"],
  ["tests/test_core.py", "unit tests of tree export, IRF logic and wavelet features"],
], [2.4, 5.2]));
c.push(P("To reproduce: install Python 3.11, Java 17 and requirements.txt, then run bash scripts/run_all.sh, or start the experiments workflow from the Actions tab of the repository."));
c.push(H1("Declaration on the Use of Artificial Intelligence"));
c.push(P("In line with the module's policy, I declare that a generative AI assistant (Claude, Anthropic) was used during this assignment. It assisted in drafting and debugging the Python/PySpark code and the GitHub Actions workflow, in structuring this report and the presentation, and in editing the English text. The selection of the paper, the scope, the decisions on assumptions and the interpretation were reviewed and approved by me. All experimental results reported in Sections 4 and 5 were produced by actually executing the code in the repository; no number was generated or estimated by the AI tool. I have checked the content and take full responsibility for this submission."));

// ================================================================== document
const doc = new Document({
  creator: "{{AUTHOR}}",
  title: "AI508 Assignment 2 Report",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 30, bold: true, color: "1F3864" }, paragraph: { spacing: { before: 300, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: "2F5496" }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  footnotes: FN,
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: 1200, bottom: 1200, left: MARGIN, right: MARGIN } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 })] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(HERE, "..", "report_template.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out);
});
