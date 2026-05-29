#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.gui.app import CardDetectorGUI
import tkinter as tk


def main():
    root = tk.Tk()
    CardDetectorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
