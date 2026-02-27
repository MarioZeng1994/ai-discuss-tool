# -*- coding: utf-8 -*-
"""
AI 多窗口集中討論工具（最終版）
- ttkbootstrap 主題美化
- 設定區可收合
- 單頁架構 + 章節按鈕導航
- 自動恢復、多主題、累積紀錄、上一輪摘要
- Windows / macOS 雙平台相容
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import sys
import json
import re
import subprocess
from datetime import datetime

IS_WIN = sys.platform == 'win32'
IS_MAC = sys.platform == 'darwin'

# Windows DPI
if IS_WIN:
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from ttkbootstrap import Style
from ttkbootstrap.constants import *
import ttkbootstrap as ttkb

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
CONFIG_FILE = os.path.join(DESKTOP, "AI討論工具_config.json")

ICON_NAME_ICO = "玻璃球.ico"
ICON_NAME_ICNS = "玻璃球.icns"


def resource_path(relative_path: str) -> str:
    """PyInstaller 打包後 / 開發期都適用的資源路徑"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"topics": {}, "last_topic": ""}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def scan_max_round(topic_folder):
    if not os.path.isdir(topic_folder):
        return 0
    mx = 0
    for name in os.listdir(topic_folder):
        m = re.match(r"^第(\d+)輪$", name)
        if m and os.path.isdir(os.path.join(topic_folder, name)):
            mx = max(mx, int(m.group(1)))
    return mx


