def get_crop_params(settings):
    crop = settings.data.get("crop", {})
    enabled = bool(crop.get("enabled", False))
    rect = crop.get("rect", None)

    if rect is None or not isinstance(rect, (list, tuple)) or len(rect) != 4:
        return False, None

    x0, y0, x1, y1 = [int(v) for v in rect]
    if x1 <= x0 or y1 <= y0:
        return False, None

    return enabled, (x0, y0, x1, y1)


def apply_crop_if_enabled(frame, settings, selecting=False):
    if selecting:
        return frame

    enabled, rect = get_crop_params(settings)
    if not enabled or rect is None:
        return frame

    x0, y0, x1, y1 = rect
    h, w = frame.shape

    x0 = max(0, min(w - 2, x0))
    x1 = max(1, min(w - 1, x1))
    y0 = max(0, min(h - 2, y0))
    y1 = max(1, min(h - 1, y1))

    if x1 <= x0 or y1 <= y0:
        return frame

    return frame[y0:y1, x0:x1]
