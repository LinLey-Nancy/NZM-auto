"""Dynamic property form for one workflow step."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


FIELD_LABELS = {
    "id": "步骤 ID",
    "type": "动作类型",
    "name": "显示名称",
    "enabled": "启用",
    "on_failure": "失败时",
    "template": "模板路径",
    "threshold": "识别阈值",
    "attempts": "识别次数",
    "result_variable": "结果变量",
    "x": "X 坐标",
    "y": "Y 坐标",
    "match_variable": "匹配变量",
    "button": "鼠标按键",
    "count": "点击次数",
    "key": "按键",
    "modifiers": "组合键",
    "text": "输入文本",
    "strategy": "文本策略",
    "interval_ms": "间隔（毫秒）",
    "duration_ms": "等待（毫秒）",
    "sensitive": "敏感内容",
}

CHOICES = {
    "on_failure": (("停止工作流", "stop"), ("继续下一步", "continue")),
    "button": (("左键", "left"), ("右键", "right"), ("中键", "middle")),
    "strategy": (("逐键输入（游戏推荐）", "key_sequence"), ("Maa 直接文本", "direct")),
}


class PropertyEditor(QWidget):
    property_changed = Signal(int, str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step_index = -1
        self._form_host = QWidget()
        self._form = QFormLayout(self._form_host)
        self._form.setContentsMargins(12, 12, 12, 12)
        self._form.setHorizontalSpacing(14)
        self._form.setVerticalSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._form_host)

        title = QLabel("步骤属性")
        title.setObjectName("sectionTitle")
        self._empty = QLabel("选择一个步骤以编辑参数。")
        self._empty.setObjectName("mutedLabel")
        self._empty.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(title)
        layout.addWidget(self._empty)
        layout.addWidget(scroll, 1)
        self.set_step(-1, None)

    def set_step(self, index: int, step: dict[str, Any] | None) -> None:
        self._step_index = index
        while self._form.rowCount():
            self._form.removeRow(0)
        self._empty.setVisible(step is None)
        self._form_host.setVisible(step is not None)
        if step is None:
            return

        ordered = ("id", "type", "name", "enabled", "on_failure")
        keys = [key for key in ordered if key in step]
        keys.extend(key for key in step if key not in ordered)
        for key in keys:
            self._add_field(key, step[key])

    def _add_field(self, key: str, value: Any) -> None:
        label = FIELD_LABELS.get(key, key)
        if key == "type":
            widget = QLabel(str(value))
            widget.setObjectName("mutedLabel")
        elif key in CHOICES:
            widget = QComboBox()
            for text, stored in CHOICES[key]:
                widget.addItem(text, stored)
            selected = widget.findData(value)
            widget.setCurrentIndex(max(0, selected))
            widget.currentIndexChanged.connect(
                lambda _value, control=widget, field=key: self._emit(
                    field, control.currentData()
                )
            )
        elif isinstance(value, bool):
            widget = QCheckBox()
            widget.setChecked(value)
            widget.toggled.connect(lambda checked, field=key: self._emit(field, checked))
        elif isinstance(value, int):
            widget = QSpinBox()
            widget.setRange(0, 1_000_000)
            widget.setValue(value)
            widget.editingFinished.connect(
                lambda control=widget, field=key: self._emit(field, control.value())
            )
        elif isinstance(value, float):
            widget = QDoubleSpinBox()
            widget.setRange(0.0, 1.0)
            widget.setDecimals(3)
            widget.setSingleStep(0.05)
            widget.setValue(value)
            widget.editingFinished.connect(
                lambda control=widget, field=key: self._emit(field, control.value())
            )
        else:
            widget = QLineEdit(self._format_value(value))
            if key == "text":
                widget.setPlaceholderText("输入要发送的文本")
            widget.editingFinished.connect(
                lambda control=widget, field=key, original=value: self._emit(
                    field,
                    self._parse_text(control.text(), original),
                )
            )
        widget.setAccessibleName(label)
        self._form.addRow(f"{label}：", widget)

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _parse_text(text: str, original: Any) -> Any:
        if isinstance(original, list):
            return [item.strip() for item in text.split(",") if item.strip()]
        if original is None:
            return text.strip() or None
        return text

    def _emit(self, field: str, value: object) -> None:
        if self._step_index >= 0:
            self.property_changed.emit(self._step_index, field, value)