def read_round_files(topic_folder, round_num, ai_list):
    rn = f"第{round_num}輪"
    folder = os.path.join(topic_folder, rn)
    question = ""
    responses = {}
    q_path = os.path.join(folder, "提問.txt")
    if os.path.exists(q_path):
        with open(q_path, "r", encoding="utf-8") as f:
            question = f.read()
    for ai in ai_list:
        ai_file = os.path.join(folder, f"{ai['name']}_回覆.txt")
        if os.path.exists(ai_file):
            with open(ai_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            content_lines = []
            past_header = False
            for line in lines:
                if past_header:
                    content_lines.append(line)
                elif line.startswith("-" * 10) or line.startswith("=" * 10):
                    past_header = True
            responses[ai["name"]] = "".join(content_lines).strip()
    return question, responses


class App:
    THEMES = {"Cosmo 清爽": "cosmo", "Darkly 暗黑": "darkly",
              "Flatly 扁平": "flatly", "Minty 薄荷": "minty"}

    def __init__(self):
        self.cfg = load_config()
        if "topics" not in self.cfg:
            self.cfg = {"topics": {}, "last_topic": ""}
        saved_theme = self.cfg.get("theme", "cosmo")
        self.style = Style(theme=saved_theme)
        self.root = self.style.master
        self.root.title("AI 多窗口集中討論工具")
        self.root.geometry("780x820")
        self.root.minsize(600, 450)
        self.colors = self.style.colors
        self._set_dark_titlebar(saved_theme)
        self._setup_icon()

        self.topic_var = tk.StringVar()
        self.topic_root_var = tk.StringVar(value=DESKTOP)
        self.ai_list = []
        self.viewing_round = 0
        self.max_round = 0
        self.topic_folder = ""

        self._settings_visible = False
        prefs = self.cfg.get("prefs", {})
        self._auto_unfocus_on_paste = tk.BooleanVar(value=prefs.get("auto_unfocus_on_paste", False))
        self._auto_advance = tk.BooleanVar(value=prefs.get("auto_advance", False))
        self._no_full_record = tk.BooleanVar(value=prefs.get("no_full_record", False))
        self._only_full_record = tk.BooleanVar(value=prefs.get("only_full_record", False))
        # 防呆：若兩個互斥開關都為 True，會導致不產生任何檔案，直接回退為正常輸出
        if self._no_full_record.get() and self._only_full_record.get():
            self._no_full_record.set(False)
            self._only_full_record.set(False)
            prefs["no_full_record"] = False
            prefs["only_full_record"] = False
            self.cfg["prefs"] = prefs
            save_config(self.cfg)
        self._focused_text = None

        current_theme = self.cfg.get("theme", "cosmo")
        current_display = next((k for k, v in self.THEMES.items() if v == current_theme), "Cosmo 清爽")
        self.theme_var = tk.StringVar(value=current_display)

        # 開場白 / 結語 / 罐頭
        tpl = self.cfg.get("templates", {})
        self._openings = tpl.get("openings", [])   # [{"name":..,"text":..,"active":bool}]
        self._closings = tpl.get("closings", [])
        self._canned   = tpl.get("canned", [])      # [{"name":..,"text":..}]
        self._use_opening = tk.BooleanVar(value=tpl.get("use_opening", False))
        self._use_closing = tk.BooleanVar(value=tpl.get("use_closing", False))
        self._saved_snapshot_round = 0
        self._saved_snapshot_question = ""
        self._saved_snapshot_replies = {}
        self._build_ui()
        self._load_last_session()
        self._bind_keyboard_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_app_close)

    def _bind_keyboard_shortcuts(self):
        """鍵盤快捷鍵（參考 report_tool 模式）"""
        def _on_ctrl_enter(e):
            self._submit_round()
            return 'break'

        def _on_ctrl_n(e):
            self._new_round()
            return 'break'

        def _on_escape(e):
            self._focused_text = None
            self.root.focus_set()

        self.root.bind('<Control-Return>', _on_ctrl_enter)
        self.root.bind('<Control-n>', _on_ctrl_n)
        self.root.bind('<Control-N>', _on_ctrl_n)
        self.root.bind('<Escape>', _on_escape)

    # ═══════════════════════════════════════════════════════
    #  UI
    # ═══════════════════════════════════════════════════════
    def _build_ui(self):
        main = ttkb.Frame(self.root)
        main.pack(fill="both", expand=True, padx=8, pady=8)
        self.main_container = main

        # 點擊非輸入區域時自動取消焦點
        def _click_unfocus(event):
            w = event.widget
            input_classes = {"Text", "Entry", "TEntry", "Combobox", "TCombobox", "Spinbox", "TSpinbox", "Listbox"}
            cls_name = ""
            try:
                cls_name = str(w.winfo_class())
            except Exception:
                cls_name = ""
            widget_path = str(w).lower()
            if "popdown" in widget_path:
                return
            # 輸入元件（含 Combobox 下拉清單 Listbox）不攔截，避免切換主題被收合打斷
            if cls_name in input_classes or isinstance(w, tk.Text):
                return

            # 點擊收合區以外時，自動收起上方設定（窗簾模式）
            if self._settings_visible:
                target = w
                in_settings = False
                in_toggle = False
                while target is not None:
                    if target is self.frm_settings:
                        in_settings = True
                        break
                    if target is self.btn_toggle:
                        in_toggle = True
                        break
                    try:
                        target = target.master
                    except Exception:
                        break
                if (not in_settings) and (not in_toggle):
                    self._toggle_settings()
            target = w
            while target is not None:
                cls_name = ""
                try:
                    cls_name = str(target.winfo_class())
                except Exception:
                    cls_name = ""
                if cls_name in input_classes or isinstance(target, tk.Text):
                    return
                try:
                    target = target.master
                except Exception:
                    break
            self._focused_text = None
            self.root.focus_set()
        self.root.bind_all('<Button-1>', _click_unfocus, add='+')

        # ── 設定區（可收合）──
        self.btn_toggle = ttkb.Button(main, text="▼ 顯示設定（主題 / AI 成員）",
                                       command=self._toggle_settings, bootstyle="info-outline")
        self.btn_toggle.pack(fill="x", pady=(0, 5))

        self.frm_settings = ttkb.Frame(main)
        # 預設隱藏

        self._build_settings_area(self.frm_settings)
        self.frm_settings.place_forget()

        # 設定區改為懸浮展開（像窗簾），不擠壓下方區塊
        self.main_container.bind("<Configure>", lambda e: self._reposition_settings_overlay(), add="+")
        self.btn_toggle.bind("<Configure>", lambda e: self._reposition_settings_overlay(), add="+")

        # ── ③ 討論控制 ──
        frm_ctrl = ttkb.Labelframe(main, text="討論", padding=8)
        frm_ctrl.pack(fill="x", pady=(0, 5))

        ctrl_row = ttkb.Frame(frm_ctrl)
        ctrl_row.pack(fill="x")

        self.btn_prev = ttkb.Button(ctrl_row, text="◀", command=self._prev_round,
                                     state="disabled", bootstyle="secondary", width=3)
        self.btn_prev.pack(side="left", padx=(0, 3))
        self.btn_next = ttkb.Button(ctrl_row, text="▶", command=self._next_round,
                                     state="disabled", bootstyle="secondary", width=3)
        self.btn_next.pack(side="left", padx=(0, 6))

        ttkb.Button(ctrl_row, text="⊕ 新一輪", command=self._new_round,
                     bootstyle="warning").pack(side="left", padx=(0, 8))

        self.lbl_round = tk.Label(
            ctrl_row,
            text="══ 尚未開始 ══",
            font=("Microsoft JhengHei", 10, "bold"),
            fg="#ffffff",
            bg="#3b3f46",
            padx=8,
            pady=2
        )
        self.lbl_round.place(relx=0.5, rely=0.5, anchor="center")

        ttkb.Button(ctrl_row, text="📂 資料夾", command=self._open_folder,
                     bootstyle="info-outline").pack(side="right", padx=2)
        ttkb.Button(ctrl_row, text="📄 累積紀錄", command=self._open_accumulated,
                     bootstyle="info-outline").pack(side="right", padx=2)
        ttkb.Button(ctrl_row, text="模板", command=self._show_template_dialog,
                     bootstyle="info-outline").pack(side="right", padx=2)

        # ── 討論區（捲動）──
        self.frm_outer = ttkb.Frame(main)
        self.frm_outer.pack(fill="both", expand=True, pady=(0, 5))

        self.canvas = tk.Canvas(self.frm_outer, highlightthickness=0,
                                 bg=str(self.colors.bg))
        self.scrollbar = ttkb.Scrollbar(self.frm_outer, orient="vertical",
                                         command=self.canvas.yview, bootstyle="round")
        self.frm_discuss = ttkb.Frame(self.canvas)

        self.frm_discuss.bind("<Configure>",
                               lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_win = self.canvas.create_window((0, 0), window=self.frm_discuss, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>",
                          lambda e: self.canvas.itemconfig(self.canvas_win, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 滾輪邏輯：
        # 有焦點的 Text 且滑鼠在其上 → 該 Text 自滾（若內容可滾）
        # 其餘情況 → 全局 canvas 滾動
        def _on_mousewheel(event):
            try:
                w = self.root.winfo_containing(event.x_root, event.y_root)
                if w is None:
                    return
                # 若滑鼠在彈出視窗（Combobox 下拉等）上，不攔截
                if str(w.winfo_toplevel()) != str(self.canvas.winfo_toplevel()):
                    return
                # 若有焦點 Text 且滑鼠剛好在該 Text 上 → 讓 Text 自己滾
                if self._focused_text is not None:
                    target = w
                    while target is not None:
                        if target is self._focused_text:
                            # 只有內容可滾才攔截
                            if target.yview() != (0.0, 1.0):
                                return
                            break
                        try:
                            target = target.master
                        except Exception:
                            break
                # 檢查內容是否需要滾動
                sr = self.canvas.cget("scrollregion")
                if sr:
                    parts = sr.split()
                    if len(parts) >= 4:
                        if float(parts[3]) <= self.canvas.winfo_height():
                            return
                # 檢查滑鼠是否在 canvas 範圍內
                mx = event.x_root - self.canvas.winfo_rootx()
                my = event.y_root - self.canvas.winfo_rooty()
                if 0 <= mx <= self.canvas.winfo_width() and 0 <= my <= self.canvas.winfo_height():
                    if IS_MAC:
                        delta = -1 * int(event.delta)
                    else:
                        delta = -1 * int(event.delta / 120)
                    if delta != 0:
                        self.canvas.yview_scroll(delta, 'units')
            except Exception:
                pass

        self.root.bind_all('<MouseWheel>', _on_mousewheel)

        # ── 送出 ──
        self.btn_submit = ttkb.Button(main, text="✅ 確認送出（儲存本輪）",
                                       command=self._submit_round,
                                       bootstyle="success", state="disabled")
        self.btn_submit.pack(fill="x", pady=(0, 2))

    def _build_quick_topic_area(self, parent):
        frm_topic = ttkb.Labelframe(parent, text="主題", padding=6)
        frm_topic.pack(fill="x", pady=(0, 5))

        row_create = ttkb.Frame(frm_topic)
        row_create.pack(fill="x")

        ttkb.Label(row_create, text="名稱：").pack(side="left")
        self.ent_topic_name = ttkb.Entry(row_create, textvariable=self.topic_var, width=20)
        self.ent_topic_name.pack(side="left", padx=3)
        self.ent_topic_name.bind('<Return>', lambda e: (self._create_or_load_topic(), 'break')[1])

        ttkb.Label(row_create, text="建立位置：").pack(side="left")
        self.ent_topic_root = ttkb.Entry(row_create, textvariable=self.topic_root_var, width=30)
        self.ent_topic_root.pack(side="left", padx=3)
        self.ent_topic_root.bind('<Return>', lambda e: (self._create_or_load_topic(), 'break')[1])
        ttkb.Button(row_create, text="瀏覽", command=self._browse_topic_root,
                    bootstyle="outline", width=4).pack(side="left", padx=2)
        ttkb.Button(row_create, text="建立/載入", command=self._create_or_load_topic,
                    bootstyle="success").pack(side="left", padx=4)

        row_switch = ttkb.Frame(frm_topic)
        row_switch.pack(fill="x", pady=(6, 0))

        ttkb.Label(row_switch, text="切換主題：").pack(side="left")
        self.combo_topic = ttkb.Combobox(row_switch, width=45, state="readonly")
        self.combo_topic.pack(side="left", padx=6)
        self.combo_topic.bind("<<ComboboxSelected>>", lambda e: self.root.after_idle(self._on_topic_selected))

        self.lbl_topic_status = ttkb.Label(row_switch, text="", bootstyle="success")
        self.lbl_topic_status.pack(side="left", padx=5)

    def _build_settings_area(self, parent):
        # ── 主題 ──
        self._build_quick_topic_area(parent)

        # ── AI 成員 ──
        frm_ai = ttkb.Labelframe(parent, text="AI 成員", padding=6)
        frm_ai.pack(fill="x", pady=(0, 5))

        row_ai = ttkb.Frame(frm_ai)
        row_ai.pack(fill="x")

        ttkb.Label(row_ai, text="名稱：").pack(side="left")
        self.ent_ai_name = ttkb.Entry(row_ai, width=8)
        self.ent_ai_name.pack(side="left", padx=3)

        ttkb.Label(row_ai, text="資料夾（選填）：").pack(side="left")
        self.ent_ai_path = ttkb.Entry(row_ai, width=30)
        self.ent_ai_path.pack(side="left", padx=3)
        ttkb.Button(row_ai, text="瀏覽", command=self._browse_ai_path,
                     bootstyle="outline", width=4).pack(side="left", padx=2)
        ttkb.Button(row_ai, text="新增", command=self._add_ai,
                     bootstyle="info", width=4).pack(side="left", padx=3)

        self.frm_ai_list = ttkb.Frame(frm_ai)
        self.frm_ai_list.pack(fill="x", pady=(5, 0))

        # ⚙ 設定按鈕（放在收合區底部）
        ttkb.Button(parent, text="⚙ 進階設定", command=self._open_advanced_settings,
                     bootstyle="warning-outline").pack(anchor="w", pady=(5, 0))

    def _open_advanced_settings(self):
        if self._settings_visible:
            self._toggle_settings()
        self._show_settings_dialog()

    def _show_settings_dialog(self):
        """彈窗：所有設定選項"""
        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        dlg.title("設定")
        dlg.geometry("420x360")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        pad = {"padx": 12, "pady": 4, "anchor": "w"}

        # ── 行為設定 ──
        ttkb.Label(dlg, text="行為設定", font=("Microsoft JhengHei", 11, "bold")).pack(padx=12, pady=(10, 4), anchor="w")
        ttkb.Separator(dlg).pack(fill="x", padx=10)

        ttkb.Checkbutton(dlg, text="貼上後自動移除焦點",
                          variable=self._auto_unfocus_on_paste,
                          bootstyle="round-toggle").pack(**pad)
        ttkb.Checkbutton(dlg, text="確認送出後自動進入下一輪",
                          variable=self._auto_advance,
                          bootstyle="round-toggle").pack(**pad)

        # ── 輸出設定 ──
        ttkb.Label(dlg, text="輸出設定", font=("Microsoft JhengHei", 11, "bold")).pack(padx=12, pady=(12, 4), anchor="w")
        ttkb.Separator(dlg).pack(fill="x", padx=10)

        def _on_no_full():
            if self._no_full_record.get():
                self._only_full_record.set(False)

        def _on_only_full():
            if self._only_full_record.get():
                self._no_full_record.set(False)

        ttkb.Checkbutton(dlg, text="不生成完整紀錄（第N輪_完整紀錄.txt）",
                          variable=self._no_full_record,
                          command=_on_no_full,
                          bootstyle="round-toggle").pack(**pad)
        ttkb.Checkbutton(dlg, text="僅生成完整紀錄（不生成個別 _回覆 / 提問.txt）",
                          variable=self._only_full_record,
                          command=_on_only_full,
                          bootstyle="round-toggle").pack(**pad)

        # ── 外觀主題 ──
        ttkb.Label(dlg, text="外觀主題", font=("Microsoft JhengHei", 11, "bold")).pack(padx=12, pady=(12, 4), anchor="w")
        ttkb.Separator(dlg).pack(fill="x", padx=10)

        row_th = ttkb.Frame(dlg)
        row_th.pack(fill="x", padx=12, pady=6)
        ttkb.Label(row_th, text="風格：").pack(side="left")
        combo_th = ttkb.Combobox(row_th, textvariable=self.theme_var,
                                  values=list(self.THEMES.keys()), state="readonly", width=15)
        combo_th.pack(side="left", padx=3)
        ttkb.Button(row_th, text="套用", command=self._switch_theme,
                     bootstyle="warning").pack(side="left", padx=5)

        # 關閉
        def _close_settings():
            self._save_prefs()
            dlg.destroy()
        btn_close = ttkb.Button(dlg, text="關閉", command=_close_settings,
                                 bootstyle="secondary")
        btn_close.pack(pady=12)

        dlg.protocol("WM_DELETE_WINDOW", _close_settings)
        dlg.bind('<Escape>', lambda e: _close_settings())
        dlg.bind('<Return>', lambda e: btn_close.invoke())
        dlg.bind('<KP_Enter>', lambda e: btn_close.invoke())
        self._center_dialog(dlg, 420, 360)

    def _switch_theme(self):
        display = self.theme_var.get()
        theme = self.THEMES.get(display, "cosmo")
        try:
            self.style.theme_use(theme)
            self.colors = self.style.colors
            if hasattr(self, "canvas"):
                self.canvas.configure(bg=str(self.colors.bg))
            self._set_dark_titlebar(theme)
        except Exception as e:
            messagebox.showerror("主題切換失敗", f"無法切換主題：\n{e}")
            return
        self.cfg["theme"] = theme
        save_config(self.cfg)
        messagebox.showinfo("主題已切換", f"已切換為「{display}」。")

    def _save_templates(self):
        # 若啟用但無有效啟用項，自動關閉
        if self._use_opening.get():
            if not self._openings or not any(o.get("active") and o.get("text") for o in self._openings):
                self._use_opening.set(False)
        if self._use_closing.get():
            if not self._closings or not any(c.get("active") and c.get("text") for c in self._closings):
                self._use_closing.set(False)
        self.cfg["templates"] = {
            "openings": self._openings,
            "closings": self._closings,
            "canned":   self._canned,
            "use_opening": self._use_opening.get(),
            "use_closing": self._use_closing.get(),
        }
        save_config(self.cfg)

    def _save_prefs(self):
        self.cfg["prefs"] = {
            "auto_unfocus_on_paste": self._auto_unfocus_on_paste.get(),
            "auto_advance": self._auto_advance.get(),
            "no_full_record": self._no_full_record.get(),
            "only_full_record": self._only_full_record.get(),
        }
        save_config(self.cfg)

    def _resolve_placeholders(self, text):
        """將模板佔位符替換為實際路徑（加「」框）"""
        rn = self.viewing_round
        topic = self.topic_folder
        mapping = {
            "<上輪路徑>": f"「{os.path.join(topic, f'第{max(rn-1,1)}輪')}」" if topic else "",
            "<本輪路徑>": f"「{os.path.join(topic, f'第{rn}輪')}」" if topic else "",
            "<主題資料夾>": f"「{topic}」" if topic else "",
        }
        for k, v in mapping.items():
            text = text.replace(k, v)
        return text

    def _get_active_opening(self):
        for item in self._openings:
            if item.get("active"):
                return self._resolve_placeholders(item["text"])
        return ""

    def _get_active_closing(self):
        for item in self._closings:
            if item.get("active"):
                return self._resolve_placeholders(item["text"])
        return ""

    def _show_template_dialog(self):
        """開場白 / 結語 / 罐頭 管理彈窗"""
        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        dlg.title("開場白 / 結語 / 罐頭信息")
        dlg.geometry("620x560")
        dlg.transient(self.root)
        dlg.grab_set()

        # 先 pack 底部按鈕，保證永遠可見
        def _on_close():
            self._save_templates()
            dlg.destroy()
            # 重新載入當前輪次 UI，保留未儲存草稿，讓罐頭按鈕即時更新
            self._refresh_current_round_preserve_draft()
        btn_frame = ttkb.Frame(dlg)
        btn_frame.pack(side="bottom", fill="x", pady=8)
        btn_save_close = ttkb.Button(btn_frame, text="儲存並關閉", command=_on_close,
                                      bootstyle="success")
        btn_save_close.pack()

        nb = ttkb.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        dlg.protocol("WM_DELETE_WINDOW", _on_close)
        dlg.bind('<Escape>', lambda e: _on_close())
        dlg.bind('<Control-s>', lambda e: (btn_save_close.invoke(), 'break')[1])

        # ─── 開場白 ───
        frm_open = ttkb.Frame(nb, padding=8)
        nb.add(frm_open, text="開場白")

        def _check_opening(*_):
            if self._use_opening.get():
                if not self._openings or not any(o.get("active") and o.get("text") for o in self._openings):
                    messagebox.showinfo("提示", "目前沒有任何開場白方案被啟用（或內容為空），請先新增並啟用一個方案。", parent=dlg)
                    self._use_opening.set(False)

        cb_open = ttkb.Checkbutton(frm_open, text="啟用開場白",
                          variable=self._use_opening,
                          bootstyle="round-toggle", state="disabled")
        cb_open.pack(anchor="w")
        ttkb.Label(frm_open, text="可用佔位符：<上輪路徑>  <本輪路徑>  <主題資料夾>",
                    font=("Microsoft JhengHei", 8)).pack(anchor="w", pady=(2, 4))
        self._build_template_list(frm_open, self._openings, "opening", self._use_opening)

        # ─── 結語 ───
        frm_close = ttkb.Frame(nb, padding=8)
        nb.add(frm_close, text="結語")

        def _check_closing(*_):
            if self._use_closing.get():
                if not self._closings or not any(c.get("active") and c.get("text") for c in self._closings):
                    messagebox.showinfo("提示", "目前沒有任何結語方案被啟用（或內容為空），請先新增並啟用一個方案。", parent=dlg)
                    self._use_closing.set(False)

        cb_close = ttkb.Checkbutton(frm_close, text="啟用結語",
                          variable=self._use_closing,
                          bootstyle="round-toggle", state="disabled")
        cb_close.pack(anchor="w")
        ttkb.Label(frm_close, text="可用佔位符：<上輪路徑>  <本輪路徑>  <主題資料夾>",
                    font=("Microsoft JhengHei", 8)).pack(anchor="w", pady=(2, 4))
        self._build_template_list(frm_close, self._closings, "closing", self._use_closing)

        # ─── 罐頭信息 ───
        frm_can = ttkb.Frame(nb, padding=8)
        nb.add(frm_can, text="罐頭信息")
        ttkb.Label(frm_can, text="按「插入」可將內容貼入提問框。可用佔位符同上。",
                    font=("Microsoft JhengHei", 8)).pack(anchor="w", pady=(0, 4))
        self._build_canned_list(frm_can)

        self._center_dialog(dlg, 620, 560)

    def _build_template_list(self, parent, items, kind, master_var):
        """建立開場白/結語列表 UI（帶 radio 選擇，與 master toggle 同步）"""
        container = ttkb.Frame(parent)
        container.pack(fill="both", expand=True)

        listbox = ttkb.Frame(container)
        listbox.pack(fill="both", expand=True)

        def _sync_master():
            """同步 master toggle：有任何 active 就開，全部關就關"""
            has_active = any(it.get("active") and it.get("text") for it in items)
            master_var.set(has_active)

        def _refresh():
            for w in listbox.winfo_children():
                w.destroy()
            for i, item in enumerate(items):
                row = ttkb.Frame(listbox)
                row.pack(fill="x", pady=1)
                rb = ttkb.Checkbutton(row, text="啟用", bootstyle="round-toggle")
                rb_var = tk.BooleanVar(value=item.get("active", False))
                rb.config(variable=rb_var,
                          command=lambda idx=i, v=rb_var: _set_active(idx, v.get()))
                rb.pack(side="left")
                ttkb.Label(row, text=f"[{item['name']}]", width=10).pack(side="left", padx=3)
                ttkb.Label(row, text=item["text"][:50] + ("..." if len(item["text"]) > 50 else ""),
                            wraplength=300).pack(side="left", padx=3, fill="x", expand=True)
                ttkb.Button(row, text="✏", width=2, bootstyle="info-outline",
                             command=lambda idx=i: _edit(idx)).pack(side="right", padx=1)
                ttkb.Button(row, text="✕", width=2, bootstyle="danger-outline",
                             command=lambda idx=i: _delete(idx)).pack(side="right", padx=1)

        def _set_active(idx, val):
            if val:
                for j, it in enumerate(items):
                    it["active"] = (j == idx)
            else:
                items[idx]["active"] = False
            _refresh()
            _sync_master()

        def _delete(idx):
            items.pop(idx)
            _refresh()
            _sync_master()

        def _edit(idx):
            self._edit_template_item(items, idx, _refresh)

        def _add():
            items.append({"name": f"方案{len(items)+1}", "text": "", "active": False})
            self._edit_template_item(items, len(items) - 1, _refresh, is_new=True)

        ttkb.Button(parent, text="＋ 新增", command=_add,
                     bootstyle="success-outline").pack(anchor="w", pady=4)
        _refresh()

    def _build_canned_list(self, parent):
        """建立罐頭信息列表"""
        container = ttkb.Frame(parent)
        container.pack(fill="both", expand=True)

        listbox = ttkb.Frame(container)
        listbox.pack(fill="both", expand=True)

        def _refresh():
            for w in listbox.winfo_children():
                w.destroy()
            for i, item in enumerate(self._canned):
                row = ttkb.Frame(listbox)
                row.pack(fill="x", pady=1)
                ttkb.Label(row, text=f"[{item['name']}]", width=10).pack(side="left", padx=3)
                ttkb.Label(row, text=item["text"][:60] + ("..." if len(item["text"]) > 60 else ""),
                            wraplength=350).pack(side="left", padx=3, fill="x", expand=True)
                ttkb.Button(row, text="✏", width=2, bootstyle="info-outline",
                             command=lambda idx=i: _edit(idx)).pack(side="right", padx=1)
                ttkb.Button(row, text="✕", width=2, bootstyle="danger-outline",
                             command=lambda idx=i: _delete(idx)).pack(side="right", padx=1)

        def _delete(idx):
            self._canned.pop(idx)
            _refresh()

        def _edit(idx):
            self._edit_template_item(self._canned, idx, _refresh)

        def _add():
            self._canned.append({"name": f"罐頭{len(self._canned)+1}", "text": ""})
            self._edit_template_item(self._canned, len(self._canned) - 1, _refresh, is_new=True)

        ttkb.Button(parent, text="＋ 新增", command=_add,
                     bootstyle="success-outline").pack(anchor="w", pady=4)
        _refresh()

    def _edit_template_item(self, items, idx, refresh_cb, is_new=False):
        """編輯單個模板項目"""
        item = items[idx]
        orig_name = item.get("name", "")
        orig_text = item.get("text", "")

        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        dlg.title("編輯模板")
        dlg.geometry("520x420")
        dlg.transient(self.root)
        dlg.grab_set()

        ttkb.Label(dlg, text="名稱：").pack(anchor="w", padx=8, pady=(8, 2))
        ent_name = ttkb.Entry(dlg, width=30)
        ent_name.pack(padx=8, anchor="w")
        ent_name.insert(0, item.get("name", ""))

        # 佔位符快捷按鈕
        ph_frame = ttkb.Frame(dlg)
        ph_frame.pack(anchor="w", padx=8, pady=(8, 2))
        ttkb.Label(ph_frame, text="佔位符：").pack(side="left")
        for ph in ["<上輪路徑>", "<本輪路徑>", "<主題資料夾>"]:
            ttkb.Button(ph_frame, text=ph, bootstyle="secondary-outline",
                        command=lambda p=ph: txt.insert(tk.INSERT, p)).pack(side="left", padx=2)

        # 罐頭信息快捷按鈕
        if self._canned:
            cn_frame = ttkb.Frame(dlg)
            cn_frame.pack(anchor="w", padx=8, pady=(2, 2))
            ttkb.Label(cn_frame, text="罐頭：").pack(side="left")
            for ci, c in enumerate(self._canned):
                ttkb.Button(cn_frame, text=c["name"], bootstyle="warning-outline",
                            command=lambda idx=ci: txt.insert(tk.INSERT, self._canned[idx]["text"])
                            ).pack(side="left", padx=2)

        txt = scrolledtext.ScrolledText(dlg, height=8, font=("Microsoft JhengHei", 10), wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=(2, 4))
        txt.insert("1.0", item.get("text", ""))

        def _save():
            text = txt.get("1.0", tk.END).rstrip("\n")
            if not text:
                messagebox.showwarning("提示", "內容不可為空！", parent=dlg)
                return
            item["name"] = ent_name.get().strip() or orig_name
            item["text"] = text
            dlg.destroy()
            refresh_cb()

        def _cancel():
            if is_new:
                items.pop(idx)
            else:
                item["name"] = orig_name
                item["text"] = orig_text
            dlg.destroy()
            refresh_cb()

        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        dlg.bind('<Escape>', lambda e: _cancel())
        dlg.bind('<Control-Return>', lambda e: (_save(), 'break')[1])

        btn_save = ttkb.Button(dlg, text="儲存", command=_save,
                                bootstyle="success")
        btn_save.pack(pady=8)
        dlg.bind('<Control-s>', lambda e: (btn_save.invoke(), 'break')[1])

        self._center_dialog(dlg, 520, 420)

    @staticmethod
    def _set_dark_titlebar(theme_name):
        if not IS_WIN:
            return
        dark_themes = {"darkly", "cyborg", "solar", "superhero", "vapor"}
        try:
            import ctypes
            # 需要在 root.update() 之後才能拿到 hwnd，延遲處理
            def _apply():
                try:
                    root = tk._default_root
                    if root is None:
                        return
                    root.update_idletasks()
                    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                    value = ctypes.c_int(1 if theme_name in dark_themes else 0)
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
                except Exception:
                    pass
            tk._default_root.after(100, _apply)
        except Exception:
            pass

    def _setup_icon(self):
        """設定視窗圖示 + Windows 工作列 AppUserModelID"""
        # Windows: 設定 AppUserModelID，讓工作列圖示獨立不與 Python 共用
        if IS_WIN:
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    'AI.DiscussTool.GUI.1.0')
            except Exception:
                pass

        # 優先用 PNG + wm_iconphoto（工作列/左上角都正確）
        icon_set = False
        try:
            png = resource_path(ICON_NAME_ICO.replace('.ico', '.png'))
            if os.path.exists(png):
                from PIL import Image, ImageTk
                src = Image.open(png)
                self._icon_photos = []
                for s in [256, 128, 64, 48, 32, 16]:
                    img = src.resize((s, s), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self._icon_photos.append(photo)
                self.root.wm_iconphoto(True, *self._icon_photos)
                icon_set = True
        except Exception:
            pass

        # Fallback: 用 ico
        if not icon_set:
            try:
                ico = resource_path(ICON_NAME_ICO)
                if os.path.exists(ico):
                    self.root.iconbitmap(default=ico)
            except Exception:
                pass

    def _toggle_settings(self):
        if self._settings_visible:
            self.frm_settings.place_forget()
            self.btn_toggle.config(text="▼ 顯示設定（主題 / AI 成員）")
            self._settings_visible = False
        else:
            self._settings_visible = True
            self._reposition_settings_overlay()
            self.frm_settings.lift()
            self.btn_toggle.config(text="▲ 收合設定")

    def _reposition_settings_overlay(self):
        if not getattr(self, "_settings_visible", False):
            return
        try:
            host = self.main_container
            x = self.btn_toggle.winfo_x()
            y = self.btn_toggle.winfo_y() + self.btn_toggle.winfo_height() + 1
            width = max(120, self.btn_toggle.winfo_width())
            self.frm_settings.place(in_=host, x=x, y=y, width=width)
            self.frm_settings.lift()
        except Exception:
            pass

    def _bind_text_focus(self, txt_widget):
        """為 ScrolledText 綁定焦點追蹤 + 貼上後自動移除焦點"""
        def _on_focus_in(event):
            self._focused_text = txt_widget
            txt_widget._paste_done = False

        def _on_focus_out(event):
            if self._focused_text is txt_widget:
                self._focused_text = None

        def _on_paste(event):
            if self._auto_unfocus_on_paste.get() and not getattr(txt_widget, '_paste_done', False):
                txt_widget._paste_done = True
                self.root.after(50, lambda: self.root.focus_set())

        txt_widget.bind('<FocusIn>', _on_focus_in, add='+')
        txt_widget.bind('<FocusOut>', _on_focus_out, add='+')
        txt_widget.bind('<<Paste>>', _on_paste, add='+')

    # ═══════════════════════════════════════════════════════
    #  主題
    # ═══════════════════════════════════════════════════════
    @staticmethod
    def _normalize_path(path):
        p = (path or "").strip().strip('"').strip("'")
        if not p:
            return ""
        return os.path.normpath(os.path.expanduser(p))

    def _topic_folder_of(self, topic_name):
        topic_info = self.cfg.get("topics", {}).get(topic_name, {})
        folder = topic_info.get("folder", "") if isinstance(topic_info, dict) else ""
        folder = self._normalize_path(folder)
        if not folder:
            folder = os.path.join(DESKTOP, topic_name)
        return folder

    def _refresh_topic_combo(self):
        topics = sorted(list(self.cfg.get("topics", {}).keys()))
        if hasattr(self, "combo_topic"):
            self.combo_topic["values"] = topics
            if topics and self.topic_var.get() in topics:
                self.combo_topic.set(self.topic_var.get())
            elif not topics:
                self.combo_topic.set("")

    def _browse_topic_root(self):
        current_root = self._normalize_path(self.topic_root_var.get()) or DESKTOP
        if not os.path.isdir(current_root):
            current_root = DESKTOP
        p = filedialog.askdirectory(initialdir=current_root)
        if p:
            self.topic_root_var.set(self._normalize_path(p).replace("/", "\\"))

    def _load_topic(self, topic_name):
        t = (topic_name or "").strip()
        if not t:
            return

        topics_cfg = self.cfg.setdefault("topics", {})
        info = topics_cfg.get(t, {})
        if not isinstance(info, dict):
            info = {}
        if "ai_list" not in info or not isinstance(info.get("ai_list"), list):
            info["ai_list"] = []

        folder = self._topic_folder_of(t)
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("錯誤", f"無法建立或載入主題資料夾：\n{folder}\n\n{e}")
            return

        info["folder"] = folder
        topics_cfg[t] = info
        self.cfg["last_topic"] = t
        save_config(self.cfg)

        self.topic_var.set(t)
        self.topic_folder = folder
        self.topic_root_var.set((os.path.dirname(folder) or DESKTOP).replace("/", "\\"))
        self.ai_list = info.get("ai_list", [])
        self.max_round = scan_max_round(self.topic_folder)
        self._refresh_ai_list_display()
        self._refresh_topic_combo()

        if self.max_round > 0 and self.ai_list:
            self.lbl_topic_status.config(text=f"✔ 共 {self.max_round} 輪")
            self._goto_round(self.max_round)
        else:
            self.lbl_topic_status.config(text="✔ 已建立")
            self.lbl_round.config(text="請新增 AI 成員後按「新一輪」")
            self._clear_discuss()
        self._update_nav()

    def _create_or_load_topic(self):
        t = self.topic_var.get().strip()
        if not t:
            messagebox.showwarning("提示", "請輸入主題名稱")
            return
        root = self._normalize_path(self.topic_root_var.get()) or DESKTOP
        try:
            os.makedirs(root, exist_ok=True)
        except Exception as e:
            messagebox.showerror("錯誤", f"無法建立主題根目錄：\n{root}\n\n{e}")
            return

        folder = os.path.join(root, t)
        if os.path.exists(folder) and not os.path.isdir(folder):
            messagebox.showerror("錯誤", f"建立失敗：目標不是資料夾\n{folder}")
            return

        topics_cfg = self.cfg.setdefault("topics", {})
        info = topics_cfg.get(t, {})
        if not isinstance(info, dict):
            info = {}
        if "ai_list" not in info or not isinstance(info.get("ai_list"), list):
            info["ai_list"] = []
        info["folder"] = folder
        topics_cfg[t] = info

        self._load_topic(t)

    def _on_topic_selected(self, event=None):
        t = self.combo_topic.get().strip() if hasattr(self, "combo_topic") else ""
        if not t:
            t = self.topic_var.get().strip()
        if t:
            self._load_topic(t)
            if self._settings_visible:
                self._toggle_settings()

    # ═══════════════════════════════════════════════════════
    #  AI 成員
    # ═══════════════════════════════════════════════════════
    def _browse_ai_path(self):
        p = filedialog.askdirectory()
        if p:
            self.ent_ai_path.delete(0, tk.END)
            self.ent_ai_path.insert(0, p.replace("/", "\\"))

    def _add_ai(self):
        name = self.ent_ai_name.get().strip()
        path = self.ent_ai_path.get().strip()
        if not name:
            messagebox.showwarning("提示", "請輸入 AI 名稱")
            return
        self.ai_list.append({"name": name, "path": path})
        self.ent_ai_name.delete(0, tk.END)
        self.ent_ai_path.delete(0, tk.END)
        self._refresh_ai_list_display()
        self._save_ai_config()

    def _remove_ai(self, idx):
        if 0 <= idx < len(self.ai_list):
            self.ai_list.pop(idx)
            self._refresh_ai_list_display()
            self._save_ai_config()

    def _refresh_ai_list_display(self):
        for w in self.frm_ai_list.winfo_children():
            w.destroy()
        for i, ai in enumerate(self.ai_list):
            frm = ttkb.Frame(self.frm_ai_list)
            frm.pack(fill="x", pady=1)
            display = f"  {ai['name']}"
            if ai.get('path'):
                display += f"  →  {ai['path']}"
            ttkb.Label(frm, text=display, anchor="w").pack(side="left", fill="x", expand=True)
            ttkb.Button(frm, text="✕", command=lambda idx=i: self._remove_ai(idx),
                         bootstyle="danger-outline", width=3).pack(side="right")

    def _save_ai_config(self):
        t = self.topic_var.get().strip()
        if not t:
            return
        topics_cfg = self.cfg.setdefault("topics", {})
        info = topics_cfg.get(t, {})
        if not isinstance(info, dict):
            info = {}
        info["ai_list"] = self.ai_list
        if self.topic_folder:
            info["folder"] = self.topic_folder
        topics_cfg[t] = info
        save_config(self.cfg)
        if self.topic_folder:
            os.makedirs(self.topic_folder, exist_ok=True)
            info_path = os.path.join(self.topic_folder, "AI成員資料.txt")
            with open(info_path, "w", encoding="utf-8") as f:
                f.write(f"主題：{t}\n")
                f.write(f"更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                for ai in self.ai_list:
                    f.write(f"AI 名稱：{ai['name']}\n")
                    if ai.get('path'):
                        f.write(f"工作資料夾：{ai['path']}\n")
                    f.write("-" * 30 + "\n")

    # ═══════════════════════════════════════════════════════
    #  輪次導航
    # ═══════════════════════════════════════════════════════
    def _update_nav(self):
        self.max_round = scan_max_round(self.topic_folder) if self.topic_folder else 0
        if hasattr(self, "btn_prev"):
            self.btn_prev.config(state="normal" if self.viewing_round > 1 else "disabled")
        if hasattr(self, "btn_next"):
            self.btn_next.config(state="normal" if self.viewing_round < self.max_round else "disabled")

    def _prev_round(self):
        if self.viewing_round > 1:
            self._goto_round(self.viewing_round - 1)

    def _next_round(self):
        if self.viewing_round < self.max_round:
            self._goto_round(self.viewing_round + 1)

    def _new_round(self):
        if not self.topic_folder:
            messagebox.showwarning("提示", "請先建立主題")
            return
        if not self.ai_list:
            messagebox.showwarning("提示", "請先新增至少一個 AI 成員")
            return
        self.max_round = scan_max_round(self.topic_folder)
        new_n = self.max_round + 1
        os.makedirs(os.path.join(self.topic_folder, f"第{new_n}輪"), exist_ok=True)
        self._goto_round(new_n)
        # 自動收合設定
        if self._settings_visible:
            self._toggle_settings()

    def _goto_round(self, n):
        if not self.topic_folder or not self.ai_list:
            return
        self.viewing_round = n
        rn = f"第{n}輪"
        saved_q, saved_r = read_round_files(self.topic_folder, n, self.ai_list)
        has_saved = bool(saved_q) or bool(saved_r)
        self._build_round_ui(n, saved_q, saved_r, has_saved)
        self.lbl_round.config(text=f"══ {rn} ══", fg="#ffffff")
        self.btn_submit.config(state="normal")
        self._update_nav()

    def _clear_discuss(self):
        for w in self.frm_discuss.winfo_children():
            w.destroy()
        self.btn_submit.config(state="disabled")
        self._saved_snapshot_round = 0
        self._saved_snapshot_question = ""
        self._saved_snapshot_replies = {}

    def _normalize_text(self, text):
        return (text or "").strip()

    def _capture_current_inputs(self):
        question = ""
        if hasattr(self, 'txt_question'):
            question = self._normalize_text(self.txt_question.get("1.0", tk.END))
        replies = {}
        for aw in getattr(self, "ai_text_widgets", []):
            replies[aw["name"]] = self._normalize_text(aw["widget"].get("1.0", tk.END))
        return question, replies

    def _capture_round_draft(self):
        if self.viewing_round <= 0 or not hasattr(self, 'txt_question'):
            return None
        question, replies = self._capture_current_inputs()
        focus_key = None
        if self._focused_text is self.txt_question:
            focus_key = ("question", "")
        else:
            for aw in getattr(self, "ai_text_widgets", []):
                if self._focused_text is aw["widget"]:
                    focus_key = ("ai", aw["name"])
                    break
        return {
            "round": self.viewing_round,
            "question": question,
            "replies": replies,
            "focus_key": focus_key,
        }

    def _restore_round_draft(self, draft):
        if not draft or draft.get("round") != self.viewing_round:
            return
        if hasattr(self, 'txt_question'):
            self.txt_question.delete("1.0", tk.END)
            if draft.get("question"):
                self.txt_question.insert("1.0", draft["question"])
        focus_target = None
        focus_key = draft.get("focus_key")
        if focus_key and focus_key[0] == "question":
            focus_target = getattr(self, "txt_question", None)
        for aw in getattr(self, "ai_text_widgets", []):
            txt = aw["widget"]
            txt.delete("1.0", tk.END)
            val = draft.get("replies", {}).get(aw["name"], "")
            if val:
                txt.insert("1.0", val)
            if focus_key and focus_key[0] == "ai" and focus_key[1] == aw["name"]:
                focus_target = txt
        if focus_target is not None:
            try:
                focus_target.focus_set()
                self._focused_text = focus_target
            except Exception:
                self._focused_text = None
        else:
            self._focused_text = None

    def _refresh_current_round_preserve_draft(self):
        if self.viewing_round <= 0 or not self.topic_folder or not self.ai_list:
            return
        round_num = self.viewing_round
        draft = self._capture_round_draft()
        self._goto_round(round_num)
        if draft:
            self._restore_round_draft(draft)

    def _set_saved_snapshot(self, round_num, question, replies):
        self._saved_snapshot_round = round_num
        self._saved_snapshot_question = self._normalize_text(question)
        self._saved_snapshot_replies = {}
        for aw in getattr(self, "ai_text_widgets", []):
            name = aw["name"]
            self._saved_snapshot_replies[name] = self._normalize_text(replies.get(name, ""))

    def _sync_saved_snapshot_from_widgets(self):
        question, replies = self._capture_current_inputs()
        self._set_saved_snapshot(self.viewing_round, question, replies)

    def _has_unsaved_text_changes(self):
        if self.viewing_round <= 0 or not hasattr(self, 'txt_question'):
            return False

        current_q, current_r = self._capture_current_inputs()
        if self._saved_snapshot_round != self.viewing_round:
            return bool(current_q) or any(bool(v) for v in current_r.values())

        if current_q != self._saved_snapshot_question:
            return True
        for name, val in current_r.items():
            if val != self._saved_snapshot_replies.get(name, ""):
                return True
        for name, val in self._saved_snapshot_replies.items():
            if name not in current_r and val:
                return True
        return False

    def _on_app_close(self):
        if self._has_unsaved_text_changes():
            choice = messagebox.askyesnocancel(
                "尚未儲存",
                "偵測到目前有未儲存內容。\n\n是：保存並退出\n否：不保存並退出\n取消：不關閉程式"
            )
            if choice is None:
                return
            if choice:
                old_auto_advance = self._auto_advance.get()
                self._auto_advance.set(False)
                try:
                    self._submit_round(show_done_message=False, do_auto_advance=False)
                finally:
                    self._auto_advance.set(old_auto_advance)
                if self._has_unsaved_text_changes():
                    return
        self.root.destroy()

    # ═══════════════════════════════════════════════════════
    #  討論 UI
    # ═══════════════════════════════════════════════════════
    def _build_round_ui(self, round_num, saved_q="", saved_r=None, has_saved=False):
        if saved_r is None:
            saved_r = {}
        # 避免切換輪次時逐步重排造成可見抖動
        try:
            self.canvas.itemconfigure(self.canvas_win, state="hidden")
        except Exception:
            pass

        for w in self.frm_discuss.winfo_children():
            w.destroy()

        rn = f"第{round_num}輪"

        # 標題已移到上方輪次位置顯示

        # ── 上一輪摘要 ──
        if round_num > 1:
            prev_q, prev_r = read_round_files(self.topic_folder, round_num - 1, self.ai_list)
            if prev_q or prev_r:
                frm_prev = ttkb.Labelframe(self.frm_discuss,
                                            text=f"▼ 上一輪（第{round_num-1}輪）摘要",
                                            padding=5)
                frm_prev.pack(fill="x", padx=8, pady=(0, 5))
                txt_prev = scrolledtext.ScrolledText(frm_prev, height=5,
                                                      font=("Microsoft JhengHei", 9),
                                                      wrap="word")
                txt_prev.pack(fill="x")
                summary = ""
                if prev_q:
                    summary += f"【我的問題】\n{prev_q}\n\n"
                for ai_name, reply in prev_r.items():
                    preview = reply[:300] + ("..." if len(reply) > 300 else "")
                    summary += f"【{ai_name}】\n{preview}\n\n"
                txt_prev.insert("1.0", summary)
                txt_prev.config(state="disabled")

        # ── 提問區 ──
        frm_q = ttkb.Labelframe(self.frm_discuss, text="📝 本輪提問", padding=8)
        frm_q.pack(fill="x", padx=8, pady=(0, 5))

        # 章節路徑：只顯示鄰近 5 輪（插入路徑，不切換輪次）
        frm_chapter = ttkb.Frame(frm_q)
        frm_chapter.pack(fill="x", pady=(0, 4))
        ttkb.Label(frm_chapter, text="插入路徑：", font=("Microsoft JhengHei", 8)).pack(side="left")
        self.max_round = scan_max_round(self.topic_folder)
        total_rounds = max(round_num, self.max_round)
        window_size = 5
        start_round = max(1, round_num - (window_size // 2))
        end_round = min(total_rounds, start_round + window_size - 1)
        start_round = max(1, end_round - window_size + 1)
        for r in range(start_round, end_round + 1):
            rp = os.path.join(self.topic_folder, f"第{r}輪")
            label = f"第{r}輪"
            if r == round_num:
                label += " ★"
            ttkb.Button(
                frm_chapter,
                text=label,
                command=lambda p=rp: self._insert_path(p),
                bootstyle="outline"
            ).pack(side="left", padx=1)

        # 罐頭快捷按鈕（超過寬度自動換行）
        if self._canned:
            can_btns = [(c["name"], lambda idx=ci: self._insert_canned(idx), "info-outline")
                        for ci, c in enumerate(self._canned)]
            self._create_wrapping_buttons(frm_q, "罐頭：", can_btns, pady=(0, 4))

        self.txt_question= scrolledtext.ScrolledText(frm_q, height=7,
                                                       font=("Microsoft JhengHei", 10), wrap="word")
        self.txt_question.pack(fill="x")
        self._bind_text_focus(self.txt_question)
        self._place_expand_btn(frm_q, self.txt_question, "本輪提問")
        if saved_q:
            self.txt_question.insert("1.0", saved_q)
        elif not has_saved:
            # 新一輪：自動帶入開場白 + 結語
            auto_text = ""
            if self._use_opening.get():
                opening = self._get_active_opening()
                if opening:
                    auto_text += opening
            if self._use_closing.get():
                closing = self._get_active_closing()
                if closing:
                    if auto_text:
                        auto_text += "\n\n\n"
                    auto_text += closing
            if auto_text:
                self.txt_question.insert("1.0", auto_text)

        # ── 各 AI 回覆 ──
        self.ai_text_widgets = []
        for ai in self.ai_list:
            label_text = f"🤖 {ai['name']}"
            if ai.get('path'):
                label_text += f"　　{ai['path']}"
            frm_ai = ttkb.Labelframe(self.frm_discuss, text=label_text, padding=8)
            frm_ai.pack(fill="x", padx=8, pady=3)

            txt = scrolledtext.ScrolledText(frm_ai, height=4,
                                             font=("Microsoft JhengHei", 10), wrap="word")
            txt.pack(fill="x")
            self._bind_text_focus(txt)
            self._place_expand_btn(frm_ai, txt, ai['name'])
            if ai["name"] in saved_r:
                txt.insert("1.0", saved_r[ai["name"]])
            self.ai_text_widgets.append({"name": ai["name"], "path": ai.get("path", ""), "widget": txt})

        self._sync_saved_snapshot_from_widgets()
        self.frm_discuss.update_idletasks()
        try:
            self.canvas.itemconfigure(self.canvas_win, state="normal")
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
        self.canvas.yview_moveto(0)

    def _place_expand_btn(self, parent_frame, txt_widget, title):
        """在文字區域右下角放小放大按鈕"""
        bg = str(self.colors.inputbg)
        fg = str(self.colors.primary)
        btn = tk.Label(parent_frame, text="⤡", font=("Arial", 9), fg=fg,
                        bg=bg, cursor="hand2", bd=0, padx=0, pady=0)
        btn.bind('<Button-1>', lambda e: self._expand_text(txt_widget, title))
        btn.place(relx=1.0, rely=1.0, anchor="se", x=-30, y=-6)
        btn.lift()

    def _create_wrapping_buttons(self, parent, label_text, buttons_info, pady=(0, 2)):
        """建立可自動換行的按鈕列。"""
        if not buttons_info:
            return None

        wrapper = ttkb.Frame(parent)
        wrapper.pack(fill="x", pady=pady)
        ttkb.Label(wrapper, text=label_text, font=("Microsoft JhengHei", 8)).pack(anchor="w")

        flow = ttkb.Frame(wrapper)
        flow.pack(fill="x")

        btns = []
        for text, cmd, style in buttons_info:
            btns.append(ttkb.Button(flow, text=text, command=cmd, bootstyle=style))

        refresh_state = {"pending": False}
        layout_state = {"width": -1, "laid_out": False}

        def _relayout(force=False):
            max_width = max(1, flow.winfo_width() - 4)
            if (not force) and layout_state["laid_out"] and max_width == layout_state["width"]:
                return
            layout_state["width"] = max_width
            layout_state["laid_out"] = True

            for btn in btns:
                btn.grid_forget()

            used_width = 0
            row = 0
            col = 0
            for btn in btns:
                need = btn.winfo_reqwidth() + 8
                if col > 0 and used_width + need > max_width:
                    row += 1
                    col = 0
                    used_width = 0
                btn.grid(row=row, column=col, padx=(0, 4), pady=(0, 4), sticky="w")
                col += 1
                used_width += need

        def _schedule(event=None):
            if refresh_state["pending"]:
                return
            refresh_state["pending"] = True

            def _run():
                refresh_state["pending"] = False
                _relayout()

            flow.after_idle(_run)

        flow.bind("<Configure>", _schedule)
        _relayout(force=True)
        return wrapper

    def _insert_path(self, path):
        if hasattr(self, 'txt_question'):
            self.txt_question.insert(tk.INSERT, f"「{path}」")
            self.txt_question.focus_set()

    def _insert_canned(self, idx):
        if hasattr(self, 'txt_question') and 0 <= idx < len(self._canned):
            resolved = self._resolve_placeholders(self._canned[idx]["text"])
            self.txt_question.insert(tk.INSERT, resolved)
            self.txt_question.focus_set()

    def _expand_text(self, txt_widget, title):
        """放大編輯：在獨立視窗中編輯文字，關閉後回寫"""
        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        dlg.title(f"放大編輯 — {title}")
        dlg.geometry("780x820")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg_bg = str(getattr(self.colors, "bg", "#f2f2f2"))
        input_bg = txt_widget.cget("bg")
        input_fg = txt_widget.cget("fg")
        dlg.configure(bg=dlg_bg)

        big_txt = scrolledtext.ScrolledText(
            dlg,
            font=("Microsoft JhengHei", 11),
            wrap="word",
            bg=input_bg,
            fg=input_fg,
            insertbackground=input_fg
        )
        big_txt.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        content = txt_widget.get("1.0", tk.END).rstrip("\n")
        if content:
            big_txt.insert("1.0", content)

        def _save_and_close():
            new_content = big_txt.get("1.0", tk.END).rstrip("\n")
            txt_widget.delete("1.0", tk.END)
            if new_content:
                txt_widget.insert("1.0", new_content)
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _save_and_close)
        dlg.bind('<Escape>', lambda e: _save_and_close())
        dlg.bind('<Control-Return>', lambda e: (_save_and_close(), 'break')[1])

        btn_apply = ttkb.Button(dlg, text="確認回寫", command=_save_and_close,
                                 bootstyle="success")
        btn_apply.pack(pady=(0, 8))
        dlg.bind('<Control-s>', lambda e: (btn_apply.invoke(), 'break')[1])

        self._center_dialog(dlg, 780, 820)

    # ═══════════════════════════════════════════════════════
    #  儲存
    # ═══════════════════════════════════════════════════════
    def _submit_round(self, show_done_message=True, do_auto_advance=True):
        if not hasattr(self, 'txt_question') or self.viewing_round == 0:
            return
        question = self.txt_question.get("1.0", tk.END).strip()
        rn = f"第{self.viewing_round}輪"
        round_folder = os.path.join(self.topic_folder, rn)
        os.makedirs(round_folder, exist_ok=True)

        lines = [
            f"主題：{self.topic_var.get().strip()}",
            f"輪次：{rn}",
            f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60, "",
            "【本輪提問】", question, "",
            "=" * 60,
        ]
        for aw in self.ai_text_widgets:
            resp = aw["widget"].get("1.0", tk.END).strip()
            lines += ["", f"【{aw['name']}】的回覆"]
            if aw.get("path"):
                lines.append(f"專案路徑：{aw['path']}")
            lines += ["-" * 40, resp if resp else "（未填寫）", "", "=" * 60]

        # 根據設定決定輸出檔案（防呆：兩開關同時為 True 時，改成兩種都輸出）
        write_full = not self._no_full_record.get()
        write_split = not self._only_full_record.get()
        if (not write_full) and (not write_split):
            write_full = True
            write_split = True

        if write_full:
            with open(os.path.join(round_folder, f"{rn}_完整紀錄.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        if write_split:
            for aw in self.ai_text_widgets:
                resp = aw["widget"].get("1.0", tk.END).strip()
                with open(os.path.join(round_folder, f"{aw['name']}_回覆.txt"), "w", encoding="utf-8") as f:
                    f.write(f"AI 名稱：{aw['name']}\n")
                    if aw.get("path"):
                        f.write(f"專案路徑：{aw['path']}\n")
                    f.write(f"輪次：{rn}\n")
                    f.write("-" * 40 + "\n")
                    f.write(resp if resp else "（未填寫）")

            with open(os.path.join(round_folder, "提問.txt"), "w", encoding="utf-8") as f:
                f.write(question)

        self._sync_saved_snapshot_from_widgets()
        self._rebuild_accumulated()
        self.lbl_round.config(text=f"📖 {rn}（已儲存 ✔）")
        self._update_nav()
        if show_done_message:
            messagebox.showinfo("完成", f"{rn} 已儲存至：\n{round_folder}")

        # 自動進入下一輪
        if do_auto_advance and self._auto_advance.get():
            self._new_round()

    def _rebuild_accumulated(self):
        if not self.topic_folder:
            return
        mx = scan_max_round(self.topic_folder)
        all_lines = [
            f"主題：{self.topic_var.get().strip()}  —  全部討論累積紀錄",
            f"更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"AI 成員：{', '.join(a['name'] for a in self.ai_list)}",
            "=" * 60, "",
        ]
        for i in range(1, mx + 1):
            rn = f"第{i}輪"
            rp = os.path.join(self.topic_folder, rn, f"{rn}_完整紀錄.txt")
            if os.path.exists(rp):
                with open(rp, "r", encoding="utf-8") as f:
                    all_lines.append(f.read())
                all_lines.append("\n")
        with open(os.path.join(self.topic_folder, "全部討論紀錄（累積）.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(all_lines))

    # ═══════════════════════════════════════════════════════
    #  工具
    # ═══════════════════════════════════════════════════════
    @staticmethod
    def _open_path(path):
        """跨平台開啟檔案或資料夾"""
        if IS_WIN:
            os.startfile(path)
        elif IS_MAC:
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def _center_dialog(self, dlg, w, h):
        """將彈窗置中於主視窗（需先 withdraw，最後 deiconify）"""
        dlg.update_idletasks()
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        ry = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{max(rx,0)}+{max(ry,0)}")
        dlg.update_idletasks()
        dlg.deiconify()

    def _open_folder(self):
        if self.topic_folder and os.path.isdir(self.topic_folder):
            self._open_path(self.topic_folder)

    def _open_accumulated(self):
        if not self.topic_folder:
            return
        p = os.path.join(self.topic_folder, "全部討論紀錄（累積）.txt")
        if os.path.exists(p):
            self._open_path(p)
        else:
            messagebox.showinfo("提示", "尚無累積紀錄（送出至少一輪後產生）")

    # ═══════════════════════════════════════════════════════
    #  持久化
    # ═══════════════════════════════════════════════════════
    def _load_last_session(self):
        last = self.cfg.get("last_topic", "")
        self._refresh_topic_combo()
        if last and last in self.cfg.get("topics", {}):
            self._load_topic(last)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = App()
    app.run()
