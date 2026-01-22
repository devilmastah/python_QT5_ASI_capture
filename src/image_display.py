import numpy as np
from PyQt5 import QtGui


def gray16_to_qimage_bytes(img16: np.ndarray):
    if img16.dtype != np.uint16:
        img16 = img16.astype(np.uint16, copy=False)

    if not img16.flags["C_CONTIGUOUS"]:
        img16 = np.ascontiguousarray(img16)

    h, w = img16.shape
    bytes_per_line = w * 2

    buf = img16.tobytes()

    fmt16 = getattr(QtGui.QImage, "Format_Grayscale16", None)
    if fmt16 is None:
        return None, buf

    qimg = QtGui.QImage(buf, w, h, bytes_per_line, fmt16)
    return qimg, buf


def gray16_to_qimage_8bit_preview(img16: np.ndarray):
    if img16.dtype != np.uint16:
        img16 = img16.astype(np.uint16, copy=False)

    if not img16.flags["C_CONTIGUOUS"]:
        img16 = np.ascontiguousarray(img16)

    h, w = img16.shape

    img8 = (img16 >> 4).astype(np.uint8, copy=False)  # 12 bit to 8 bit preview
    buf = img8.tobytes()

    qimg = QtGui.QImage(buf, w, h, w, QtGui.QImage.Format_Grayscale8)
    return qimg, buf
