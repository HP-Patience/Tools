# 本地使用说明

安装目录：D:\Penrose-Staircase-Generator

## 启动
双击 Start-Penrose.cmd，输入 1–10000 的楼梯编号，点击“打开楼梯”。
默认编号为 35。点击绘图内部或关闭窗口会退出该图形。

也可以在 PowerShell 运行：

    Set-Location D:\Penrose-Staircase-Generator
    .\.venv\Scripts\python.exe .\vpstairs.py 35

注意：上游 README 写的是 `-n 35`，但原版代码直接读取第一个位置参数，因此应使用 `35`，不要加 `-n`。

## 内容
- 原版源码保持不变，版本：135f913e772890c551409d2914da1fa5d1d95b2c
- .venv：项目专用 Python 3.12 虚拟环境。
- graphics.py：John Zelle 官方 graphics 5.0，基于 Tkinter，GPL 授权。
  来源：https://mcsp.wartburg.edu/zelle/python/graphics.py
- launch.pyw / Start-Penrose.cmd：新增本地启动器。
- viewer.log：启动器打开绘图时的运行输出和错误日志。

运行时不需要网络，不需要服务器，不需要管理员权限。
这是二维不可能楼梯图形生成器，不是第一人称 3D 游戏。
原项目：https://github.com/fl3000/Penrose-Staircase-Generator
