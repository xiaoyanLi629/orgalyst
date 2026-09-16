"""把实例轮廓画到图上（评审/报告用）。"""
import numpy as np
from PIL import Image
from skimage.segmentation import find_boundaries

def overlay(img: np.ndarray, masks: np.ndarray, color=(0, 200, 120), width: int = 2) -> Image.Image:
    base = img if img.ndim == 3 else np.stack([img] * 3, axis=-1)
    base = base.astype(np.uint8).copy()
    b = find_boundaries(masks, mode="thick")
    if width > 2:
        from scipy.ndimage import binary_dilation; b = binary_dilation(b, iterations=width - 2)
    base[b] = color
    return Image.fromarray(base)
