"""Local Windows launcher; upstream viewer and generator remain unchanged."""
import pathlib
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

BASE = pathlib.Path(__file__).resolve().parent

def main():
    root = tk.Tk()
    root.title("Penrose Staircase — 本地启动器")
    root.geometry("440x220")
    root.resizable(False, False)
    tk.Label(root, text="彭罗斯不可能楼梯", font=("Microsoft YaHei UI", 17)).pack(pady=(20, 10))
    tk.Label(root, text="输入楼梯编号（1–10000），每个编号生成不同的图形。").pack()
    row = tk.Frame(root)
    row.pack(pady=16)
    number = tk.StringVar(value="35")
    entry = tk.Entry(row, textvariable=number, width=12, justify="center")
    entry.pack(side="left", padx=8)

    def launch(event=None):
        try:
            n = int(number.get())
            if not 1 <= n <= 10000:
                raise ValueError
        except ValueError:
            messagebox.showerror("编号无效", "请输入 1 到 10000 之间的整数。")
            return
        try:
            with (BASE / "viewer.log").open("a", encoding="utf-8") as log:
                subprocess.Popen([sys.executable, "-u", str(BASE / "vpstairs.py"), str(n)],
                                 cwd=BASE, stdout=log, stderr=log)
        except OSError as exc:
            messagebox.showerror("启动失败", str(exc))

    tk.Button(row, text="打开楼梯", command=launch, width=12).pack(side="left")
    tk.Label(root, text="原版为二维错觉绘图，不支持第一人称行走。\n点击图形内部或关闭窗口可退出该图形。", fg="#555555").pack()
    root.bind("<Return>", launch)
    entry.focus_set()
    root.mainloop()

if __name__ == "__main__":
    main()
