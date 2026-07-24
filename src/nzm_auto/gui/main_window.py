"""Main window for the NZM Auto workflow editor."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from nzm_auto.application.input_profiles import INPUT_PROFILES, InputProfileName
from nzm_auto.config.loader import load_config
from nzm_auto.diagnostics.workspace import create_debug_workspace
from nzm_auto.gui.document import STEP_LABELS, WorkflowDocument
from nzm_auto.gui.property_editor import PropertyEditor
from nzm_auto.gui.window_dialog import WindowSelectorDialog
from nzm_auto.gui.worker import WorkflowWorker
from nzm_auto.windowing.discovery import WindowInfo
from nzm_auto.workflow.events import WorkflowEvent
from nzm_auto.workflow.loader import WorkflowV2ConfigError, load_workflow_v2


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.json"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.document = WorkflowDocument()
        self.selected_window: WindowInfo | None = None
        self._thread: QThread | None = None
        self._worker: WorkflowWorker | None = None
        self.setWindowTitle("NZM Auto 工作流编辑器")
        self.resize(1360, 820)
        self.setMinimumSize(1024, 640)
        self._build_actions()
        self._build_toolbar()
        self._build_central()
        self._build_log_dock()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")
        self._refresh_document()

    def _build_actions(self) -> None:
        self.new_action = QAction("新建", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self.new_document)
        self.open_action = QAction("打开", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_document)
        self.save_action = QAction("保存", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save_document)
        self.save_as_action = QAction("另存为", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(lambda: self.save_document(save_as=True))

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()

        self.target_label = QLabel("未选择目标窗口")
        self.target_label.setObjectName("mutedLabel")
        self.target_label.setMinimumWidth(280)
        select_window = QPushButton("选择窗口")
        select_window.clicked.connect(self.choose_window)
        toolbar.addWidget(self.target_label)
        toolbar.addWidget(select_window)
        toolbar.addSeparator()

        toolbar.addWidget(QLabel("输入策略："))
        self.profile_combo = QComboBox()
        for name, profile in INPUT_PROFILES.items():
            label = {
                InputProfileName.BACKGROUND_MESSAGE: "后台消息（兼容性中）",
                InputProfileName.FOREGROUND_COMPATIBLE: "前台兼容（游戏推荐）",
                InputProfileName.DRIVER_INTERCEPTION: "驱动级（需管理员）",
            }[name]
            self.profile_combo.addItem(label, profile)
        self.profile_combo.setCurrentIndex(
            self.profile_combo.findData(
                INPUT_PROFILES[InputProfileName.FOREGROUND_COMPATIBLE]
            )
        )
        toolbar.addWidget(self.profile_combo)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(spacer)
        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_workflow)
        self.run_button = QPushButton("运行工作流")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.run_workflow)
        toolbar.addWidget(self.stop_button)
        toolbar.addWidget(self.run_button)
        self.addToolBar(toolbar)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_palette())
        splitter.addWidget(self._build_steps())
        self.properties = PropertyEditor()
        self.properties.property_changed.connect(self.update_property)
        splitter.addWidget(self.properties)
        splitter.setSizes((230, 420, 610))
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        self.setCentralWidget(splitter)

    def _build_palette(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(12, 12, 8, 12)
        title = QLabel("动作组件")
        title.setObjectName("sectionTitle")
        help_text = QLabel("双击动作，或选择后点击“添加”。")
        help_text.setObjectName("mutedLabel")
        self.palette = QListWidget()
        for step_type, label in STEP_LABELS.items():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, step_type)
            self.palette.addItem(item)
        self.palette.itemDoubleClicked.connect(lambda _item: self.add_selected_action())
        add_button = QPushButton("添加到工作流")
        add_button.clicked.connect(self.add_selected_action)
        layout.addWidget(title)
        layout.addWidget(help_text)
        layout.addWidget(self.palette, 1)
        layout.addWidget(add_button)
        return host

    def _build_steps(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(8, 12, 8, 12)
        title_row = QHBoxLayout()
        title = QLabel("工作流步骤")
        title.setObjectName("sectionTitle")
        self.workflow_name = QLabel()
        self.workflow_name.setObjectName("mutedLabel")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.workflow_name)
        self.step_list = QListWidget()
        self.step_list.setAlternatingRowColors(True)
        self.step_list.currentRowChanged.connect(self.select_step)
        controls = QHBoxLayout()
        for text, callback in (
            ("上移", lambda: self.move_step(-1)),
            ("下移", lambda: self.move_step(1)),
            ("删除", self.remove_step),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(title_row)
        layout.addWidget(self.step_list, 1)
        layout.addLayout(controls)
        return host

    def _build_log_dock(self) -> None:
        dock = QDockWidget("运行日志", self)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setAccessibleName("工作流运行日志")
        dock.setWidget(self.log_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def _refresh_document(self, selected_row: int | None = None) -> None:
        self.workflow_name.setText(self.document.name)
        self.step_list.clear()
        for index, step in enumerate(self.document.steps, start=1):
            enabled = "" if step.get("enabled", True) else "（已禁用）"
            label = STEP_LABELS.get(step.get("type"), str(step.get("type")))
            item = QListWidgetItem(
                f"{index:02d}  {step.get('name', label)}\n      {label}  ·  {step.get('id')} {enabled}"
            )
            item.setToolTip(str(step))
            self.step_list.addItem(item)
        if not self.document.steps:
            empty = QListWidgetItem(
                "还没有步骤\n\n从左侧选择动作并添加，工作流将按从上到下的顺序执行。"
            )
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.step_list.addItem(empty)
        self._update_title()
        if selected_row is not None and self.document.steps:
            self.step_list.setCurrentRow(
                min(max(selected_row, 0), self.step_list.count() - 1)
            )
        elif not self.document.steps:
            self.properties.set_step(-1, None)

    def _update_title(self) -> None:
        marker = " *" if self.document.dirty else ""
        path = self.document.path.name if self.document.path else "未命名"
        self.setWindowTitle(f"{path}{marker} — NZM Auto 工作流编辑器")

    def add_selected_action(self) -> None:
        item = self.palette.currentItem() or self.palette.item(0)
        index = self.document.add_step(item.data(Qt.ItemDataRole.UserRole))
        self._refresh_document(index)

    def select_step(self, row: int) -> None:
        step = self.document.steps[row] if 0 <= row < len(self.document.steps) else None
        self.properties.set_step(row, step)

    def update_property(self, index: int, field: str, value: object) -> None:
        try:
            self.document.update_step(index, field, value)
        except ValueError as error:
            QMessageBox.warning(self, "无法更新属性", str(error))
        self._refresh_document(index)

    def move_step(self, offset: int) -> None:
        row = self.step_list.currentRow()
        if 0 <= row < len(self.document.steps):
            self._refresh_document(self.document.move_step(row, offset))

    def remove_step(self) -> None:
        row = self.step_list.currentRow()
        if not 0 <= row < len(self.document.steps):
            return
        step = self.document.steps[row]
        answer = QMessageBox.question(
            self,
            "删除步骤",
            f"确定删除“{step.get('name')}”吗？",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.document.remove_step(row)
            self._refresh_document(max(0, row - 1))

    def new_document(self) -> None:
        if not self._confirm_discard():
            return
        self.document = WorkflowDocument()
        self.selected_window = None
        self.target_label.setText("未选择目标窗口")
        self._refresh_document()

    def open_document(self) -> None:
        if not self._confirm_discard():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "打开工作流",
            str(PROJECT_ROOT / "config"),
            "工作流 JSON (*.json)",
        )
        if not filename:
            return
        try:
            self.document = WorkflowDocument.load(Path(filename), PROJECT_ROOT)
        except Exception as error:
            QMessageBox.critical(self, "无法打开工作流", str(error))
            return
        self._refresh_document(0)
        self.statusBar().showMessage(f"已打开 {filename}", 4000)

    def save_document(self, save_as: bool = False) -> bool:
        path = self.document.path
        if save_as or path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "保存工作流",
                str(PROJECT_ROOT / "config" / "workflow.local.json"),
                "工作流 JSON (*.json)",
            )
            if not filename:
                return False
            path = Path(filename)
        try:
            saved = self.document.save(path)
        except Exception as error:
            QMessageBox.critical(self, "保存失败", str(error))
            return False
        self._update_title()
        self.statusBar().showMessage(f"已保存 {saved}", 4000)
        return True

    def choose_window(self) -> None:
        dialog = WindowSelectorDialog(self)
        if dialog.exec() and dialog.selected_window is not None:
            self.selected_window = dialog.selected_window
            window = dialog.selected_window
            self.target_label.setText(f"{window.title}  ·  {window.class_name}")
            self.target_label.setToolTip(
                f"HWND 0x{window.hwnd:X} · 客户区 {window.client_width}×{window.client_height}"
            )
            self.document.set_target(window.title, window.class_name)
            self._update_title()

    def run_workflow(self) -> None:
        if self._thread is not None:
            return
        if self.selected_window is None:
            QMessageBox.information(self, "尚未选择窗口", "请先选择唯一的目标窗口。")
            return
        if self.document.dirty or self.document.path is None:
            if not self.save_document():
                return
        try:
            definition = load_workflow_v2(self.document.path, PROJECT_ROOT)
            config = load_config(DEFAULT_CONFIG_PATH)
        except (WorkflowV2ConfigError, OSError, ValueError) as error:
            QMessageBox.critical(self, "工作流无法运行", str(error))
            return

        profile = self.profile_combo.currentData()
        warning = (
            f"目标：{self.selected_window.title}\n"
            f"输入策略：{profile.name.value}\n\n"
            f"{profile.warning}\n\n"
            "运行期间可能发送鼠标和键盘输入。是否继续？"
        )
        if (
            QMessageBox.warning(
                self,
                "确认运行工作流",
                warning,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        workspace = create_debug_workspace(
            PROJECT_ROOT,
            config["diagnostics"]["debug_dir"],
        )
        self._thread = QThread(self)
        self._worker = WorkflowWorker(
            definition,
            self.selected_window,
            config,
            PROJECT_ROOT,
            workspace,
            profile,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event_received.connect(self.on_workflow_event)
        self._worker.finished.connect(self.on_workflow_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker)
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.statusBar().showMessage("工作流运行中…")
        self.append_log(f"开始运行：{definition.name}")
        self._thread.start()

    def stop_workflow(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.stop_button.setEnabled(False)
            self.statusBar().showMessage("正在安全停止…")
            self.append_log("已请求停止，将在当前安全边界结束。")

    def on_workflow_event(self, event: object) -> None:
        if isinstance(event, WorkflowEvent):
            text = event.type.value
            if event.step_name:
                text += f" · {event.step_name}"
            if event.message:
                text += f" · {event.message}"
        else:
            text = str(event)
        self.append_log(text)

    def on_workflow_finished(self, succeeded: bool, message: str) -> None:
        self.append_log(message)
        self.statusBar().showMessage(message, 8000)
        if not succeeded and "已停止" not in message:
            QMessageBox.critical(
                self,
                "工作流运行失败",
                f"{message}\n\n请检查目标窗口、分辨率和输入策略，然后查看运行日志后重试。",
            )

    def _clear_worker(self) -> None:
        self._worker = None
        self._thread = None
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] {message}")

    def _confirm_discard(self) -> bool:
        if not self.document.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "未保存的更改",
            "当前工作流有未保存更改。是否保存？",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save_document()
        return answer == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None:
            QMessageBox.information(
                self,
                "工作流仍在运行",
                "请先停止工作流，等待控制器安全释放后再关闭。",
            )
            event.ignore()
            return
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
