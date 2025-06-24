#!/usr/bin/env python
# coding: utf-8

import os, sys
sys.path.insert(0, "..")
import numpy as np
import argparse
import skimage, skimage.io

import torch
import torch.nn.functional as F
import torchvision, torchvision.transforms

import torchxrayvision as xrv
from pprint import pprint

# ------------------------------------------------------------------
# 1) Change default weights to the ResNet50‐512 model
# ------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('-f', type=str, default="", help='')
parser.add_argument('img_path', type=str)
parser.add_argument(
    '-weights',
    type=str,
    default="resnet50-res512-all",     # ← here: resnet50‐res512
    help='which pretrained weights to load'
)
parser.add_argument('-feats', action='store_true', help='extract features instead of preds')
parser.add_argument('-cuda', action='store_true', help='use CUDA')
parser.add_argument('-resize', action='store_true', help='center‐crop & resize to model input size')

cfg = parser.parse_args()

# ------------------------------------------------------------------
# 2) Load and normalize image
# ------------------------------------------------------------------
img = skimage.io.imread(cfg.img_path)
img = xrv.datasets.normalize(img, 255)

# Ensure we have a single 2D slice
if img.ndim > 2:
    img = img[:, :, 0]
elif img.ndim < 2:
    raise ValueError("Input image must have at least 2 dimensions")

# Add channel dimension
img = img[None, :, :]

# ------------------------------------------------------------------
# 3) Center‐crop & (optionally) resize to 512×512
# ------------------------------------------------------------------
# For ResNet50‐512 the model expects 512×512 inputs
if cfg.resize:
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(512)       # ← here: resize to 512
    ])
else:
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop()
    ])

img = transform(img)

# ------------------------------------------------------------------
# 4) Instantiate ResNet50‐512
# ------------------------------------------------------------------
# You can either call get_model with the name...
model = xrv.models.get_model(cfg.weights)
# ...or directly:
# model = xrv.models.ResNet(weights="resnet50-res512-all")

output = {}
with torch.no_grad():
    # Batchify and move to device
    img_tensor = torch.from_numpy(img).unsqueeze(0)
    if cfg.cuda:
        img_tensor = img_tensor.cuda()
        model = model.cuda()

    # Optional: extract convolutional features
    if cfg.feats:
        feats = model.features(img_tensor)
        feats = F.relu(feats, inplace=True)
        feats = F.adaptive_avg_pool2d(feats, (1, 1))
        output["feats"] = feats.cpu().squeeze().numpy().tolist()

    # Classification predictions
    preds = model(img_tensor).cpu().squeeze().numpy()
    output["preds"] = dict(zip(
        xrv.datasets.default_pathologies,
        preds
    ))

# Print
if cfg.feats:
    pprint(output)
else:
    pprint(output)
