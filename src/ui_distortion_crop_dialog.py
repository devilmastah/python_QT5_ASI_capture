import numpy as np
from PyQt5 import QtCore, QtWidgets
from settings_manager import SettingsManager


class DistortionWindow(QtWidgets.QDialog):
    changed = QtCore.pyqtSignal()
    request_crop_selection = QtCore.pyqtSignal()

    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Distortion calibration")
        self.setWindowModality(QtCore.Qt.NonModal)
        self.resize(560, 420)
        self.settings = settings

        self._build_ui()
        self._load_from_settings()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.enabled = QtWidgets.QCheckBox("Enable distortion correction")
        layout.addWidget(self.enabled)

        self.k1_label = QtWidgets.QLabel()
        self.k1_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.k1_slider.setMinimum(-1000)
        self.k1_slider.setMaximum(1000)
        self.k1_slider.setSingleStep(1)
        self.k1_slider.setPageStep(25)

        self.k2_label = QtWidgets.QLabel()
        self.k2_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.k2_slider.setMinimum(-1000)
        self.k2_slider.setMaximum(1000)
        self.k2_slider.setSingleStep(1)
        self.k2_slider.setPageStep(25)

        self.k3_label = QtWidgets.QLabel()
        self.k3_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.k3_slider.setMinimum(-1000)
        self.k3_slider.setMaximum(1000)
        self.k3_slider.setSingleStep(1)
        self.k3_slider.setPageStep(25)

        self.zoom_label = QtWidgets.QLabel()
        self.zoom_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.zoom_slider.setMinimum(50)
        self.zoom_slider.setMaximum(200)
        self.zoom_slider.setSingleStep(1)
        self.zoom_slider.setPageStep(5)

        layout.addWidget(self.k1_label)
        layout.addWidget(self.k1_slider)
        layout.addWidget(self.k2_label)
        layout.addWidget(self.k2_slider)
        layout.addWidget(self.k3_label)
        layout.addWidget(self.k3_slider)
        layout.addWidget(self.zoom_label)
        layout.addWidget(self.zoom_slider)

        layout.addSpacing(10)

        crop_group = QtWidgets.QGroupBox("Crop")
        crop_layout = QtWidgets.QVBoxLayout(crop_group)

        self.crop_enabled = QtWidgets.QCheckBox("Enable crop")
        crop_layout.addWidget(self.crop_enabled)

        self.crop_info = QtWidgets.QLabel("No crop set")
        crop_layout.addWidget(self.crop_info)

        self.crop_select_btn = QtWidgets.QPushButton("Select crop region")
        crop_layout.addWidget(self.crop_select_btn)

        layout.addWidget(crop_group)
        layout.addStretch(1)

        self.enabled.stateChanged.connect(self._on_any_change)
        self.k1_slider.valueChanged.connect(self._on_any_change)
        self.k2_slider.valueChanged.connect(self._on_any_change)
        self.k3_slider.valueChanged.connect(self._on_any_change)
        self.zoom_slider.valueChanged.connect(self._on_any_change)

        self.crop_enabled.stateChanged.connect(self._on_crop_toggle)
        self.crop_select_btn.clicked.connect(self.request_crop_selection.emit)

    def _load_from_settings(self):
        d = self.settings.data.get("distortion_manual", {})
        enabled = bool(d.get("enabled", False))
        k1 = float(d.get("k1", 0.0))
        k2 = float(d.get("k2", 0.0))
        k3 = float(d.get("k3", 0.0))
        zoom = float(d.get("zoom", 1.0))

        crop = self.settings.data.get("crop", {})
        crop_enabled = bool(crop.get("enabled", False))
        rect = crop.get("rect", None)

        self.enabled.blockSignals(True)
        self.k1_slider.blockSignals(True)
        self.k2_slider.blockSignals(True)
        self.k3_slider.blockSignals(True)
        self.zoom_slider.blockSignals(True)
        self.crop_enabled.blockSignals(True)

        self.enabled.setChecked(enabled)
        self.k1_slider.setValue(int(np.clip(round(k1 * 1000.0), -1000, 1000)))
        self.k2_slider.setValue(int(np.clip(round(k2 * 1000.0), -1000, 1000)))
        self.k3_slider.setValue(int(np.clip(round(k3 * 1000.0), -1000, 1000)))
        self.zoom_slider.setValue(int(np.clip(round(zoom * 100.0), 50, 200)))
        self.crop_enabled.setChecked(crop_enabled)

        self.enabled.blockSignals(False)
        self.k1_slider.blockSignals(False)
        self.k2_slider.blockSignals(False)
        self.k3_slider.blockSignals(False)
        self.zoom_slider.blockSignals(False)
        self.crop_enabled.blockSignals(False)

        self._refresh_labels()
        self._refresh_crop_info(rect)

    def _refresh_labels(self):
        k1 = self.k1_slider.value() / 1000.0
        k2 = self.k2_slider.value() / 1000.0
        k3 = self.k3_slider.value() / 1000.0
        zoom = self.zoom_slider.value() / 100.0

        self.k1_label.setText(f"k1: {k1:+.3f}")
        self.k2_label.setText(f"k2: {k2:+.3f}")
        self.k3_label.setText(f"k3: {k3:+.3f}")
        self.zoom_label.setText(f"zoom: {zoom:.2f}")

    def _refresh_crop_info(self, rect):
        if not rect or len(rect) != 4:
            self.crop_info.setText("No crop set")
            return
        x0, y0, x1, y1 = rect
        self.crop_info.setText(f"Crop rect: x {x0} to {x1}, y {y0} to {y1}")

    def _on_any_change(self):
        self._refresh_labels()

        d = {
            "enabled": bool(self.enabled.isChecked()),
            "k1": self.k1_slider.value() / 1000.0,
            "k2": self.k2_slider.value() / 1000.0,
            "k3": self.k3_slider.value() / 1000.0,
            "zoom": self.zoom_slider.value() / 100.0,
        }
        self.settings.set("distortion_manual", d)
        self.changed.emit()

    def _on_crop_toggle(self):
        crop = self.settings.data.get("crop", {})
        crop["enabled"] = bool(self.crop_enabled.isChecked())
        if "rect" not in crop:
            crop["rect"] = None
        self.settings.set("crop", crop)
        self.changed.emit()

    def update_crop_rect_display(self):
        crop = self.settings.data.get("crop", {})
        self.crop_enabled.blockSignals(True)
        self.crop_enabled.setChecked(bool(crop.get("enabled", False)))
        self.crop_enabled.blockSignals(False)
        self._refresh_crop_info(crop.get("rect", None))
