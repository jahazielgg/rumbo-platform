"""BuildingCV (ResNet34-UNet, CubiCasa5K) backend with multi-scale tiled inference.

The published model was trained on 512x512 letterboxed renders where walls are roughly
6-10 px thick. Hospital plans are large; letterboxing a 1500 px image makes walls
sub-pixel and columns vanish. We therefore run the network at several effective
resolutions and average class probabilities:

1. a global letterboxed pass for context;
2. overlapping 512 px tiles at a zoom chosen so walls look training-like;
3. an extra finer tile pass when the plan is large, to recover small elements.

Everything here is optional at import time so the geometry pipeline stays torch-free.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from ..contracts import RasterInput, Scale, StructuralMasks
from .classical import dark_mask, estimate_stroke_thickness

TARGET_WALL_PX = 8.0
TILE = 512
OVERLAP = 96
# ImageNet statistics used by the BuildingCV training pipeline. Defined here so the
# perceiver never imports `buildingcv.data`, which drags in cairosvg/libcairo.
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class BuildingCvPerceiver:
    name = "buildingcv-resnet34-unet"

    def __init__(self, run_dir: str | Path | None = None, device: str = "cpu"):
        import torch
        import yaml
        from buildingcv.checkpoint import load_inference_checkpoint
        from buildingcv.labels import CLASS_TO_ID
        from buildingcv.model import build_model

        run_dir = Path(run_dir or os.getenv("BUILDINGCV_RUN_DIR", "/opt/buildingcv/weights"))
        with (run_dir / "config.yaml").open() as fh:
            self.cfg = yaml.safe_load(fh)
        self.device = self._device(device)
        self.model = build_model(encoder_name=self.cfg["model"]["encoder_name"], encoder_weights=None).to(self.device)
        state, self.epoch = load_inference_checkpoint(run_dir / "best.safetensors", self.device)
        self.model.load_state_dict(state)
        self.model.eval()
        self.class_to_id = CLASS_TO_ID
        self.torch = torch

    @staticmethod
    def _device(name: str):
        import torch

        if name == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            if torch.backends.mps.is_available():
                return torch.device("mps")
            return torch.device("cpu")
        return torch.device(name)

    # ---- inference -------------------------------------------------------------------
    def _normalize(self, rgb: np.ndarray):
        arr = rgb.astype(np.float32) / 255.0
        arr = (arr - np.array(IMAGENET_MEAN, dtype=np.float32)) / np.array(IMAGENET_STD, dtype=np.float32)
        return self.torch.from_numpy(arr).permute(2, 0, 1).contiguous()

    def _softmax(self, rgb: np.ndarray) -> np.ndarray:
        """Return CxHxW probabilities for an RGB array whose sides are multiples of 32."""
        with self.torch.no_grad():
            logits = self.model(self._normalize(rgb).unsqueeze(0).to(self.device))
            return self.torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

    def _global_pass(self, image: np.ndarray) -> np.ndarray:
        import cv2

        h, w = image.shape[:2]
        size = int(self.cfg["data"]["image_size"][0])
        factor = min(size / w, size / h)
        inner_w, inner_h = max(32, round(w * factor)), max(32, round(h * factor))
        resized = cv2.resize(image, (inner_w, inner_h), interpolation=cv2.INTER_AREA)
        canvas = np.full((size, size, 3), 128, dtype=np.uint8)
        left, top = (size - inner_w) // 2, (size - inner_h) // 2
        canvas[top : top + inner_h, left : left + inner_w] = resized
        probs = self._softmax(canvas)[:, top : top + inner_h, left : left + inner_w]
        return np.stack([cv2.resize(p, (w, h), interpolation=cv2.INTER_LINEAR) for p in probs])

    def _tiled_pass(self, image: np.ndarray, zoom: float) -> np.ndarray:
        import cv2

        h, w = image.shape[:2]
        zw, zh = max(TILE, int(round(w * zoom))), max(TILE, int(round(h * zoom)))
        zoomed = cv2.resize(image, (zw, zh), interpolation=cv2.INTER_AREA if zoom < 1 else cv2.INTER_CUBIC)
        classes = len(self.class_to_id)
        acc = np.zeros((classes, zh, zw), dtype=np.float32)
        weight = np.zeros((zh, zw), dtype=np.float32)
        window = np.outer(np.hanning(TILE), np.hanning(TILE)).astype(np.float32) + 1e-3
        step = TILE - OVERLAP
        ys = list(range(0, max(1, zh - TILE + 1), step))
        xs = list(range(0, max(1, zw - TILE + 1), step))
        if ys[-1] != zh - TILE:
            ys.append(zh - TILE)
        if xs[-1] != zw - TILE:
            xs.append(zw - TILE)
        for y in ys:
            for x in xs:
                tile = zoomed[y : y + TILE, x : x + TILE]
                probs = self._softmax(tile)
                acc[:, y : y + TILE, x : x + TILE] += probs * window
                weight[y : y + TILE, x : x + TILE] += window
        acc /= weight
        return np.stack([cv2.resize(p, (w, h), interpolation=cv2.INTER_LINEAR) for p in acc])

    def perceive(self, source: RasterInput, scale: Scale | None) -> StructuralMasks:
        image = source.image
        h, w = image.shape[:2]
        # Present walls to the network at a training-like thickness. The drawn stroke
        # thickness is measured on the image itself; the metric scale only bounds it.
        wall_px = estimate_stroke_thickness(dark_mask(image))
        if scale is not None:
            wall_px = float(np.clip(wall_px, scale.px(0.1), scale.px(0.6)))
        zoom = float(np.clip(TARGET_WALL_PX / max(wall_px, 2.0), 0.25, 2.0))

        passes = [self._global_pass(image)]
        weights = [1.0]
        if max(h, w) * zoom > TILE * 0.9:
            passes.append(self._tiled_pass(image, zoom))
            weights.append(2.0)
        probs = sum(p * wgt for p, wgt in zip(passes, weights)) / sum(weights)
        labels = probs.argmax(axis=0)
        ids = self.class_to_id
        return StructuralMasks(
            wall=labels == ids["wall"],
            door=labels == ids["door"],
            window=labels == ids["window"],
            wall_probability=probs[ids["wall"]].astype(np.float32),
            backend=f"{self.name}@x{zoom:.2f}",
        )
