#!/usr/bin/env python3
"""
卡片探测器 GUI 启动脚本
直接运行此脚本启动 GUI 界面
"""

import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 使用绝对导入
from src.gui.app import CardDetectorGUI
import tkinter as tk


def main():
    """主函数"""
    print("正在启动卡片探测器 GUI...")
    root = tk.Tk()
    root.title("卡片自动探测器 - 纯 Python 实现")
    root.geometry("800x600")
    
    app = CardDetectorGUI(root)
    
    print("✓ GUI 已启动")
    print("提示：关闭 GUI 窗口即可退出程序")
    
    root.mainloop()


if __name__ == "__main__":
    main()
