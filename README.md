# NZM-auto

一个基于 MaaFramework 的 Windows 自动化通用框架。

当前已具备窗口发现与选择、Maa Win32Controller 连接、截图与模板识别、显式确认输入、画面变化验证，以及配置驱动的顺序工作流。正式业务模板和目标程序工作流仍需按实际界面制作。

## 运行自检

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m nzm_auto self-test
```

也可在安装项目后使用：

```powershell
nzm-auto self-test
```

只检查 MaaFramework 运行库版本：

```powershell
nzm-auto maa-version
```

只读列出桌面窗口：

```powershell
nzm-auto windows list
nzm-auto windows list --title "窗口标题的一部分"
nzm-auto windows list --class-name "窗口类名的一部分" --json
```

窗口枚举不会创建 Maa 控制器、截图或发送输入。

根据 `config/default.json` 唯一选择目标窗口：

```powershell
nzm-auto windows select
nzm-auto windows select --json
```

当前 `title_pattern` 按不区分大小写的标题子串匹配。匹配数量不是恰好一个时，选择会安全失败。

通用交互选择（推荐）：

```powershell
nzm-auto windows choose
nzm-auto windows choose --visible-only
nzm-auto windows choose --title "标题的一部分"
```

程序会列出候选窗口并要求输入编号。`--index 0` 可用于非交互测试。当前步骤只返回本次选择，不保存配置。

运行最小控制器连接闭环：

```powershell
nzm-auto run
nzm-auto run --visible-only
nzm-auto run --title "标题的一部分"
```

该命令会选择窗口、连接 Maa Win32Controller、检查原始画面为 `1920×1080` 且标准识别截图为 `1280×720`、加载资源包并执行 `FrameworkSelfTest`，然后安全释放。任一分辨率不符合要求时会在发送输入前安全失败。自检 Pipeline 使用 `DirectHit + DoNothing`，不会发送输入。任务执行时间超过 `runtime.task_timeout_seconds` 时，程序会请求 Maa 停止任务并安全失败。

## 调试文件

所有运行时调试文件统一写入被 Git 忽略的 `debug/`：

```text
debug/
├─ logs/
├─ screenshots/
└─ reports/
```

截取一次所选窗口并保存到 `debug/screenshots/`：

```powershell
nzm-auto capture
nzm-auto capture --title "标题的一部分" --index 0
```

每次 `run` 或 `capture` 都会在 `debug/logs/` 生成独立日志。

裁剪临时模板并执行 Maa TemplateMatch：

```powershell
nzm-auto template-match --title "逆战" --index 0 --template-roi 20 10 200 35
```

临时模板只保留在内存中，不写入 `debug/`。匹配标注图和 JSON 报告分别写入 `debug/screenshots/` 和 `debug/reports/`；正式模板统一放在 `assets/resource/image/`。

执行一次明确坐标的双击并对比前后截图：

```powershell
nzm-auto input-test --title "逆战" --index 0 --point 280 205
```

默认需要输入 `YES` 才会发送双击，并明确提示目标可能被打开；自动化测试可显式传入 `--yes`。该诊断命令临时使用 MaaFramework 的 `Seize` 前台鼠标输入，以产生 Windows 能够识别的原生双击，因此执行时会短暂激活目标窗口并占用物理鼠标。两次点击间隔 100ms，前后截图、差异图和 JSON 报告均写入 `debug/`。

根据模板识别结果自动计算中心坐标并执行操作：

```powershell
nzm-auto template-action --title "逆战" --index 0 --template assets/resource/image/start.png --action click
```

正式模板统一存放在 `assets/resource/image/`。该目录中的本地模板已被 `.gitignore` 排除，不会提交到 GitHub；仓库只保留 `.gitkeep`。在尚未制作正式模板时，也可以从当前画面裁剪一块仅驻留内存的临时模板来验证完整流程：

```powershell
nzm-auto template-action --title "逆战" --index 0 --template-roi 200 190 150 32 --action double-click
```

执行器仅在 MaaFramework 模板匹配成功后发送输入，并使用匹配框中心而不是固定坐标。默认需要输入 `YES` 确认；可显式传入 `--yes`。目标标注图、操作前后截图、差异图和 JSON 报告均写入 `debug/`。

## 配置驱动的顺序工作流

把 `config/workflow.example.json` 复制为被 Git 忽略的 `config/workflow.local.json`，将每一步的 `template` 指向 `assets/resource/image/` 下的本地模板，然后执行：

```powershell
nzm-auto workflow-run --title "逆战" --index 0 --workflow config/workflow.local.json
```

当前工作流是普通的顺序步骤列表，不是游戏状态机。每一步支持以下配置：

- `template`：相对项目根目录或绝对路径的 PNG 模板。
- `threshold`：MaaFramework 模板匹配阈值。
- `action`：`click` 或 `double-click`。
- `recognition_attempts`：发送输入前的最大识别次数，范围为 1–100。
- `recognition_interval_ms`：识别失败后的重试间隔。
- `pre_delay_ms` / `post_delay_ms`：步骤执行前和操作后的等待时间。
- `require_visual_change`：操作后是否必须检测到画面变化。

只有“尚未识别到模板”会触发识别重试。输入一旦发出，即使后续截图或画面验证失败，也会立即停止工作流，不会自动重复点击。
