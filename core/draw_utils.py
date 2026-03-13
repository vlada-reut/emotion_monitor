from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


@lru_cache(maxsize=16)
def _get_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def annotate_frame(frame: np.ndarray, annotations: Iterable[dict]) -> np.ndarray:
    """
    annotations = [
        {
            "bbox": (x1, y1, x2, y2),
            "label": "жен | взрослый | радость",
            "color": (0, 255, 0),
        }
    ]
    """
    output = frame.copy()

    for ann in annotations:
        x1, y1, x2, y2 = map(int, ann["bbox"])
        color = ann.get("color", (0, 255, 0))
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)

    rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil_img)
    font = _get_font(18)

    for ann in annotations:
        x1, y1, x2, y2 = map(int, ann["bbox"])
        label = str(ann.get("label", "")).strip()
        if not label:
            continue

        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        text_w = right - left
        text_h = bottom - top

        tx = max(0, x1)
        ty = max(0, y1 - text_h - 12)

        draw.rounded_rectangle(
            (tx, ty, tx + text_w + 12, ty + text_h + 8),
            radius=6,
            fill=(0, 0, 0),
        )
        draw.text((tx + 6, ty + 4), label, font=font, fill=(255, 255, 255))

    return cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)
