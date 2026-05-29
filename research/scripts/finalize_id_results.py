#!/usr/bin/env python3
"""Finalize ID benchmark results for thesis-grade reporting.

This script reads the already-computed predictions and metrics, then:

1. Detects DEGENERATE labels (constant predictions, AUROC == 0.5 exactly) and
   excludes them from aggregation. Documents which labels are excluded per model.
2. Computes a COMMON-LABEL macro (only the 7 labels every model supports) for
   fair head-to-head comparison.
3. Computes a VALID-LABEL macro (model-specific label set, minus degenerate ones).
4. Generates SCORE DISTRIBUTION plots (predicted probability histograms by class)
   for every model.
5. Generates OVERLAY ROC curves (all models on one plot, per common label).
6. Generates fair macro comparison bar charts with error bars (bootstrap CI on
   common-label set).
7. Re-bootstraps (patient-level cluster) on the common-label set.
8. Writes a consolidated thesis-ready summary table (CSV + JSON).

Usage:
    research/.venv/bin/python research/scripts/finalize_id_results.py \
        --tag full_frontal_all --n-bootstrap 500 --jobs 4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    matthews_corrcoef,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ID_LABELS: Tuple[str, ...] = (
    "No Finding", "Enlarged Cardiomediastinum", "Cardiomegaly", "Lung Lesion",
    "Lung Opacity", "Edema", "Consolidation", "Pneumonia", "Atelectasis",
    "Pneumothorax", "Pleural Effusion", "Pleural Other", "Fracture",
    "Support Devices",
)

DEFAULT_MODELS: Tuple[str, ...] = (
    "densenet121-res224-all",
    "densenet121-res224-nih",
    "resnet50-res512-all",
)

# Short display names for compact plots.
MODEL_SHORT: Dict[str, str] = {
    "densenet121-res224-all": "DN121-all",
    "densenet121-res224-chex": "DN121-chex",
    "densenet121-res224-mimic_nb": "DN121-mimic_nb",
    "densenet121-res224-mimic_ch": "DN121-mimic_ch",
    "densenet121-res224-nih": "DN121-nih",
    "densenet121-res224-pc": "DN121-pc",
    "resnet50-res512-all": "RN50-all",
}


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def json_dump(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_model_info(root: Path, model: str, tag: str) -> Dict[str, Any]:
    """Read label_map + predictions for a model."""
    base = root / model / tag
    lm = json.loads((base / "label_map.json").read_text(encoding="utf-8"))
    pathologies = list(lm["model_pathologies"])
    label_to_idx = {k: int(v) for k, v in lm["id_to_model_index"].items()}
    labels = list(lm["id_labels_evaluated"])
    pred_df = pd.read_csv(base / "predictions_raw.csv")
    return {
        "model": model,
        "pathologies": pathologies,
        "label_to_idx": label_to_idx,
        "labels": labels,
        "pred_df": pred_df,
    }


def get_y_and_p(info: Dict, label: str, policy: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (mask, y01, prob) for a given label + policy."""
    df = info["pred_df"]
    idx = info["label_to_idx"].get(label)
    if idx is None:
        return np.array([], dtype=bool), np.array([]), np.array([])
    pred_col = f"pred__{info['pathologies'][idx]}"
    if pred_col not in df.columns:
        return np.array([], dtype=bool), np.array([]), np.array([])
    y_raw = pd.to_numeric(df[label], errors="coerce").fillna(0).astype(int).to_numpy()
    p = np.clip(pd.to_numeric(df[pred_col], errors="coerce").fillna(0.0).astype(float).to_numpy(), 0.0, 1.0)
    if policy == "u0":
        y = y_raw.copy()
        y[y == -1] = 0
        mask = (y == 0) | (y == 1)
    elif policy == "ignore_uncertain":
        mask = (y_raw == 0) | (y_raw == 1)
        y = y_raw.copy()
    else:
        raise ValueError(policy)
    return mask, y[mask].astype(np.int64), p[mask]


