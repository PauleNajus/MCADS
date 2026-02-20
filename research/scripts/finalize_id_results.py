#!/usr/bin/env python3
"""Finalize ID evaluation results (merged TorchXRayVision datasets).

This script reads the raw predictions output by evaluate_id_models.py,
computes confidence intervals for binary metrics using bootstrapping,
and outputs a comprehensive set of plots and tables under
`research/results_id/comparison/<tag>`.

Usage:
  python finalize_id_results.py --tag full_frontal_all
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import seaborn as sns
from joblib import Parallel, delayed
from sklearn.metrics import average_precision_score, roc_auc_score
from tqdm import tqdm

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torchxrayvision as xrv


ID_LABELS: Tuple[str, ...] = tuple(xrv.datasets.default_pathologies)

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def bootstrap_metric(y_true: np.ndarray, y_prob: np.ndarray, metric_fn, n_bootstraps: int = 1000, seed: int = 42) -> Tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    scores = []
    
    for _ in range(n_bootstraps):
        idx = rng.choice(n, n, replace=True)
        y_t, y_p = y_true[idx], y_prob[idx]
        
        # metric needs both positive and negative samples
        if np.sum(y_t) > 0 and np.sum(y_t == 0) > 0:
            try:
                score = metric_fn(y_t, y_p)
                scores.append(score)
            except Exception:
                pass
                
    if not scores:
        return float('nan'), float('nan'), float('nan')
        
    scores = np.array(scores)
    return float(np.mean(scores)), float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))


def process_model_label_bootstrap(
    model: str, 
    label: str, 
    policy: str,
    y_raw: np.ndarray, 
    probs: np.ndarray,
    n_bootstraps: int
) -> Dict[str, Any]:
    
    if policy == "u0":
        y = y_raw.copy()
        y[y == -1] = 0
        mask = np.isin(y, [0, 1])
        y = y[mask]
        p = probs[mask]
    elif policy == "ignore_uncertain":
        mask = np.isin(y_raw, [0, 1])
        y = y_raw[mask]
        p = probs[mask]
    else:
        raise ValueError(f"Unknown policy {policy}")
        
    if len(np.unique(y)) < 2:
        return {
            "model": model, "label": label, "policy": policy,
            "auroc": float('nan'), "auroc_lb": float('nan'), "auroc_ub": float('nan'),
            "auprc": float('nan'), "auprc_lb": float('nan'), "auprc_ub": float('nan')
        }
        
    auroc_mean, auroc_lb, auroc_ub = bootstrap_metric(y, p, roc_auc_score, n_bootstraps=n_bootstraps)
    auprc_mean, auprc_lb, auprc_ub = bootstrap_metric(y, p, average_precision_score, n_bootstraps=n_bootstraps)
    
    return {
        "model": model, "label": label, "policy": policy,
        "auroc": auroc_mean, "auroc_lb": auroc_lb, "auroc_ub": auroc_ub,
        "auprc": auprc_mean, "auprc_lb": auprc_lb, "auprc_ub": auprc_ub
    }


def finalize_results(tag: str, in_dir: Path, out_dir: Path, n_bootstraps: int, n_jobs: int):
    comp_dir = ensure_dir(out_dir / "comparison" / tag)
    plots_dir = ensure_dir(comp_dir / "plots")
    
    # Check if we have models in this tag
    models = [p.name for p in (in_dir).iterdir() if p.is_dir() and p.name != "comparison" and (p / tag).exists()]
    print(f"Found {len(models)} models for tag {tag}: {models}")
    
    if not models:
        print("No models found. Exiting.")
        return
        
    # Process bootstrap metrics
    print(f"Computing bootstrap CI ({n_bootstraps} iterations) using {n_jobs} cores...")
    
    tasks = []
    
    for model in models:
        model_tag_dir = in_dir / model / tag
        
        preds_file = model_tag_dir / "predictions_raw.csv"
        if not preds_file.exists():
            continue
            
        df = pd.read_csv(preds_file)
        
        # label mapping
        label_map_file = model_tag_dir / "label_map.json"
        if not label_map_file.exists():
            continue
            
        with open(label_map_file, 'r') as f:
            lmap = json.load(f)["brax_to_model_index"]
            
        # Get patholgies
        with open(model_tag_dir / "run_info.json", 'r') as f:
            pathologies = json.load(f)["n_model_pathologies"]
            
        for policy in ["u0", "ignore_uncertain"]:
            for lab, p_idx in lmap.items():
                if lab not in df.columns:
                    continue
                    
                model_col = f"pred__{list(lmap.keys())[list(lmap.values()).index(p_idx)]}"
                # The pred column is typically named pred__<pathology_name_in_model>
                # Let's try to find the exact column name
                pred_cols = [c for c in df.columns if c.startswith("pred__")]
                model_col = pred_cols[p_idx]
                
                y_raw = df[lab].astype(float).fillna(np.nan).to_numpy()
                valid_mask = ~np.isnan(y_raw)
                
                y_raw = y_raw[valid_mask]
                probs = df[model_col].to_numpy()[valid_mask]
                
                tasks.append(delayed(process_model_label_bootstrap)(
                    model, lab, policy, y_raw, probs, n_bootstraps
                ))
                
    if not tasks:
        print("No tasks generated. Exiting.")
        return
        
    results = Parallel(n_jobs=n_jobs)(tqdm(tasks, desc="Bootstrapping"))
    
    # Save bootstrap results
    res_df = pd.DataFrame(results)
    for policy in ["u0", "ignore_uncertain"]:
        pol_df = res_df[res_df["policy"] == policy].drop(columns=["policy"])
        pol_df.to_csv(comp_dir / f"bootstrap_metrics_{policy}.csv", index=False)
        
        # Plot macroscopic results
        macro_df = pol_df.groupby("model").agg({
            "auroc": "mean",
            "auprc": "mean"
        }).reset_index()
        
        macro_df.to_csv(comp_dir / f"summary_{policy}.csv", index=False)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(data=macro_df.sort_values("auroc", ascending=False), x="model", y="auroc", ax=ax, color="#4C72B0")
        ax.set_title(f"Macro AUROC by model ({policy})")
        ax.set_xlabel("Model")
        ax.set_ylabel("Macro AUROC")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(plots_dir / f"macro_auroc_{policy}.png", dpi=200)
        plt.close(fig)
        
    print(f"Results finalized in {comp_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="full_frontal_all")
    parser.add_argument("--in-root", default="research/results_id")
    parser.add_argument("--out-root", default="research/results_id")
    parser.add_argument("--n-bootstraps", type=int, default=1000)
    parser.add_argument("--n-jobs", type=int, default=-1)
    args = parser.parse_args()
    
    finalize_results(
        tag=args.tag,
        in_dir=Path(args.in_root),
        out_dir=Path(args.out_root),
        n_bootstraps=args.n_bootstraps,
        n_jobs=args.n_jobs
    )


if __name__ == "__main__":
    main()
