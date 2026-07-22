# NZM-auto

一个基于 MaaFramework 的 Windows 自动化通用框架。

当前阶段包含项目骨架、配置自检和 MaaFramework 运行库版本检测；尚未创建控制器、搜索窗口或发送输入。

## 运行自检

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
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

该命令会选择窗口、连接 Maa Win32Controller、加载资源包并执行 `FrameworkSelfTest`，然后安全释放。自检 Pipeline 使用 `DirectHit + DoNothing`，不会发送输入。

## 调试文件

所有运行时调试文件统一写入被 Git 忽略的 `debug/`：

```text
debug/
├─ logs/
├─ screenshots/
├─ templates/
├─ reports/
└─ temp/
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

模板、匹配标注图和 JSON 报告分别写入 `debug/templates/`、`debug/screenshots/` 和 `debug/reports/`。

执行一次明确坐标的双击并对比前后截图：

```powershell
nzm-auto input-test --title "逆战" --index 0 --point 280 205
```

默认需要输入 `YES` 才会发送双击，并明确提示目标可能被打开；自动化测试可显式传入 `--yes`。该诊断命令临时使用 MaaFramework 的 `Seize` 前台鼠标输入，以产生 Windows 能够识别的原生双击，因此执行时会短暂激活目标窗口并占用物理鼠标。两次点击间隔 100ms，前后截图、差异图和 JSON 报告均写入 `debug/`。