def is_degenerate(y: np.ndarray, p: np.ndarray) -> bool:
    """True if the model outputs a near-constant prediction (AUROC ~0.5)."""
    if y.size < 10:
        return True
    pos = int(np.sum(y == 1))
    neg = int(np.sum(y == 0))
    if pos == 0 or neg == 0:
        return True
    try:
        auc = roc_auc_score(y, p)
    except Exception:
        return True
    # Constant prediction -> AUROC exactly 0.5.  Allow small epsilon.
    if abs(auc - 0.5) < 0.005:
        return True
    # Extremely low variance in predictions also indicates degeneracy.
    if np.std(p) < 1e-6:
        return True
    return False


def safe_auroc(y: np.ndarray, p: np.ndarray) -> Optional[float]:
    if y.size == 0 or int(np.sum(y == 1)) == 0 or int(np.sum(y == 0)) == 0:
        return None
    return float(roc_auc_score(y, p))


def safe_ap(y: np.ndarray, p: np.ndarray) -> Optional[float]:
    if y.size == 0:
        return None
    pos = int(np.sum(y == 1))
    if pos == 0:
        return 0.0
    neg = int(np.sum(y == 0))
    if neg == 0:
        return 1.0
    try:
        return float(average_precision_score(y, p))
    except Exception:
        return None


def ece_10bin(y: np.ndarray, p: np.ndarray) -> Optional[float]:
    if y.size == 0:
        return None
    y = y.astype(np.int64)
    p = np.clip(p.astype(np.float64), 0.0, 1.0)
    bins = np.linspace(0.0, 1.0, 11)
    idx = np.clip(np.digitize(p, bins) - 1, 0, 9)
    ece = 0.0
    for b in range(10):
        m = idx == b
        if not np.any(m):
            continue
        ece += (np.sum(m) / y.size) * abs(float(np.mean(y[m])) - float(np.mean(p[m])))
    return float(ece)


def confusion_at(y: np.ndarray, p: np.ndarray, thr: float) -> Dict[str, Any]:
    y = y.astype(np.int64)
    yp = (p >= thr).astype(np.int64)
    tp = int(np.sum((y == 1) & (yp == 1)))
    tn = int(np.sum((y == 0) & (yp == 0)))
    fp = int(np.sum((y == 0) & (yp == 1)))
    fn = int(np.sum((y == 1) & (yp == 0)))
    rec = tp / max(1, tp + fn)
    spec = tn / max(1, tn + fp)
    prec = tp / max(1, tp + fp)
    f1 = (2 * prec * rec) / max(1e-12, prec + rec)
    try:
        mcc = float(matthews_corrcoef(y, yp)) if len(np.unique(y)) > 1 and len(np.unique(yp)) > 1 else None
    except Exception:
        mcc = None
    return {
        "threshold": float(thr), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": float((tp + tn) / max(1, tp + tn + fp + fn)),
        "balanced_accuracy": float(0.5 * (rec + spec)),
        "precision": float(prec), "recall_sensitivity": float(rec),
        "specificity": float(spec), "f1": float(f1), "mcc": mcc,
    }


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

PALETTE = sns.color_palette("tab10", n_colors=10)
MODEL_COLORS = {m: PALETTE[i] for i, m in enumerate(DEFAULT_MODELS)}


