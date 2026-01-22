import os
import time
import numpy as np
import cv2


def save_tiff16(path: str, img16: np.ndarray):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if img16.dtype != np.uint16:
        img16 = img16.astype(np.uint16)
    cv2.imwrite(path, img16)


def build_master_stack(frames: list[np.ndarray], method: str = "median") -> np.ndarray:
    stack = np.stack(frames, axis=0)  # (N, H, W)
    if method == "mean":
        out = np.mean(stack, axis=0)
    else:
        out = np.median(stack, axis=0)
    return np.clip(out, 0, 65535).astype(np.uint16)


def make_master_dark(frames: list[np.ndarray], method: str = "median") -> np.ndarray:
    return build_master_stack(frames, method=method)


def make_master_flat(flat_frames: list[np.ndarray], master_dark: np.ndarray, method: str = "median") -> np.ndarray:
    # Stack the raw flats first
    flat = build_master_stack(flat_frames, method=method).astype(np.int32)

    # Dark-correct the flat (classic: flats must be bias/darkflat/dark corrected or they overcorrect)
    dark = master_dark.astype(np.int32)
    flat_corr = flat - dark
    flat_corr = np.clip(flat_corr, 1, 65535).astype(np.uint16)

    # Normalize to a multiplicative flat (mean = 1.0)
    flat_f = flat_corr.astype(np.float32)
    mean_val = float(np.mean(flat_f))
    if mean_val <= 0.0:
        mean_val = 1.0
    flat_norm = flat_f / mean_val

    return flat_norm.astype(np.float32)  # keep float flat for later application


def save_flat_float(path: str, flat_norm: np.ndarray):
    # store float flat as 32 bit tiff so we keep precision
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, flat_norm.astype(np.float32))


def timestamped_name(prefix: str, ext: str = ".tiff"):
    t = time.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{t}{ext}"
