#!/usr/bin/env python3
"""NIH Chest X-rays ID benchmark for TorchXRayVision pretrained models.

This script tests the ID generalization of models using the NIH dataset.

Outputs
-------
- Model-specific: research/results_id/<model>/<tag>/...
- Cross-model:   research/results_id/comparison/<tag>/...
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.utils.data as tud
import torchxrayvision as xrv
from PIL import Image
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


# We use the pathologies listed in xrv.datasets.default_pathologies
ID_LABELS: Tuple[str, ...] = tuple(xrv.datasets.default_pathologies)

META_COLS: Tuple[str, ...] = (
    "PatientID",
    "PatientSex",
    "PatientAge",
    "Manufacturer",
    "ViewPosition",
)

DEFAULT_MODELS: Tuple[str, ...] = (
    "densenet121-res224-all",
    "densenet121-res224-nih",
    "resnet50-res512-all",
)


def canonical(name: str) -> str:
    s = (name or "").strip().lower()
    out = []
    prev_us = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    return "".join(out).strip("_")


LABEL_ALIASES_CANON: Dict[str, str] = {
    canonical("Pleural Effusion"): canonical("Effusion"),
}


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


AGE_ORDER = [
    "Infants and Toddlers: 0–4 years",
    "Children: 5–14 years",
    "Young Adults: 15–24 years",
    "Adults: 25–64 years",
    "Seniors: 65–84 years",
    "Open-ended: 85+",
]


def json_dump(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def age_to_band(age_str: str) -> str:
    s = str(age_str or "").strip().lower()
    if not s or s == "nan" or s == "none":
        return "unknown"
    if "85" in s:
        return "Open-ended: 85+"
    try:
        age = float(s)
    except ValueError:
        return "unknown"
    if age < 5:
        return "Infants and Toddlers: 0–4 years"
    if age < 15:
        return "Children: 5–14 years"
    if age < 25:
        return "Young Adults: 15–24 years"
    if age < 65:
        return "Adults: 25–64 years"
    if age < 85:
        return "Seniors: 65–84 years"
    return "Open-ended: 85+"


def get_input_size(model_name: str) -> int:
    s = model_name.lower()
    if "res512" in s:
        return 512
    if "res224" in s:
        return 224
    return 512 if "resnet" in s else 224


def load_xrv_model(model_name: str, cache_dir: Path, device: torch.device) -> torch.nn.Module:
    cache_dir = ensure_dir(cache_dir)
    if "resnet" in model_name.lower():
        m = xrv.models.ResNet(weights=model_name, cache_dir=str(cache_dir))
    else:
        m = xrv.models.DenseNet(weights=model_name, cache_dir=str(cache_dir))
    m = m.to(device)
    m.eval()
    return m


def resolve_label_map(model_pathologies: Sequence[str]) -> Dict[str, int]:
    canon_to_idx = {canonical(p): i for i, p in enumerate(model_pathologies)}
    out: Dict[str, int] = {}
    for lab in ID_LABELS:
        c = canonical(lab)
        if c in canon_to_idx:
            out[lab] = canon_to_idx[c]
            continue
        alias = LABEL_ALIASES_CANON.get(c)
        if alias and alias in canon_to_idx:
            out[lab] = canon_to_idx[alias]
    return out


def apply_label_policy(y_raw: np.ndarray, policy: str) -> Tuple[np.ndarray, np.ndarray]:
    if policy == "u0":
        y = y_raw.copy()
        y[y == -1] = 0
        mask = np.isin(y, [0, 1])
        return mask, y.astype(np.int64)
    if policy == "ignore_uncertain":
        mask = np.isin(y_raw, [0, 1])
        return mask, y_raw.astype(np.int64)
    raise ValueError(policy)


def ece_10bin(y_true: np.ndarray, y_prob: np.ndarray) -> Optional[float]:
    if y_true.size == 0:
        return None
    y_true = y_true.astype(np.int64)
    y_prob = np.clip(y_prob.astype(np.float64), 0.0, 1.0)
    bins = np.linspace(0.0, 1.0, 11)
    idx = np.digitize(y_prob, bins) - 1
    idx = np.clip(idx, 0, 9)
    ece = 0.0
    for b in range(10):
        m = idx == b
        if not np.any(m):
            continue
        acc = float(np.mean(y_true[m]))
        conf = float(np.mean(y_prob[m]))
        ece += (np.sum(m) / y_true.size) * abs(acc - conf)
    return float(ece)


def confusion_metrics(y_true: np.ndarray, y_prob: np.ndarray, thr: float = 0.5) -> Dict[str, Any]:
    y_true = y_true.astype(np.int64)
    y_pred = (y_prob >= thr).astype(np.int64)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    rec = tp / max(1, tp + fn)
    spec = tn / max(1, tn + fp)
    prec = tp / max(1, tp + fp)
    bal_acc = 0.5 * (rec + spec)
    f1 = (2 * prec * rec) / max(1e-12, prec + rec)

    try:
        mcc = None if (len(np.unique(y_true)) < 2 or len(np.unique(y_pred)) < 2) else float(matthews_corrcoef(y_true, y_pred))
    except Exception:
        mcc = None

    return {
        "threshold": float(thr),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": float(acc),
        "balanced_accuracy": float(bal_acc),
        "precision": float(prec),
        "recall_sensitivity": float(rec),
        "specificity": float(spec),
        "f1": float(f1),
        "mcc": mcc,
    }


def binary_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, Any]:
    y_true = y_true.astype(np.int64)
    y_prob = np.clip(y_prob.astype(np.float64), 0.0, 1.0)
    pos = int(np.sum(y_true == 1))
    neg = int(np.sum(y_true == 0))

    if pos > 0 and neg > 0:
        auroc = float(roc_auc_score(y_true, y_prob))
    else:
        auroc = None

    try:
        ap = float(average_precision_score(y_true, y_prob))
    except Exception:
        ap = None

    try:
        brier = float(brier_score_loss(y_true, y_prob))
    except Exception:
        brier = None

    return {
        "n": int(y_true.size),
        "pos": pos,
        "neg": neg,
        "prevalence": float(pos / max(1, y_true.size)),
        "auroc": auroc,
        "auprc_ap": ap,
        "brier": brier,
        "ece_10bin": ece_10bin(y_true, y_prob),
        "thr_0_5": confusion_metrics(y_true, y_prob, 0.5),
    }


def plot_grid_curves(
    title: str,
    labels: Sequence[str],
    curves: Dict[str, Tuple[np.ndarray, np.ndarray, Optional[float]]],
    xlab: str,
    ylab: str,
    diag: bool,
    out_path: Path,
) -> None:
    sns.set_theme(style="whitegrid")
    # Only plot labels that have actual curve data
    valid = [l for l in labels if l in curves and curves[l][0].size > 0]
    n = len(valid)
    if n == 0:
        return
    ncols = 4
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(4.2 * ncols, 3.4 * nrows))
    axes = np.array(axes).reshape(-1)
    for i, lab in enumerate(valid):
        ax = axes[i]
        x, y, score = curves[lab]
        ax.plot(x, y, lw=1.6)
        if diag:
            ax.plot([0, 1], [0, 1], ls="--", lw=1.0, color="gray", alpha=0.6)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        ax.set_title(lab if score is None else f"{lab} ({score:.3f})")
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_grid_calibration(
    title: str,
    labels: Sequence[str],
    cal: Dict[str, Tuple[np.ndarray, np.ndarray, Optional[float]]],
    out_path: Path,
) -> None:
    sns.set_theme(style="whitegrid")
    # Only plot labels that have actual calibration data
    valid = [l for l in labels if l in cal and cal[l][0].size > 0]
    n = len(valid)
    if n == 0:
        return
    ncols = 4
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(4.2 * ncols, 3.4 * nrows))
    axes = np.array(axes).reshape(-1)
    for i, lab in enumerate(valid):
        ax = axes[i]
        frac_pos, mean_pred, ece = cal[lab]
        ax.plot([0, 1], [0, 1], ls="--", lw=1.0, color="gray", alpha=0.6)
        ax.plot(mean_pred, frac_pos, marker="o", lw=1.4)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Mean predicted")
        ax.set_ylabel("Fraction positive")
        ax.set_title(lab if ece is None else f"{lab} (ECE={ece:.3f})")
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def write_cohort_summary(df: pd.DataFrame, out_dir: Path, tag: str) -> None:
    out_dir = ensure_dir(out_dir)
    plots = ensure_dir(out_dir / "plots")
    df2 = df.copy()
    df2["AgeBand"] = df2["PatientAge"].map(age_to_band)

    n_total = len(df2)

    def bar(col: str, fname: str, title: str) -> None:
        series = df2[col].fillna("unknown").astype(str)
        if col == "AgeBand":
            order = [b for b in AGE_ORDER if b in series.values]
            vc = series.value_counts().reindex(order).dropna()
        else:
            vc = series.value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(10, 5))
        # Use ax.bar to preserve chronological order for age bands
        bars = ax.bar(range(len(vc)), vc.values, color="#4C72B0", width=0.6)
        ax.set_xticks(range(len(vc)))
        ax.set_xticklabels(vc.index.tolist(), rotation=45, ha="right")
        ax.set_title(f"{title}, total of {n_total:,} frontal X-ray images")
        ax.set_xlabel(col)
        ax.set_ylabel("Count of frontal X-ray images")
        ax.bar_label(bars, fmt="%d", padding=3, fontsize=9)
        ax.set_ylim(top=ax.get_ylim()[1] * 1.10)
        fig.tight_layout()
        fig.savefig(plots / fname, dpi=200)
        plt.close(fig)

    bar("PatientSex", "sex_distribution.png", f"Sex distribution ({tag})")
    bar("AgeBand", "age_band_distribution.png", f"Age band distribution ({tag})")
    bar("ViewPosition", "view_distribution.png", f"View distribution ({tag})")
    bar("Manufacturer", "manufacturer_distribution.png", f"Manufacturer distribution ({tag})")

    rows = []
    for lab in ID_LABELS:
        if lab not in df2.columns:
            continue
        y = df2[lab].astype(float).fillna(np.nan).to_numpy()
        rows.append({
            "label": lab,
            "n": int(np.sum(~np.isnan(y))),
            "pos": int(np.sum(y == 1)),
            "neg": int(np.sum(y == 0)),
            "uncertain": int(np.sum(y == -1)),
        })
    prev = pd.DataFrame(rows)
    prev["pos_rate"] = prev["pos"] / prev["n"].clip(lower=1)
    prev.to_csv(out_dir / "cohort_label_counts.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.barplot(data=prev.sort_values("pos_rate", ascending=False), x="label", y="pos_rate", ax=ax, color="#DD8452")
    ax.set_title(f"Label prevalence (positive rate) ({tag})")
    ax.set_xlabel("Label")
    ax.set_ylabel("Positive rate")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(plots / "label_prevalence.png", dpi=200)
    plt.close(fig)


def eval_policy(
    *,
    df: pd.DataFrame,
    probs: np.ndarray,
    model_pathologies: Sequence[str],
    label_policy: str,
    out_dir: Path,
    label_map: Dict[str, int],
    model_name: str,
) -> Dict[str, Any]:
    out_dir = ensure_dir(out_dir)
    plots = ensure_dir(out_dir / "plots")

    per_label: Dict[str, Any] = {}
    roc_curves: Dict[str, Tuple[np.ndarray, np.ndarray, Optional[float]]] = {}
    pr_curves: Dict[str, Tuple[np.ndarray, np.ndarray, Optional[float]]] = {}
    cal: Dict[str, Tuple[np.ndarray, np.ndarray, Optional[float]]] = {}

    labels = list(label_map.keys())

    for lab, p_idx in label_map.items():
        if lab not in df.columns:
            continue
        y_raw = df[lab].astype(float).fillna(np.nan).to_numpy()
        valid_mask = ~np.isnan(y_raw)
        y_raw = y_raw[valid_mask]
        p_sub = probs[valid_mask, p_idx]
        
        mask, y01 = apply_label_policy(y_raw, label_policy)
        y = y01[mask]
        p = np.clip(p_sub[mask].astype(np.float64), 0.0, 1.0)

        m = binary_metrics(y, p)
        m["model_pathology"] = model_pathologies[p_idx]
        per_label[lab] = m

        if m["auroc"] is not None:
            fpr, tpr, _ = roc_curve(y, p)
            roc_curves[lab] = (fpr, tpr, m["auroc"])
        else:
            roc_curves[lab] = (np.array([]), np.array([]), None)

        if m["auprc_ap"] is not None:
            prec, rec, _ = precision_recall_curve(y, p)
            pr_curves[lab] = (rec, prec, m["auprc_ap"])
        else:
            pr_curves[lab] = (np.array([]), np.array([]), None)

        try:
            frac_pos, mean_pred = calibration_curve(y, p, n_bins=10, strategy="uniform")
        except Exception:
            frac_pos, mean_pred = np.array([]), np.array([])
        cal[lab] = (frac_pos, mean_pred, m.get("ece_10bin"))

    aurocs = [v["auroc"] for v in per_label.values() if v.get("auroc") is not None]
    aps = [v["auprc_ap"] for v in per_label.values() if v.get("auprc_ap") is not None]
    briers = [v["brier"] for v in per_label.values() if v.get("brier") is not None]
    eces = [v["ece_10bin"] for v in per_label.values() if v.get("ece_10bin") is not None]

    summary = {
        "model": model_name,
        "label_policy": label_policy,
        "n_images": int(len(df)),
        "n_labels_evaluated": int(len(per_label)),
        "macro_auroc": float(np.mean(aurocs)) if aurocs else None,
        "macro_auprc_ap": float(np.mean(aps)) if aps else None,
        "macro_brier": float(np.mean(briers)) if briers else None,
        "macro_ece_10bin": float(np.mean(eces)) if eces else None,
    }

    json_dump(out_dir / "metrics.json", {"summary": summary, "per_label": per_label})
    pd.DataFrame([summary]).to_csv(out_dir / "metrics_summary.csv", index=False)
    
    if per_label:
        pd.DataFrame([
            {
                "label": lab,
                "model_pathology": m["model_pathology"],
                "n": m["n"],
                "pos": m["pos"],
                "neg": m["neg"],
                "prevalence": m["prevalence"],
                "auroc": m["auroc"],
                "auprc_ap": m["auprc_ap"],
                "brier": m["brier"],
                "ece_10bin": m["ece_10bin"],
            }
            for lab, m in per_label.items()
        ]).to_csv(out_dir / "metrics_per_label.csv", index=False)

    plot_grid_curves(
        f"ROC curves ({model_name}, {label_policy})",
        labels,
        roc_curves,
        "False positive rate",
        "True positive rate",
        True,
        plots / "roc_grid.png",
    )
    plot_grid_curves(
        f"PR curves ({model_name}, {label_policy})",
        labels,
        pr_curves,
        "Recall",
        "Precision",
        False,
        plots / "pr_grid.png",
    )
    plot_grid_calibration(
        f"Calibration ({model_name}, {label_policy})",
        labels,
        cal,
        plots / "calibration_grid.png",
    )

    return {"summary": summary, "per_label": per_label}


def subgroup_metrics(
    *,
    df: pd.DataFrame,
    probs: np.ndarray,
    model_pathologies: Sequence[str],
    label_policy: str,
    label_map: Dict[str, int],
    group_col: str,
    out_csv: Path,
) -> None:
    rows: List[Dict[str, Any]] = []
    for g, df_g in df.groupby(group_col, dropna=False):
        idx = df_g.index.to_numpy()
        for lab, p_idx in label_map.items():
            if lab not in df_g.columns:
                continue
            y_raw = df_g[lab].astype(float).fillna(np.nan).to_numpy()
            valid_mask = ~np.isnan(y_raw)
            y_raw = y_raw[valid_mask]
            
            mask, y01 = apply_label_policy(y_raw, label_policy)
            y = y01[mask]
            p = np.clip(probs[idx, p_idx][valid_mask][mask].astype(np.float64), 0.0, 1.0)
            m = binary_metrics(y, p)
            rows.append({
                "grouping": group_col,
                "group_value": str(g),
                "label": lab,
                "model_pathology": model_pathologies[p_idx],
                "n": m["n"],
                "pos": m["pos"],
                "neg": m["neg"],
                "prevalence": m["prevalence"],
                "auroc": m["auroc"],
                "auprc_ap": m["auprc_ap"],
                "brier": m["brier"],
                "ece_10bin": m["ece_10bin"],
            })
    if rows:
        pd.DataFrame(rows).to_csv(out_csv, index=False)


class RealImageDatasetWrapper(tud.Dataset):
    """Reads real images from torchxrayvision and resizes to target."""
    def __init__(self, ds: tud.Dataset, img_size: int):
        self.ds = ds
        self.img_size = img_size

    def __len__(self) -> int:
        return len(self.ds)

    def __getitem__(self, idx: int) -> Tuple[int, torch.Tensor]:
        try:
            item = self.ds[idx]
        except Exception as e:
            print(f"Error loading image {idx}: {e}")
            img = np.zeros((1, self.img_size, self.img_size), dtype=np.float32)
            return int(idx), torch.from_numpy(img)
            
        img = item['img'] # Shape: (1, H, W)

            
        return int(idx), torch.from_numpy(img).float()


def get_metadata_df(d_nih, N: int) -> pd.DataFrame:
    metadata = []
    for idx in range(N):
        d_idx = d_nih.csv.iloc[idx]
        patientid = str(d_idx.get("patientid", "unknown"))
        sex = "unknown"
        if "sex_male" in d_idx and d_idx["sex_male"] == 1:
            sex = "M"
        elif "sex_female" in d_idx and d_idx["sex_female"] == 1:
            sex = "F"
        
        age = d_idx.get("age_years", np.nan)
        view = d_idx.get("view", "unknown")
        
        ds_name = "NIH_Dataset"
        
        meta = {
            "PatientID": patientid,
            "PatientSex": sex,
            "PatientAge": age,
            "ViewPosition": view,
            "Manufacturer": ds_name
        }
        
        labels_vector = d_nih.labels[idx]
        for lab_idx, lab_name in enumerate(d_nih.pathologies):
            meta[lab_name] = labels_vector[lab_idx]
            
        metadata.append(meta)
    
    return pd.DataFrame(metadata)


def run_one_model(
    *,
    model_name: str,
    df: pd.DataFrame,
    ds_wrapper: tud.Dataset,
    out_dir: Path,
    cache_dir: Path,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    img_size = get_input_size(model_name)

    model = load_xrv_model(model_name, cache_dir, device)
    pathologies = list(getattr(model, "pathologies", []))
    if not pathologies:
        raise RuntimeError(f"No pathologies for model {model_name}")

    label_map = resolve_label_map(pathologies)

    out_dir = ensure_dir(out_dir)
    json_dump(out_dir / "label_map.json", {
        "model": model_name,
        "model_pathologies": pathologies,
        "id_to_model_index": label_map,
        "id_labels_evaluated": list(label_map.keys()),
    })

    loader = tud.DataLoader(ds_wrapper, batch_size=int(batch_size), shuffle=False, num_workers=4)

    probs = np.zeros((len(df), len(pathologies)), dtype=np.float32)
    infer_t0 = time.perf_counter()
    with torch.no_grad():
        for idxs, xb in loader:
            xb = xb.to(device, memory_format=torch.channels_last)
            out = model(xb)
            out_np = np.clip(out.detach().cpu().numpy().astype(np.float32), 0.0, 1.0)
            probs[idxs.numpy(), :] = out_np
    infer_t1 = time.perf_counter()

    # raw predictions
    pred_df = df.copy()
    for i, p in enumerate(pathologies):
        pred_df[f"pred__{p}"] = probs[:, i]
    pred_df.to_csv(out_dir / "predictions_raw.csv", index=False)

    policy_summaries: Dict[str, Any] = {}
    for policy in ("ignore_uncertain", "u0"):
        pol = ensure_dir(out_dir / f"eval_{policy}")
        res = eval_policy(
            df=df,
            probs=probs,
            model_pathologies=pathologies,
            label_policy=policy,
            out_dir=pol,
            label_map=label_map,
            model_name=model_name,
        )
        policy_summaries[policy] = res["summary"]

        df_sg = df.copy()
        df_sg["AgeBand"] = df_sg["PatientAge"].map(age_to_band)

        subgroup_metrics(
            df=df_sg,
            probs=probs,
            model_pathologies=pathologies,
            label_policy=policy,
            label_map=label_map,
            group_col="PatientSex",
            out_csv=pol / "metrics_by_sex.csv",
        )
        subgroup_metrics(
            df=df_sg,
            probs=probs,
            model_pathologies=pathologies,
            label_policy=policy,
            label_map=label_map,
            group_col="AgeBand",
            out_csv=pol / "metrics_by_age_band.csv",
        )
        subgroup_metrics(
            df=df_sg,
            probs=probs,
            model_pathologies=pathologies,
            label_policy=policy,
            label_map=label_map,
            group_col="ViewPosition",
            out_csv=pol / "metrics_by_view.csv",
        )

    t1 = time.perf_counter()
    json_dump(out_dir / "run_info.json", {
        "model": model_name,
        "img_size": int(img_size),
        "device": str(device),
        "batch_size": int(batch_size),
        "n_images": int(len(df)),
        "n_model_pathologies": int(len(pathologies)),
        "n_id_labels_evaluated": int(len(label_map)),
        "timing_seconds": {
            "total": float(t1 - t0),
            "inference": float(infer_t1 - infer_t0),
        },
    })

    return {
        "model": model_name,
        "n_images": int(len(df)),
        "labels_evaluated": list(label_map.keys()),
        "policy_summaries": policy_summaries,
    }


def write_comparison(results: List[Dict[str, Any]], out_dir: Path) -> None:
    out_dir = ensure_dir(out_dir)
    plots = ensure_dir(out_dir / "plots")

    cov_rows = []
    for r in results:
        have = set(r["labels_evaluated"])
        cov_rows.append({"model": r["model"], **{lab: (1 if lab in have else 0) for lab in ID_LABELS}})
    pd.DataFrame(cov_rows).to_csv(out_dir / "label_coverage.csv", index=False)

    for policy in ("ignore_uncertain", "u0"):
        rows = []
        for r in results:
            s = r["policy_summaries"].get(policy, {})
            rows.append({
                "model": r["model"],
                "n_images": r["n_images"],
                "n_labels_evaluated": s.get("n_labels_evaluated"),
                "macro_auroc": s.get("macro_auroc"),
                "macro_auprc_ap": s.get("macro_auprc_ap"),
                "macro_brier": s.get("macro_brier"),
                "macro_ece_10bin": s.get("macro_ece_10bin"),
            })
        df_sum = pd.DataFrame(rows).sort_values("macro_auroc", ascending=False, na_position="last")
        df_sum.to_csv(out_dir / f"summary_{policy}.csv", index=False)

        fig, ax = plt.subplots(figsize=(12, 4))
        sns.barplot(data=df_sum, x="model", y="macro_auroc", ax=ax, color="#4C72B0")
        ax.set_title(f"Macro AUROC by model ({policy})")
        ax.set_xlabel("Model")
        ax.set_ylabel("Macro AUROC")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(plots / f"macro_auroc_{policy}.png", dpi=200)
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run ID benchmark (NIH dataset).")
    p.add_argument("--n", type=int, default=-1, help="Number of images per dataset; <=0 means ALL")
    p.add_argument("--out-root", default="research/results_id")
    p.add_argument("--cache-dir", default="research/cache/torchxrayvision")
    p.add_argument("--device", default="cpu")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    p.add_argument("--tag", default="full_frontal_all")
    p.add_argument("--imgpath", default="research/datasets/nih-chest-xrays")
    p.add_argument("--csvpath", default="research/datasets/nih-chest-xrays/Data_Entry_2017.csv")
    return p.parse_args()


def load_existing_result(model_out: Path, model_name: str) -> Dict[str, Any]:
    lm_path = model_out / "label_map.json"
    labels: List[str] = []
    if lm_path.exists():
        try:
            lm = json.loads(lm_path.read_text(encoding="utf-8"))
            labels = list(lm.get("id_labels_evaluated", []) or [])
        except Exception:
            labels = []

    policy_summaries: Dict[str, Any] = {}
    for policy in ("ignore_uncertain", "u0"):
        mp = model_out / f"eval_{policy}" / "metrics.json"
        if not mp.exists():
            continue
        try:
            mj = json.loads(mp.read_text(encoding="utf-8"))
            policy_summaries[policy] = mj.get("summary", {})
        except Exception:
            policy_summaries[policy] = {}

    n_images = 0
    for s in policy_summaries.values():
        if isinstance(s, dict) and "n_images" in s:
            try:
                n_images = int(s["n_images"])
                break
            except Exception:
                pass

    return {
        "model": model_name,
        "n_images": int(n_images),
        "labels_evaluated": labels,
        "policy_summaries": policy_summaries,
    }


class NIH_Dataset_Fixed(xrv.datasets.NIH_Dataset):
    def __init__(self, *args, **kwargs):
        self.img_size = kwargs.pop('img_size', 224)
        super().__init__(*args, **kwargs)
        print("Indexing image paths...")
        self.imgid_to_path = {}
        for p in Path(self.imgpath).rglob("*.png"):
            self.imgid_to_path[p.name] = str(p)
            
    def __getitem__(self, idx):
        sample = {}
        sample["idx"] = idx
        sample["lab"] = self.labels[idx]

        imgid = self.csv['Image Index'].iloc[idx]
        if imgid in self.imgid_to_path:
            img_path = self.imgid_to_path[imgid]
        else:
            import os
            img_path = os.path.join(self.imgpath, imgid)
            
        import PIL.Image
        try:
            pil_img = PIL.Image.open(img_path).convert('L')
            if pil_img.size[0] != self.img_size or pil_img.size[1] != self.img_size:
                pil_img = pil_img.resize((self.img_size, self.img_size), PIL.Image.Resampling.BILINEAR)
            img = np.array(pil_img)
        except Exception:
            img = np.zeros((self.img_size, self.img_size), dtype=np.uint8)

        sample["img"] = xrv.datasets.normalize(img, maxval=255, reshape=True)

        if self.pathology_masks:
            sample["pathology_masks"] = self.get_mask_dict(imgid, sample["img"].shape[2])

        if self.transform is not None:
            sample = xrv.datasets.apply_transforms(sample, self.transform)
        if self.data_aug is not None:
            sample = xrv.datasets.apply_transforms(sample, self.data_aug)

        return sample

def stratified_sample_indices(labels_matrix: np.ndarray, n_sample: int, seed: int = 42) -> List[int]:
    """Sample indices for even label coverage in multi-label setting."""
    rng = np.random.default_rng(seed)
    n_total, n_labels = labels_matrix.shape
    selected: set = set()

    # Pick equal quota of positive samples per label
    per_label = max(1, n_sample // n_labels)
    for lab_idx in range(n_labels):
        pos = np.where(labels_matrix[:, lab_idx] == 1)[0]
        if len(pos) == 0:
            continue
        chosen = rng.choice(pos, size=min(per_label, len(pos)), replace=False)
        selected.update(chosen.tolist())

    # Fill remaining budget with random unselected images
    if len(selected) < n_sample:
        remaining = list(set(range(n_total)) - selected)
        n_fill = min(n_sample - len(selected), len(remaining))
        selected.update(rng.choice(remaining, size=n_fill, replace=False).tolist())

    # Trim if over budget due to rounding
    indices = sorted(selected)
    if len(indices) > n_sample:
        indices = sorted(rng.choice(indices, size=n_sample, replace=False).tolist())

    return indices


def subsample_dataset(ds, indices: List[int]) -> None:
    """In-place subsample a torchxrayvision dataset by row indices."""
    ds.csv = ds.csv.iloc[indices].reset_index(drop=True)
    ds.labels = ds.labels[indices]


def main() -> int:
    args = parse_args()
    out_root = Path(args.out_root)
    cache_dir = Path(args.cache_dir)
    tag = str(args.tag).strip() or "run"
    device = torch.device(args.device)

    # Determine unique image sizes needed across all models
    size_to_models: Dict[int, List[str]] = {}
    for m in args.models:
        s = get_input_size(m)
        size_to_models.setdefault(s, []).append(m)

    # Load dataset once at 224 for metadata extraction, then cache per size
    first_size = list(size_to_models.keys())[0]
    print(f"Loading NIH dataset (img_size={first_size})...")
    ds_cache: Dict[int, NIH_Dataset_Fixed] = {}
    d_first = NIH_Dataset_Fixed(
        imgpath=args.imgpath,
        csvpath=args.csvpath,
        views=["PA", "AP"],
        unique_patients=False,
        img_size=first_size,
    )
    xrv.datasets.relabel_dataset(xrv.datasets.default_pathologies, d_first)

    n_req = int(args.n)
    sample_indices: Optional[List[int]] = None
    if n_req > 0:
        # Stratified multi-label sampling for even label coverage
        sample_indices = stratified_sample_indices(d_first.labels, n_req, seed=42)
        subsample_dataset(d_first, sample_indices)
        print(f"Stratified sample: {len(sample_indices)} images selected")

    ds_cache[first_size] = d_first
    df = get_metadata_df(d_first, len(d_first))
    print(f"Total images to evaluate: {len(d_first)}")

    comp = ensure_dir(out_root / "comparison" / tag)
    write_cohort_summary(df, comp, tag)
    json_dump(comp / "run_environment.json", {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchxrayvision": getattr(xrv, "__version__", "unknown"),
        "n_images": int(len(df)),
        "models": list(args.models),
    })

    results: List[Dict[str, Any]] = []
    for model_name in args.models:
        model_out = ensure_dir(out_root / model_name / tag)

        if (model_out / 'run_info.json').exists() and (model_out / 'predictions_raw.csv').exists() and (model_out / 'eval_u0' / 'metrics.json').exists() and (model_out / 'eval_ignore_uncertain' / 'metrics.json').exists():
            print(f"[{model_name}] already computed; skipping.", flush=True)
            results.append(load_existing_result(model_out, model_name))
            continue

        img_size = get_input_size(model_name)

        # Create dataset at the required resolution if not cached
        if img_size not in ds_cache:
            print(f"Loading NIH dataset (img_size={img_size})...")
            d_new = NIH_Dataset_Fixed(
                imgpath=args.imgpath,
                csvpath=args.csvpath,
                views=["PA", "AP"],
                unique_patients=False,
                img_size=img_size,
            )
            xrv.datasets.relabel_dataset(xrv.datasets.default_pathologies, d_new)
            if sample_indices is not None:
                subsample_dataset(d_new, sample_indices)
            ds_cache[img_size] = d_new

        d_nih = ds_cache[img_size]
        print(f"[{model_name}] running on {len(df)} images (img_size={img_size})...", flush=True)
        ds_wrapper = RealImageDatasetWrapper(d_nih, img_size)

        results.append(run_one_model(
            model_name=model_name,
            df=df,
            ds_wrapper=ds_wrapper,
            out_dir=model_out,
            cache_dir=cache_dir,
            device=device,
            batch_size=int(args.batch_size),
        ))

    write_comparison(results, comp)
    json_dump(comp / "comparison_index.json", {"tag": tag, "models": results})
    print(f"Done. Results in: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())