def plot_score_distributions(info: Dict, policy: str, labels: List[str], out_dir: Path) -> None:
    """Histogram of predicted probabilities split by pos/neg for each label."""
    sns.set_theme(style="whitegrid")
    n = len(labels)
    if n == 0:
        return
    ncols = 4
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(4.2 * ncols, 3.4 * nrows))
    axes = np.array(axes).reshape(-1)
    for i, lab in enumerate(labels):
        ax = axes[i]
        mask, y, p = get_y_and_p(info, lab, policy)
        if y.size == 0:
            ax.axis("off")
            continue
        p0 = p[y == 0]
        p1 = p[y == 1]
        if p0.size:
            ax.hist(p0, bins=30, range=(0, 1), alpha=0.6, label=f"neg ({len(p0)})", color="#4C72B0")
        if p1.size:
            ax.hist(p1, bins=30, range=(0, 1), alpha=0.6, label=f"pos ({len(p1)})", color="#DD8452")
        ax.set_xlim(0, 1)
        ax.set_xlabel("Predicted prob")
        ax.set_ylabel("Count")
        ax.set_title(lab)
        ax.legend(fontsize=7)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    model = info["model"]
    fig.suptitle(f"Score distributions ({model}, {policy})")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_dir / "score_distributions.png", dpi=200)
    plt.close(fig)


