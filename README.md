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
