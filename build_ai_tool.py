# -*- coding: utf-8 -*-
r"""AI 多窗口集中討論工具 — Windows onefile 打包腳本

用法：
  cd Desktop
  python build_ai_tool.py

產出：
  dist\AI多窗口集中討論工具.exe
"""
import os
import sys
from pathlib import Path

import PyInstaller.__main__

MAIN_SCRIPT = "AI討論工具_最終版.py"
APP_NAME = "AI多窗口集中討論工具"
ICON_ICO = "玻璃球.ico"
ICON_PNG = "玻璃球.png"

PROJECT_ROOT = Path(__file__).resolve().parent


def add_data_arg(src: Path, dest_rel: str) -> str:
    sep = ";" if sys.platform.startswith("win") else ":"
    return f"--add-data={src}{sep}{dest_rel}"


def must_exist(p: Path, label: str) -> None:
    if not p.exists():
        raise FileNotFoundError(f"找不到 {label}: {p}")


def main() -> None:
    main_py = (PROJECT_ROOT / MAIN_SCRIPT).resolve()
    icon_path = (PROJECT_ROOT / ICON_ICO).resolve()
    png_path = (PROJECT_ROOT / ICON_PNG).resolve()

    must_exist(main_py, "main script")
    must_exist(icon_path, "icon (.ico)")

    params = [
        str(main_py),
        f"--name={APP_NAME}",
        "--noconfirm",
        "--clean",
        "--noconsole",
        "--onefile",
        f"--icon={icon_path}",

        # 將 ico + png 打進去，讓 tkinter 視窗/工作列都能用
        add_data_arg(icon_path, "."),
        # png 若存在就一起打包（可選）
        *([add_data_arg(png_path, ".")] if png_path.exists() else []),

        # ttkbootstrap 必須完整收集
        "--collect-all=ttkbootstrap",

        # 專案只有單一 .py，不需 collect-submodules
        # 隱含依賴
        "--hidden-import=PIL",
        "--hidden-import=PIL._tkinter_finder",
    ]

    print(f"[START] {sys.platform} onefile packaging ...")
    for a in params:
        print("  ", a)

    PyInstaller.__main__.run(params)
    print(f"\n[DONE] dist\\{APP_NAME}.exe")


if __name__ == "__main__":
    main()