def plot_overlay_roc(
    all_info: Dict[str, Dict],
    labels: List[str],
    policy: str,
    out_path: Path,
    title_suffix: str = "",
) -> None:
    """One subplot per label, all models overlaid."""
    sns.set_theme(style="whitegrid")
    n = len(labels)
    if n == 0:
        return
    ncols = 4
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(4.5 * ncols, 3.8 * nrows))
    axes = np.array(axes).reshape(-1)

    for i, lab in enumerate(labels):
        ax = axes[i]
        ax.plot([0, 1], [0, 1], ls="--", lw=0.8, color="gray", alpha=0.5)
        for model, info in all_info.items():
            if lab not in info["label_to_idx"]:
                continue
            mask, y, p = get_y_and_p(info, lab, policy)
            auc = safe_auroc(y, p)
            if auc is None or is_degenerate(y, p):
                continue
            fpr, tpr, _ = roc_curve(y, p)
            short = MODEL_SHORT.get(model, model)
            ax.plot(fpr, tpr, lw=1.3, color=MODEL_COLORS.get(model), label=f"{short} ({auc:.3f})")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("FPR")
        ax.set_ylabel("TPR")
        ax.set_title(lab)
        ax.legend(fontsize=6, loc="lower right")
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle(f"ROC overlay{title_suffix} ({policy})")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_overlay_pr(
    all_info: Dict[str, Dict],
    labels: List[str],
    policy: str,
    out_path: Path,
    title_suffix: str = "",
) -> None:
    """One subplot per label, all models overlaid - Precision-Recall."""
    sns.set_theme(style="whitegrid")
    n = len(labels)
    if n == 0:
        return
    ncols = 4
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(4.5 * ncols, 3.8 * nrows))
    axes = np.array(axes).reshape(-1)

    for i, lab in enumerate(labels):
        ax = axes[i]
        for model, info in all_info.items():
            if lab not in info["label_to_idx"]:
                continue
            mask, y, p = get_y_and_p(info, lab, policy)
            ap = safe_ap(y, p)
            if ap is None or is_degenerate(y, p):
                continue
            prec, rec, _ = precision_recall_curve(y, p)
            short = MODEL_SHORT.get(model, model)
            ax.plot(rec, prec, lw=1.3, color=MODEL_COLORS.get(model), label=f"{short} ({ap:.3f})")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title(lab)
        ax.legend(fontsize=6, loc="upper right")
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle(f"PR overlay{title_suffix} ({policy})")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_fair_macro_bar(
    summary_df: pd.DataFrame,
    metric: str,
    title: str,
    out_path: Path,
    ci_low_col: Optional[str] = None,
    ci_high_col: Optional[str] = None,
) -> None:
    """Horizontal bar chart with optional error bars, sorted best-to-worst."""
    sns.set_theme(style="whitegrid")
    d = summary_df.sort_values(metric, ascending=True, na_position="first").copy()
    d["short"] = d["model"].map(MODEL_SHORT)
    fig, ax = plt.subplots(figsize=(10, max(3, 0.6 * len(d))))
    y_pos = np.arange(len(d))
    vals = d[metric].to_numpy(dtype=float)

    has_ci = ci_low_col and ci_high_col and ci_low_col in d.columns and ci_high_col in d.columns
    if has_ci:
        lo = d[ci_low_col].to_numpy(dtype=float)
        hi = d[ci_high_col].to_numpy(dtype=float)
        xerr = np.array([vals - lo, hi - vals])
        xerr = np.clip(xerr, 0, None)
        ax.barh(y_pos, vals, xerr=xerr, color="#4C72B0", ecolor="#333333", capsize=3, height=0.6)
    else:
        hi = vals
        ax.barh(y_pos, vals, color="#4C72B0", height=0.6)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(d["short"].tolist())
    ax.set_xlabel(metric)
    ax.set_title(title)
    ax.set_xlim(0, 1)

    for j, v in enumerate(vals):
        if np.isfinite(v):
            x_anchor = (hi[j] if has_ci and np.isfinite(hi[j]) else v) + 0.015
            ax.text(x_anchor, j, f"{v:.3f}", va="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_per_label_grouped(
    per_label_df: pd.DataFrame,
    metric: str,
    labels: List[str],
    title: str,
    out_path: Path,
) -> None:
    """Grouped bar: x=label, hue=model, y=metric."""
    sns.set_theme(style="whitegrid")
    d = per_label_df[per_label_df["label"].isin(labels)].copy()
    d["short"] = d["model"].map(MODEL_SHORT)
    fig, ax = plt.subplots(figsize=(max(12, 1.5 * len(labels)), 5))
    sns.barplot(data=d, x="label", y=metric, hue="short", ax=ax, order=labels)
    ax.set_title(title)
    ax.set_xlabel("Label")
    ax.set_ylabel(metric)
    ax.tick_params(axis="x", rotation=35)
    ax.legend(title="Model", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_heatmap(pivot: pd.DataFrame, title: str, out_path: Path,
                 vmin=None, vmax=None, cmap="viridis", annot=True) -> None:
    sns.set_theme(style="white")
    # Rename columns for readability
    rename = {m: MODEL_SHORT.get(m, m) for m in pivot.columns}
    pv = pivot.rename(columns=rename)
    fig_w = max(10, 1.4 * pv.shape[1])
    fig_h = max(5, 0.55 * pv.shape[0])
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    sns.heatmap(pv, ax=ax, vmin=vmin, vmax=vmax, cmap=cmap,
                annot=annot, fmt=".3f" if annot else "",
                linewidths=0.3, linecolor="white",
                cbar_kws={"shrink": 0.7}, annot_kws={"fontsize": 8})
    ax.set_title(title)
    ax.set_xlabel("Model")
    ax.set_ylabel("Label")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Bootstrap (common-label, patient-level cluster)
# ---------------------------------------------------------------------------

def _bootstrap_common_labels_worker(args_tuple):
    """Worker for multiprocessing. Returns (model, policy, boot_aurocs, boot_aps)."""
    results_root, model, tag, policy, common_labels, n_boot, seed = args_tuple

    info = load_model_info(results_root, model, tag)
    df = info["pred_df"]
    n = len(df)
    patient_ids = df.get("PatientID", pd.Series([""] * n)).fillna("").astype(str).to_numpy()

    # Pre-extract arrays
    y_arrays = {}
    p_arrays = {}
    valid_labels = []
    for lab in common_labels:
        mask, y, p = get_y_and_p(info, lab, policy)
        if y.size == 0 or is_degenerate(y, p):
            continue
        # We need full-length arrays for resampling
        y_raw = pd.to_numeric(df[lab], errors="coerce").fillna(0).astype(int).to_numpy()
        idx = info["label_to_idx"][lab]
        pred_col = f"pred__{info['pathologies'][idx]}"
        p_full = np.clip(pd.to_numeric(df[pred_col], errors="coerce").fillna(0.0).to_numpy(), 0.0, 1.0)
        y_arrays[lab] = y_raw
        p_arrays[lab] = p_full
        valid_labels.append(lab)

    # Cluster bootstrap
    uniq_pids = np.unique(patient_ids)
    clusters = {pid: np.flatnonzero(patient_ids == pid) for pid in uniq_pids}

    seed_bytes = f"{seed}|{model}|{policy}|common".encode("utf-8")
    seed_int = int.from_bytes(hashlib.sha1(seed_bytes).digest()[:8], "little", signed=False)
    rng = np.random.default_rng(seed_int)

    boot_macro_auroc = np.full(n_boot, np.nan)
    boot_macro_ap = np.full(n_boot, np.nan)
    boot_auroc = {lab: np.full(n_boot, np.nan) for lab in valid_labels}
    boot_ap = {lab: np.full(n_boot, np.nan) for lab in valid_labels}

    for b in range(n_boot):
        sampled = rng.choice(uniq_pids, size=len(uniq_pids), replace=True)
        idxs = np.concatenate([clusters[pid] for pid in sampled])

        aucs = []
        aps = []
        for lab in valid_labels:
            yr = y_arrays[lab][idxs]
            pp = p_arrays[lab][idxs]
            # apply policy
            if policy == "u0":
                yr2 = yr.copy(); yr2[yr2 == -1] = 0
                m = (yr2 == 0) | (yr2 == 1)
                yy = yr2[m].astype(np.int64)
            else:
                m = (yr == 0) | (yr == 1)
                yy = yr[m].astype(np.int64)
            pp2 = np.clip(pp[m], 0.0, 1.0)

            a = safe_auroc(yy, pp2)
            ap = safe_ap(yy, pp2)
            if a is not None:
                boot_auroc[lab][b] = a
                aucs.append(a)
            if ap is not None:
                boot_ap[lab][b] = ap
                aps.append(ap)

        boot_macro_auroc[b] = float(np.mean(aucs)) if aucs else float("nan")
        boot_macro_ap[b] = float(np.mean(aps)) if aps else float("nan")

    return model, policy, boot_macro_auroc, boot_macro_ap, boot_auroc, boot_ap, valid_labels


def ci95(arr: np.ndarray) -> Tuple[float, float, float]:
    x = arr[np.isfinite(arr)]
    if x.size == 0:
        return float("nan"), float("nan"), float("nan")
    return float(np.mean(x)), float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Finalize ID results for thesis.")
    ap.add_argument("--results-root", default="research/results_id")
    ap.add_argument("--tag", default="full_frontal_all")
    ap.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    ap.add_argument("--policies", nargs="*", default=["u0", "ignore_uncertain"])
    ap.add_argument("--n-bootstrap", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--jobs", type=int, default=1)
    args = ap.parse_args()

    t0 = time.perf_counter()
    results_root = Path(args.results_root)
    tag = str(args.tag)
    models = list(args.models)
    policies = list(args.policies)
    n_boot = int(args.n_bootstrap)

    comp = ensure_dir(results_root / "comparison" / tag)
    plots = ensure_dir(comp / "plots")

    # ---- Load all model info ----
    print("Loading predictions...", flush=True)
    all_info: Dict[str, Dict] = {}
    for model in models:
        all_info[model] = load_model_info(results_root, model, tag)

    # ---- Determine common labels ----
    label_sets = [set(info["labels"]) for info in all_info.values()]
    common_labels = sorted(set.intersection(*label_sets))
    print(f"Common labels ({len(common_labels)}): {common_labels}", flush=True)

    # ---- Detect degenerate labels per model ----
    degenerate_report: Dict[str, Dict[str, List[str]]] = {}
    for policy in policies:
        degenerate_report[policy] = {}
        for model in models:
            info = all_info[model]
            degen = []
            for lab in info["labels"]:
                mask, y, p = get_y_and_p(info, lab, policy)
                if is_degenerate(y, p):
                    degen.append(lab)
            degenerate_report[policy][model] = degen
            if degen:
                print(f"  [{model}] {policy}: degenerate labels excluded: {degen}", flush=True)

    json_dump(comp / "degenerate_labels.json", degenerate_report)

    # ---- Per-label metrics (all labels, flagging degenerate) ----
    per_label_rows: List[Dict[str, Any]] = []
    for policy in policies:
        for model in models:
            info = all_info[model]
            degen_set = set(degenerate_report[policy][model])
            for lab in info["labels"]:
                mask, y, p = get_y_and_p(info, lab, policy)
                deg = lab in degen_set
                auc = safe_auroc(y, p) if not deg else None
                ap_val = safe_ap(y, p) if not deg else None
                brier = float(brier_score_loss(y, np.clip(p, 0, 1))) if y.size > 0 and not deg else None
                ece = ece_10bin(y, p) if not deg else None
                per_label_rows.append({
                    "model": model,
                    "policy": policy,
                    "label": lab,
                    "n": int(y.size),
                    "pos": int(np.sum(y == 1)) if y.size else 0,
                    "neg": int(np.sum(y == 0)) if y.size else 0,
                    "prevalence": float(np.sum(y == 1) / max(1, y.size)) if y.size else None,
                    "auroc": auc,
                    "auprc_ap": ap_val,
                    "brier": brier,
                    "ece_10bin": ece,
                    "degenerate": deg,
                    "in_common_set": lab in common_labels,
                })
    per_label_df = pd.DataFrame(per_label_rows)
    per_label_df.to_csv(comp / "per_label_metrics_final.csv", index=False)

    # ---- Macro metrics: common-label + valid-label ----
    macro_rows: List[Dict[str, Any]] = []
    for policy in policies:
        for model in models:
            d = per_label_df[(per_label_df["model"] == model) & (per_label_df["policy"] == policy)]
            dv = d[(~d["degenerate"])]
            dc = d[(d["in_common_set"]) & (~d["degenerate"])]

            def _macro(subset, scope):
                aucs = subset["auroc"].dropna().tolist()
                aps = subset["auprc_ap"].dropna().tolist()
                brs = subset["brier"].dropna().tolist()
                ecs = subset["ece_10bin"].dropna().tolist()
                return {
                    "model": model, "policy": policy, "scope": scope,
                    "n_labels": int(len(subset)),
                    "n_valid_auroc": int(len(aucs)),
                    "macro_auroc": float(np.mean(aucs)) if aucs else None,
                    "macro_auprc_ap": float(np.mean(aps)) if aps else None,
                    "macro_brier": float(np.mean(brs)) if brs else None,
                    "macro_ece_10bin": float(np.mean(ecs)) if ecs else None,
                }
            macro_rows.append(_macro(dv, "valid_labels"))
            macro_rows.append(_macro(dc, "common_labels"))

    macro_df = pd.DataFrame(macro_rows)
    macro_df.to_csv(comp / "macro_metrics_final.csv", index=False)

    # ---- Score distribution plots (per model) ----
    print("Generating score distribution plots...", flush=True)
    for model in models:
        info = all_info[model]
        for policy in policies:
            pol_dir = ensure_dir(results_root / model / tag / f"eval_{policy}" / "plots")
            valid_labels = [l for l in info["labels"] if l not in set(degenerate_report[policy][model])]
            plot_score_distributions(info, policy, valid_labels, pol_dir)

    # ---- Overlay ROC + PR (common labels, all models on one grid) ----
    print("Generating overlay ROC/PR plots...", flush=True)
    for policy in policies:
        plot_overlay_roc(all_info, common_labels, policy,
                         plots / f"overlay_roc_common_{policy}.png",
                         title_suffix=" - common labels")
        plot_overlay_pr(all_info, common_labels, policy,
                        plots / f"overlay_pr_common_{policy}.png",
                        title_suffix=" - common labels")

    # ---- Per-label grouped bar charts (common labels) ----
    for policy in policies:
        d = per_label_df[(per_label_df["policy"] == policy) & (~per_label_df["degenerate"])].copy()
        plot_per_label_grouped(d, "auroc", common_labels,
                               f"AUROC per label, all models ({policy})",
                               plots / f"per_label_auroc_common_{policy}.png")
        plot_per_label_grouped(d, "auprc_ap", common_labels,
                               f"AP per label, all models ({policy})",
                               plots / f"per_label_ap_common_{policy}.png")

    # ---- Heatmaps with annotations (common labels) ----
    for policy in policies:
        d = per_label_df[(per_label_df["policy"] == policy) &
                         (per_label_df["in_common_set"]) &
                         (~per_label_df["degenerate"])].copy()
        for metric, vmin, vmax, cmap in [
            ("auroc", 0.4, 1.0, "YlGnBu"),
            ("auprc_ap", 0.0, 0.4, "YlOrRd"),
            ("brier", None, None, "magma_r"),
            ("ece_10bin", None, None, "magma_r"),
        ]:
            pv = d.pivot_table(index="label", columns="model", values=metric, aggfunc="mean")
            pv = pv.reindex(sorted(pv.index), axis=0)
            plot_heatmap(pv,
                         f"{metric} - common labels ({policy})",
                         plots / f"heatmap_{metric}_common_{policy}.png",
                         vmin=vmin, vmax=vmax, cmap=cmap, annot=True)

    # ---- Delete old misleading comparison plots ----
    old_files = [
        "macro_auroc_u0.png", "macro_auroc_ignore_uncertain.png",
        "heatmap_auroc_u0.png", "heatmap_auroc_ignore_uncertain.png",
        "heatmap_auprc_ap_u0.png", "heatmap_auprc_ap_ignore_uncertain.png",
        "heatmap_brier_u0.png", "heatmap_brier_ignore_uncertain.png",
        "heatmap_ece_10bin_u0.png", "heatmap_ece_10bin_ignore_uncertain.png",
    ]
    for f in old_files:
        p = plots / f
        if p.exists():
            p.unlink()
            print(f"  Deleted old plot: {p.name}", flush=True)

    # Also delete old summary CSVs that used unfair macro
    for f in ["summary_u0.csv", "summary_ignore_uncertain.csv"]:
        p = comp / f
        if p.exists():
            p.unlink()
            print(f"  Deleted old CSV: {p.name}", flush=True)

    # ---- Bootstrap CIs on common labels ----
    print(f"Running bootstrap (B={n_boot}, patient-level)...", flush=True)

    tasks = [
        (results_root, model, tag, policy, common_labels, n_boot, args.seed)
        for policy in policies
        for model in models
    ]

    jobs = int(args.jobs) if args.jobs > 0 else 1
    if jobs <= 1:
        boot_results = [_bootstrap_common_labels_worker(t) for t in tasks]
    else:
        ctx = mp.get_context("fork")
        with ctx.Pool(processes=jobs) as pool:
            boot_results = pool.map(_bootstrap_common_labels_worker, tasks)

    # Consolidate bootstrap results
    ci_macro_rows = []
    ci_label_rows = []
    for model, policy, bm_auroc, bm_ap, b_auroc, b_ap, vlabels in boot_results:
        mean_a, lo_a, hi_a = ci95(bm_auroc)
        mean_p, lo_p, hi_p = ci95(bm_ap)
        # Point estimates from macro_df
        row_m = macro_df[(macro_df["model"] == model) & (macro_df["policy"] == policy) & (macro_df["scope"] == "common_labels")]
        point_auroc = float(row_m["macro_auroc"].iloc[0]) if len(row_m) else mean_a
        point_ap = float(row_m["macro_auprc_ap"].iloc[0]) if len(row_m) else mean_p

        ci_macro_rows.append({
            "model": model, "policy": policy, "metric": "macro_auroc",
            "point": point_auroc, "bootstrap_mean": mean_a,
            "ci_low": lo_a, "ci_high": hi_a, "n_boot": n_boot, "scope": "common_labels",
        })
        ci_macro_rows.append({
            "model": model, "policy": policy, "metric": "macro_auprc_ap",
            "point": point_ap, "bootstrap_mean": mean_p,
            "ci_low": lo_p, "ci_high": hi_p, "n_boot": n_boot, "scope": "common_labels",
        })

        for lab in vlabels:
            ma, la, ha = ci95(b_auroc[lab])
            mp2, lp2, hp2 = ci95(b_ap[lab])
            ci_label_rows.append({
                "model": model, "policy": policy, "label": lab,
                "metric": "auroc", "bootstrap_mean": ma, "ci_low": la, "ci_high": ha,
                "n_boot": n_boot, "scope": "common_labels",
            })
            ci_label_rows.append({
                "model": model, "policy": policy, "label": lab,
                "metric": "auprc_ap", "bootstrap_mean": mp2, "ci_low": lp2, "ci_high": hp2,
                "n_boot": n_boot, "scope": "common_labels",
            })

    ci_macro_df = pd.DataFrame(ci_macro_rows)
    ci_label_df = pd.DataFrame(ci_label_rows)
    ci_macro_df.to_csv(comp / "bootstrap_macro_ci_common.csv", index=False)
    ci_label_df.to_csv(comp / "bootstrap_per_label_ci_common.csv", index=False)

    # ---- Fair macro bar plots (with CIs) ----
    for policy in policies:
        for metric in ["macro_auroc", "macro_auprc_ap"]:
            d = ci_macro_df[(ci_macro_df["policy"] == policy) & (ci_macro_df["metric"] == metric)].copy()
            plot_fair_macro_bar(
                d, "point",
                f"{metric} - common labels, 95% CI ({policy})",
                plots / f"fair_{metric}_common_{policy}.png",
                ci_low_col="ci_low", ci_high_col="ci_high",
            )

    # ---- Final thesis summary table ----
    thesis_rows = []
    for policy in policies:
        for model in models:
            row_common = macro_df[(macro_df["model"] == model) & (macro_df["policy"] == policy) & (macro_df["scope"] == "common_labels")]
            row_valid = macro_df[(macro_df["model"] == model) & (macro_df["policy"] == policy) & (macro_df["scope"] == "valid_labels")]
            ci_row = ci_macro_df[(ci_macro_df["model"] == model) & (ci_macro_df["policy"] == policy) & (ci_macro_df["metric"] == "macro_auroc")]

            tr = {
                "model": model,
                "short_name": MODEL_SHORT.get(model, model),
                "policy": policy,
                "n_images": 112120,
            }
            if len(row_common):
                r = row_common.iloc[0]
                tr["common_labels_n"] = int(r["n_labels"])
                tr["common_macro_auroc"] = r["macro_auroc"]
                tr["common_macro_ap"] = r["macro_auprc_ap"]
                tr["common_macro_brier"] = r["macro_brier"]
                tr["common_macro_ece"] = r["macro_ece_10bin"]
            if len(row_valid):
                r = row_valid.iloc[0]
                tr["valid_labels_n"] = int(r["n_labels"])
                tr["valid_macro_auroc"] = r["macro_auroc"]
                tr["valid_macro_ap"] = r["macro_auprc_ap"]
            if len(ci_row):
                c = ci_row.iloc[0]
                tr["common_auroc_ci_low"] = c["ci_low"]
                tr["common_auroc_ci_high"] = c["ci_high"]
            n_degen = len(degenerate_report.get(policy, {}).get(model, []))
            tr["n_degenerate_labels"] = n_degen
            thesis_rows.append(tr)

    thesis_df = pd.DataFrame(thesis_rows)
    thesis_df.to_csv(comp / "thesis_summary_table.csv", index=False)
    json_dump(comp / "thesis_summary_table.json", thesis_rows)

    t1 = time.perf_counter()
    print(f"\nDone in {t1 - t0:.0f}s. Outputs under: {comp}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
