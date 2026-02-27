# -*- coding: utf-8 -*-
"""
AI 協作流程控制器
- 三窗口工作流程（架構師 A / 審查員 B / 執行者 C）
- 一鍵產生 CLI 指令 → 複製到剪貼簿 → 貼到 Copilot CLI
- 多專案管理
- ttkbootstrap 主題美化
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import json
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
CONFIG_FILE = os.path.join(DESKTOP, "AI流程控制器_config.json")

ICON_NAME_ICO = "玻璃球.ico"
ICON_NAME_ICNS = "玻璃球.icns"


def resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"projects": {}, "last_project": "", "theme": "darkly"}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────
# 鐵律（自動帶入所有開場指令）
# ──────────────────────────────────────
IRON_RULES = """重點鐵規則「你每次回覆結尾都用 ask_user」!!!
在每輪對話中必須遵守的行為規則：每次回覆的最後一個工具呼叫一定是 ask_user。
我不會代碼，你跟我溝通使用自然語言（中文白話）。

品質要求（每次回覆都遵守）：
- 做任何決定前，先完整思考所有相關因素，不要跳步驟
- 不確定的事情寧可問業主，絕不亂猜
- 回覆前自我檢查：「我有沒有遺漏什麼？有沒有跟規格書矛盾？」
- 引用具體的行號、函式名、檔案路徑，不要說模糊的「那個地方」
- 如果任務複雜，先列出步驟清單，再逐步執行，每步完成後回報"""

# ──────────────────────────────────────
# 窗口開場指令模板
# ──────────────────────────────────────
A_TEMPLATE = """{iron_rules}

你今天是架構師。
先讀以下文件（全部讀完再說話）：
1. @{shared}/CLAUDE.md
2. @{shared}/AI_常見錯誤備忘.md
3. @{shared}/PROJECT_STATE.md  ← 特別注意「歷史未完成項」
{extra_a_files}

讀完後，我會把本輪所有需求丟給你。

收到需求後，你的第一件事是「任務評估」，不是寫規格書：
逐條分析每個需求的：
- 改動範圍（只改樣式？還是涉及數據邏輯？）
- 與其他需求的依賴關係（A要先做才能做B）
- 風險（改錯了會影響哪些已完成的功能？）
- 歷史未完成項：這次有更好的方法嗎？

然後建議：本輪做哪些（不超過5項），下輪做哪些。
說明你的分輪理由，存到 _窗口A_規劃/任務評估_本輪.md。

等我確認後才開始寫規格書。
規格書存到 _窗口A_規劃/SPEC_本輪.md。

鐵律：每次回覆結尾必須確認下一步。"""

B_TEMPLATE = """{iron_rules}

你今天是審查員，工作是挑毛病，不是幫忙修。
先讀：
1. @{shared}/CLAUDE.md
2. @{shared}/AI_常見錯誤備忘.md
3. @_窗口A_規劃/SPEC_本輪.md  ← 你要審查的規格書

評審標準：只報告「如果不修，執行時會出錯或做錯」的問題。
「可以更好但不影響執行」的意見放到「建議修改」，不列必須修改。
不評審業主的商業決策（哪個功能先做、哪個暫緩），那不是你的工作。

用以下格式輸出，存到 _窗口B_審查/REVIEW_本輪.md：

## 總評（1句話）
## 四維評分（各1-5分 + 理由）
- 可執行性：工程師拿到這份文件能否直接動手？
- 完整性：數據接口、邊界情況有無遺漏？
- 一致性：有無前後矛盾？
- 風險識別：有無指出「這裡可能出錯」？
## 必須修改（不改執行時會出問題）
## 建議修改（改了更好但不強制）
## 我需要業主確認的問題

鐵律：每次回覆結尾必須確認下一步。"""

C_TEMPLATE = """{iron_rules}

你今天是執行工程師。
先讀（全部讀完再說話）：
1. @{shared}/CLAUDE.md
2. @{shared}/AI_常見錯誤備忘.md
3. @{shared}/AI_執行前核對清單.md
4. @{shared}/PROJECT_STATE.md  ← 特別注意「歷史未完成項」
5. @_共識/CONSENSUS.md
{extra_c_files}

讀完後做「執行前確認」：
- 逐項確認 AI_執行前核對清單.md，回報確認結果
- 列出你打算改的每一個地方（函式名 + 大約行號 + 改什麼）
- 列出規格書沒說清楚、需要我確認的地方
- 如果有歷史未完成項，說明這次打算用什麼不同的做法

等我說「可以開始」才動代碼。

完成後必須做以下 3 件事（缺一不可）：

1. 輸出「瀏覽器操作清單」存到 _窗口C_執行/操作清單_本輪.md：
   格式：「打開瀏覽器 → 做[X動作] → 應該看到[Y結果]」
   沒把握完成的項目，在旁邊標注 ⚠️ + 說明不確定的原因

2. 輸出 CHANGELOG 存到 _窗口C_執行/CHANGELOG_本輪.md：
   格式：「改了[函式名]的[哪個部分]，原因是[規格書第N點]」

3. 檢查 _共用文件 的規格書是否需要更新（視覺樣式規格書、全報表名詞手冊、全域時間規格書）：
   如果你新增或修改了任何樣式、格式、名詞，必須直接更新對應的規格書。不需要問我，直接改。

鐵律：
- 每次回覆結尾必須確認下一步
- 不做規格書外的任何修改
- 不做自我驗收——你沒有辦法真正跑HTML，驗收是業主的工作"""

D_TEMPLATE = """{iron_rules}

你是我的「小秘書」，我完全不懂代碼，你要用最白話的中文跟我溝通。
不准用任何技術術語，如果要提到技術概念，用比喻或生活化的說法。
例如：不要說「函式呼叫鏈」，要說「A 叫 B，B 再叫 C 去做事」。

你的工作：
1. 幫我翻譯 — 我會把架構師(A)、審查員(B)、執行者(C) 的回覆貼給你，你用白話跟我說他們在講什麼
2. 告訴我下一步 — 根據三窗口流程，告訴我現在該做什麼、該貼什麼、貼到哪個窗口
3. 追蹤進度 — 記住我們現在第幾輪、到哪個步驟了
4. 幫我寫指示 — 如果我要跟 A/B/C 說什麼，幫我寫好文字讓我複製貼上

先讀以下文件了解情況：
1. @{shared}/PROJECT_STATE.md

三窗口流程：
- 窗口 A（架構師）：負責規劃、寫規格書
- 窗口 B（審查員）：負責挑毛病、審查規格書
- 窗口 C（執行者）：負責改代碼
- 正確順序：A寫好 → B審查 → 有問題回A改 → B再審 → 通過後才給C
- A/B/C 可能會給你錯誤的「下一步」建議，不要聽他們的，以上面的流程為準

重要：
- 你不改代碼！你只負責翻譯和引導
- 如果 A/B/C 說的話你也不確定是什麼意思，就老實說你不確定，不要亂猜
- 每次回覆最後都要告訴我「你現在該做什麼」"""

# ──────────────────────────────────────
# 需求格式模板
# ──────────────────────────────────────
REQ_TEMPLATE = """以下是本輪需求（請逐條處理）：

🔴 必須完成：
1. [需求1]

🟡 盡量完成：
2. [需求2]

🔵 有空再做：
3. [需求3]

現況：[目前遇到什麼問題 / 現在的狀態]
驗收標準：[怎樣算做好了]"""

ISSUE_TEMPLATE = """以下是上輪驗收結果：

❌ 未完成 / 有問題：
1. [問題描述]
   - 現象：[我看到什麼]
   - 預期：[應該是什麼]

✅ 已完成：
1. [完成項目]

請根據以上結果修正。"""

# ──────────────────────────────────────
# 核心文件模板（初始流程建立用）
# ──────────────────────────────────────
CLAUDE_MD_TEMPLATE = """# CLAUDE.md — AI 永久記憶（{project_name}）

> 這份文件是 AI 助手的「長期記憶」。每次開新對話，先讀這份文件。

## 專案簡介
- 專案名稱：{project_name}
- 代碼資料夾：{code_folder}
- 建立日期：{date}

## 鐵規則（Iron Rules）
1. 每次回覆結尾用 ask_user
2. 用中文白話溝通，不用技術術語
3. 改代碼前先回報理解，等業主確認
4. 不做規格書外的修改

## 歷史踩坑記錄
（由 AI_常見錯誤備忘.md 詳細記錄）

## 架構備註
（隨專案進展補充）
"""

ERROR_MEMO_TEMPLATE = """# AI 常見錯誤備忘（{project_name}）

> 記錄 AI 曾經犯過的錯，避免重蹈覆轍。

## 格式
每條記錄：
- **日期**：YYYY-MM-DD
- **錯誤**：做了什麼
- **正確做法**：應該怎麼做
- **影響範圍**：哪些檔案/功能被影響

## 記錄
（尚無記錄）
"""

CHECKLIST_TEMPLATE = """# AI 執行前核對清單（{project_name}）

> 執行者（窗口C）改代碼前必須逐項確認。

## 核對項目

- [ ] 我已讀完 CLAUDE.md 和 AI_常見錯誤備忘.md
- [ ] 我已讀完 CONSENSUS.md（本輪共識規格）
- [ ] 我已讀完 PROJECT_STATE.md（歷史未完成項）
- [ ] 我列出了所有要改的地方（函式名 + 行號 + 改什麼）
- [ ] 我確認改動不會影響已完成的功能
- [ ] 規格書有不清楚的地方，我已經列出來問業主
- [ ] 歷史未完成項，我有不同的做法（如適用）
"""

DECISIONS_TEMPLATE = """# 決策紀錄（{project_name}）

> 記錄業主做過的重要決策，避免 AI 反覆提問。

## 格式
- **日期**：YYYY-MM-DD
- **決策**：決定了什麼
- **理由**：為什麼這樣決定
- **影響**：後續要注意什麼

## 記錄
（尚無記錄）
"""

PROJECT_STATE_TEMPLATE = """# 專案狀態（{project_name}）

> 記錄當前進度、已完成項、歷史未完成項。

## 當前輪次：第 1 輪

## 已完成功能
（尚無）

## 歷史未完成項
（尚無）

## 本輪任務
（尚未開始）

---
最後更新：{date}
"""

CONSENSUS_TEMPLATE = """# 共識規格書（{project_name}）

> 這份文件記錄經過架構師規劃 + 審查員審核後的最終共識。
> 執行者只能改這份文件裡確認的內容。

## 本輪共識
（尚未建立 — 等架構師規劃 + 審查員審核後填入）

## 已確認的規格
（無）

## 業主額外確認事項
（無）
"""


# ══════════════════════════════════════
# 主應用程式
# ══════════════════════════════════════
class App:
    def __init__(self):
        self.cfg = load_config()

        theme = self.cfg.get("theme", "darkly")
        self.style = Style(theme=theme)
        self.root = self.style.master
        self.root.title("AI 協作流程控制器")
        self.root.geometry("820x700")
        self.root.minsize(700, 550)

        # Windows dark titlebar
        if IS_WIN:
            self._set_dark_titlebar()

        # Icon
        self._setup_icon()

        # State
        self.current_project = self.cfg.get("last_project", "")
        self.workflow_step = 1  # 工作流程當前步驟

        # Build UI
        self._build_top_bar()
        self._build_notebook()
        self._build_status_bar()

        # Load project if exists
        if self.current_project and self.current_project in self.cfg.get("projects", {}):
            self._on_project_selected()

    # ── Windows Dark Titlebar ──
    def _set_dark_titlebar(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except Exception:
            pass

    # ── Icon ──
    def _setup_icon(self):
        try:
            if IS_WIN:
                ico = resource_path(ICON_NAME_ICO)
                if os.path.exists(ico):
                    self.root.iconbitmap(ico)
            elif IS_MAC:
                pass  # macOS uses .icns in app bundle
        except Exception:
            pass

    # ── Center Dialog ──
    def _center_dialog(self, dlg, w, h):
        dlg.withdraw()
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.deiconify()

    # ══════════════════════════════════
    # Top Bar（專案選擇列）
    # ══════════════════════════════════
    def _build_top_bar(self):
        bar = ttkb.Frame(self.root, padding=8)
        bar.pack(fill=X)

        ttkb.Label(bar, text="專案：", font=("", 11)).pack(side=LEFT)

        self.project_var = tk.StringVar(value=self.current_project or "（請選擇或新建專案）")
        projects = list(self.cfg.get("projects", {}).keys())
        self.project_combo = ttkb.Combobox(
            bar, textvariable=self.project_var, values=projects,
            state="readonly", width=25)
        self.project_combo.pack(side=LEFT, padx=(0, 8))
        self.project_combo.bind("<<ComboboxSelected>>", lambda e: self._on_project_selected())

        ttkb.Button(bar, text="新建專案", bootstyle="success-outline",
                    command=self._new_project_dialog).pack(side=LEFT, padx=4)

        ttkb.Button(bar, text="⚙ 設定", bootstyle="info-outline",
                    command=self._settings_dialog).pack(side=RIGHT)

    # ══════════════════════════════════
    # Notebook（三個 Tab）
    # ══════════════════════════════════
    def _build_notebook(self):
        self.nb = ttkb.Notebook(self.root, bootstyle="dark")
        self.nb.pack(fill=BOTH, expand=True, padx=8, pady=(4, 0))

        self.tab_setup = ttkb.Frame(self.nb, padding=12)
        self.tab_launch = ttkb.Frame(self.nb, padding=12)
        self.tab_work = ttkb.Frame(self.nb, padding=12)

        self.nb.add(self.tab_setup, text="  初始設定  ")
        self.nb.add(self.tab_launch, text="  啟動窗口  ")
        self.nb.add(self.tab_work, text="  工作流程  ")

        self._build_tab_setup()
        self._build_tab_launch()
        self._build_tab_work()

    # ── Status Bar ──
    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="就緒")
        bar = ttkb.Label(self.root, textvariable=self.status_var,
                         font=("", 9), bootstyle="inverse-dark", padding=(8, 4))
        bar.pack(fill=X, side=BOTTOM)

    # ══════════════════════════════════
    # Tab 1：初始設定
    # ══════════════════════════════════
    def _build_tab_setup(self):
        frm = self.tab_setup

        ttkb.Label(frm, text="建立新專案", font=("", 14, "bold")).pack(anchor=W, pady=(0, 12))

        # 專案名稱
        row1 = ttkb.Frame(frm)
        row1.pack(fill=X, pady=4)
        ttkb.Label(row1, text="專案名稱：", width=12).pack(side=LEFT)
        self.setup_name_var = tk.StringVar()
        ttkb.Entry(row1, textvariable=self.setup_name_var, width=30).pack(side=LEFT, fill=X, expand=True)

        # 專案路徑
        row2 = ttkb.Frame(frm)
        row2.pack(fill=X, pady=4)
        ttkb.Label(row2, text="專案路徑：", width=12).pack(side=LEFT)
        self.setup_path_var = tk.StringVar(value=DESKTOP)
        ttkb.Entry(row2, textvariable=self.setup_path_var, width=30).pack(side=LEFT, fill=X, expand=True)
        ttkb.Button(row2, text="瀏覽", bootstyle="outline",
                    command=self._browse_project_path).pack(side=LEFT, padx=(4, 0))

        # 代碼資料夾名稱
        row3 = ttkb.Frame(frm)
        row3.pack(fill=X, pady=4)
        ttkb.Label(row3, text="代碼資料夾：", width=12).pack(side=LEFT)
        self.setup_code_var = tk.StringVar(value="report_tool")
        ttkb.Entry(row3, textvariable=self.setup_code_var, width=30).pack(side=LEFT, fill=X, expand=True)
        ttkb.Label(row3, text="（已有的程式碼放在這裡）", bootstyle="secondary").pack(side=LEFT, padx=4)

        # 共用規格文件
        row4 = ttkb.Frame(frm)
        row4.pack(fill=X, pady=4)
        ttkb.Label(row4, text="共用規格檔：", width=12).pack(side=LEFT)
        self.setup_shared_var = tk.StringVar(
            value="CLAUDE.md, AI_常見錯誤備忘.md, AI_執行前核對清單.md, PROJECT_STATE.md")
        ttkb.Entry(row4, textvariable=self.setup_shared_var, width=60).pack(side=LEFT, fill=X, expand=True)

        # 執行者額外檔案
        row5 = ttkb.Frame(frm)
        row5.pack(fill=X, pady=4)
        ttkb.Label(row5, text="C 額外讀檔：", width=12).pack(side=LEFT)
        self.setup_extra_c_var = tk.StringVar(value="adapters/html_dashboard_adapter.py")
        ttkb.Entry(row5, textvariable=self.setup_extra_c_var, width=60).pack(side=LEFT, fill=X, expand=True)

        # 說明
        ttkb.Label(frm, text="按「建立」後會自動建立資料夾結構和核心文件。\n"
                   "如果資料夾已存在，只會補建缺少的文件，不會覆蓋。",
                   bootstyle="info", wraplength=700).pack(anchor=W, pady=(12, 8))

        # 建立按鈕
        ttkb.Button(frm, text="建立專案結構", bootstyle="success",
                    command=self._create_project).pack(anchor=W, pady=8)

        # 結果顯示
        self.setup_result = tk.Text(frm, height=12, wrap=tk.WORD, state=tk.DISABLED,
                                    font=("Consolas" if IS_WIN else "Menlo", 10))
        self.setup_result.pack(fill=BOTH, expand=True, pady=(4, 0))

    def _browse_project_path(self):
        path = filedialog.askdirectory(initialdir=DESKTOP)
        if path:
            self.setup_path_var.set(path)

    # ══════════════════════════════════
    # Tab 2：啟動窗口
    # ══════════════════════════════════
    def _build_tab_launch(self):
        frm = self.tab_launch

        ttkb.Label(frm, text="啟動 CLI 窗口", font=("", 14, "bold")).pack(anchor=W, pady=(0, 8))

        # CLI 啟動指令
        cli_frame = ttkb.LabelFrame(frm, text="Step 1：啟動 CLI（複製後貼到終端機）")
        cli_frame.pack(fill=X, pady=(0, 12), padx=4, ipady=4, ipadx=4)

        self.cli_cmd_text = tk.Text(cli_frame, height=3, wrap=tk.WORD,
                                    font=("Consolas" if IS_WIN else "Menlo", 11))
        self.cli_cmd_text.pack(fill=X)
        self.cli_cmd_text.insert("1.0", "（請先選擇專案）")
        self.cli_cmd_text.config(state=tk.DISABLED)

        ttkb.Button(cli_frame, text="複製 CLI 啟動指令",
                    bootstyle="info", command=lambda: self._copy_text(self.cli_cmd_text)
                    ).pack(anchor=W, pady=(6, 0))

        # 開場指令按鈕
        ttkb.Label(frm, text="Step 2：選擇窗口角色，複製開場指令",
                   font=("", 11)).pack(anchor=W, pady=(0, 8))

        btn_frame = ttkb.Frame(frm)
        btn_frame.pack(fill=X, pady=(0, 8))

        for label, role, style in [
            ("窗口 A（架構師）", "A", "warning"),
            ("窗口 B（審查員）", "B", "danger"),
            ("窗口 C（執行者）", "C", "success"),
            ("窗口 D（秘書）", "D", "info"),
        ]:
            ttkb.Button(btn_frame, text=label, bootstyle=style, width=16,
                        command=lambda r=role: self._show_opening(r)
                        ).pack(side=LEFT, padx=4, expand=True)

        # 開場指令顯示
        self.opening_text = tk.Text(frm, height=20, wrap=tk.WORD,
                                    font=("Consolas" if IS_WIN else "Menlo", 10))
        self.opening_text.pack(fill=BOTH, expand=True)
        self.opening_text.insert("1.0", "← 點擊上方按鈕，產生對應窗口的開場指令")
        self.opening_text.config(state=tk.DISABLED)

        copy_frame = ttkb.Frame(frm)
        copy_frame.pack(fill=X, pady=(6, 0))
        ttkb.Button(copy_frame, text="📋 複製開場指令", bootstyle="success",
                    command=lambda: self._copy_text(self.opening_text)).pack(side=LEFT)
        self.launch_hint = ttkb.Label(copy_frame, text="", bootstyle="success")
        self.launch_hint.pack(side=LEFT, padx=12)

    # ══════════════════════════════════
    # Tab 3：工作流程
    # ══════════════════════════════════
    def _build_tab_work(self):
        frm = self.tab_work

        # 頂部：步驟指示 + 輪次
        top = ttkb.Frame(frm)
        top.pack(fill=X, pady=(0, 8))
        self.work_step_label = ttkb.Label(top, text="工作流程", font=("", 14, "bold"))
        self.work_step_label.pack(side=LEFT)
        self.work_round_label = ttkb.Label(top, text="", bootstyle="info")
        self.work_round_label.pack(side=RIGHT)

        # 中間：內容區（動態切換）
        self.work_content = ttkb.Frame(frm)
        self.work_content.pack(fill=BOTH, expand=True)

        # 初始化 Step 1
        self._build_work_step1()

    def _clear_work_content(self):
        for w in self.work_content.winfo_children():
            w.destroy()

    # ── Step 1：輸入需求 ──
    def _build_work_step1(self):
        self._clear_work_content()
        self.workflow_step = 1
        self.work_step_label.config(text="Step 1 / 6：輸入需求")
        frm = self.work_content

        ttkb.Label(frm, text="把你的需求寫在下面：", font=("", 11)).pack(anchor=W, pady=(0, 4))

        # 模板按鈕
        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X, pady=(0, 4))
        ttkb.Button(btn_row, text="插入需求模板", bootstyle="outline",
                    command=self._insert_req_template).pack(side=LEFT, padx=(0, 4))
        ttkb.Button(btn_row, text="插入問題回報模板", bootstyle="warning-outline",
                    command=self._insert_issue_template).pack(side=LEFT)

        self.req_text = tk.Text(frm, height=16, wrap=tk.WORD,
                                font=("Consolas" if IS_WIN else "Menlo", 10))
        self.req_text.pack(fill=BOTH, expand=True, pady=(0, 8))

        ttkb.Button(frm, text="產生指令，前往 Step 2 →", bootstyle="success",
                    command=self._go_step2).pack(anchor=E)

    def _insert_req_template(self):
        self.req_text.delete("1.0", tk.END)
        self.req_text.insert("1.0", REQ_TEMPLATE)

    def _insert_issue_template(self):
        self.req_text.delete("1.0", tk.END)
        self.req_text.insert("1.0", ISSUE_TEMPLATE)

    # ── Step 2：貼到窗口 A ──
    def _go_step2(self):
        req = self.req_text.get("1.0", tk.END).strip()
        if not req:
            messagebox.showwarning("提示", "請先輸入需求內容")
            return
        self.current_req = req
        self._clear_work_content()
        self.workflow_step = 2
        self.work_step_label.config(text="Step 2 / 6：貼到窗口 A（架構師）")
        frm = self.work_content

        ttkb.Label(frm, text="把以下指令複製，貼到窗口 A（架構師）：",
                   font=("", 11)).pack(anchor=W, pady=(0, 4))

        full_prompt = f"以下是本輪需求，請進行任務評估：\n\n{req}"
        self.step2_text = tk.Text(frm, wrap=tk.WORD,
                                  font=("Consolas" if IS_WIN else "Menlo", 10))
        self.step2_text.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.step2_text.insert("1.0", full_prompt)
        self.step2_text.config(state=tk.DISABLED)

        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=self._build_work_step1).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="複製", bootstyle="info",
                    command=lambda: self._copy_text(self.step2_text)).pack(side=LEFT)
        ttkb.Button(btn_row, text="A 完成了 → 前往 Step 3 →", bootstyle="success",
                    command=self._go_step3).pack(side=RIGHT)

    # ── Step 3：貼到窗口 B ──
    def _go_step3(self):
        self._clear_work_content()
        self.workflow_step = 3
        self.work_step_label.config(text="Step 3 / 6：貼到窗口 B（審查員）")
        frm = self.work_content

        ttkb.Label(frm, text="窗口 A 已完成規格書。\n"
                   "現在把以下指令複製，貼到窗口 B（審查員）：",
                   font=("", 11)).pack(anchor=W, pady=(0, 4))

        prompt = "架構師已完成 SPEC_本輪.md，請開始審查。"
        self.step3_text = tk.Text(frm, wrap=tk.WORD,
                                  font=("Consolas" if IS_WIN else "Menlo", 10))
        self.step3_text.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.step3_text.insert("1.0", prompt)
        self.step3_text.config(state=tk.DISABLED)

        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=self._go_step2_back).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="複製", bootstyle="info",
                    command=lambda: self._copy_text(self.step3_text)).pack(side=LEFT)
        ttkb.Button(btn_row, text="B 完成了 → 前往 Step 4 →", bootstyle="success",
                    command=self._go_step4).pack(side=RIGHT)

    def _go_step2_back(self):
        """回到 step 2，保留原始需求"""
        self._clear_work_content()
        self.workflow_step = 2
        self.work_step_label.config(text="Step 2 / 6：貼到窗口 A（架構師）")
        frm = self.work_content

        ttkb.Label(frm, text="把以下指令複製，貼到窗口 A（架構師）：",
                   font=("", 11)).pack(anchor=W, pady=(0, 4))

        full_prompt = f"以下是本輪需求，請進行任務評估：\n\n{self.current_req}"
        self.step2_text = tk.Text(frm, wrap=tk.WORD,
                                  font=("Consolas" if IS_WIN else "Menlo", 10))
        self.step2_text.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.step2_text.insert("1.0", full_prompt)
        self.step2_text.config(state=tk.DISABLED)

        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=self._build_work_step1).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="複製", bootstyle="info",
                    command=lambda: self._copy_text(self.step2_text)).pack(side=LEFT)
        ttkb.Button(btn_row, text="A 完成了 → 前往 Step 3 →", bootstyle="success",
                    command=self._go_step3).pack(side=RIGHT)

    # ── Step 4：確認審查 ──
    def _go_step4(self):
        self._clear_work_content()
        self.workflow_step = 4
        self.work_step_label.config(text="Step 4 / 6：確認審查結果")
        frm = self.work_content

        ttkb.Label(frm, text="審查員已完成 REVIEW_本輪.md。\n"
                   "請閱讀審查結果，決定是否需要修改規格書：",
                   font=("", 11)).pack(anchor=W, pady=(0, 12))

        ttkb.Label(frm, text="如果有「必須修改」的項目：\n"
                   "→ 回到窗口 A 讓架構師修改規格書\n"
                   "→ 修改完再讓審查員重新審查\n\n"
                   "如果審查 OK：\n"
                   "→ 請在窗口 A 把最終版規格書內容同步到 _共識/CONSENSUS.md\n"
                   "→ 然後繼續下一步",
                   wraplength=700, bootstyle="info").pack(anchor=W, pady=(0, 12))

        # 可選：用戶手動輸入給 A 的修改指示
        ttkb.Label(frm, text="（可選）給架構師的修改指示：").pack(anchor=W, pady=(4, 0))
        self.step4_note = tk.Text(frm, height=5, wrap=tk.WORD,
                                  font=("Consolas" if IS_WIN else "Menlo", 10))
        self.step4_note.pack(fill=X, pady=(0, 8))

        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=self._go_step3).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="需要修改 → 複製修改指示回 A",
                    bootstyle="warning",
                    command=self._step4_revise).pack(side=LEFT)
        ttkb.Button(btn_row, text="審查 OK → 前往 Step 5 →", bootstyle="success",
                    command=self._go_step5).pack(side=RIGHT)

    def _step4_revise(self):
        note = self.step4_note.get("1.0", tk.END).strip()
        if note:
            self._copy_to_clipboard(f"審查員的意見如下，請修改規格書：\n\n{note}")
        else:
            self._copy_to_clipboard("請根據 _窗口B_審查/REVIEW_本輪.md 的「必須修改」修改規格書。")
        # 回到 Step 2/3 讓用戶再走一遍
        self._go_step2_back()

    # ── Step 5：貼到窗口 C ──
    def _go_step5(self):
        self._clear_work_content()
        self.workflow_step = 5
        self.work_step_label.config(text="Step 5 / 6：貼到窗口 C（執行者）")
        frm = self.work_content

        ttkb.Label(frm, text="共識已確認。\n"
                   "現在把以下指令複製，貼到窗口 C（執行者），讓他開始改代碼：",
                   font=("", 11)).pack(anchor=W, pady=(0, 4))

        prompt = "CONSENSUS.md 已更新完成，請開始執行。\n先做「執行前確認」，列出你要改的所有地方，等我說「可以開始」。"
        self.step5_text = tk.Text(frm, wrap=tk.WORD,
                                  font=("Consolas" if IS_WIN else "Menlo", 10))
        self.step5_text.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.step5_text.insert("1.0", prompt)
        self.step5_text.config(state=tk.DISABLED)

        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=self._go_step4).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="複製", bootstyle="info",
                    command=lambda: self._copy_text(self.step5_text)).pack(side=LEFT)
        ttkb.Button(btn_row, text="C 完成了 → 前往 Step 6 驗收 →", bootstyle="success",
                    command=self._go_step6).pack(side=RIGHT)

    # ── Step 6：驗收 ──
    def _go_step6(self):
        self._clear_work_content()
        self.workflow_step = 6
        self.work_step_label.config(text="Step 6 / 6：驗收結果")
        frm = self.work_content

        ttkb.Label(frm, text="執行者已完成改代碼。\n"
                   "請打開瀏覽器，按照操作清單（_窗口C_執行/操作清單_本輪.md）逐項測試。\n"
                   "測試完畢後，在下方記錄結果：",
                   font=("", 11), wraplength=700).pack(anchor=W, pady=(0, 8))

        self.verify_text = tk.Text(frm, height=12, wrap=tk.WORD,
                                   font=("Consolas" if IS_WIN else "Menlo", 10))
        self.verify_text.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.verify_text.insert("1.0", ISSUE_TEMPLATE)

        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=self._go_step5).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="有問題 — 複製問題回報給 C",
                    bootstyle="danger",
                    command=self._step6_report_issues).pack(side=LEFT)
        ttkb.Button(btn_row, text="全部通過 — 本輪完成 ✔", bootstyle="success",
                    command=self._round_complete).pack(side=RIGHT)

    def _step6_report_issues(self):
        issues = self.verify_text.get("1.0", tk.END).strip()
        if issues:
            self._copy_to_clipboard(issues)
            self.status_var.set("已複製問題回報，貼到窗口 C")
        self._go_step5()  # 回到 C 讓他修

    def _round_complete(self):
        proj = self._get_project()
        if proj:
            proj["current_round"] = proj.get("current_round", 1) + 1
            self.cfg["projects"][self.current_project] = proj
            save_config(self.cfg)
            self._update_project_state_file()

        messagebox.showinfo("完成", f"本輪完成！\n下一輪：第 {proj.get('current_round', 2)} 輪")
        self._build_work_step1()
        self._update_round_display()

    # ══════════════════════════════════
    # 核心方法
    # ══════════════════════════════════
    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("已複製到剪貼簿 ✔")
        self.root.after(3000, lambda: self.status_var.set("就緒"))

    def _copy_text(self, text_widget):
        text_widget.config(state=tk.NORMAL)
        content = text_widget.get("1.0", tk.END).strip()
        text_widget.config(state=tk.DISABLED)
        if content and content != "（請先選擇專案）":
            self._copy_to_clipboard(content)

    def _get_project(self):
        if self.current_project and self.current_project in self.cfg.get("projects", {}):
            return self.cfg["projects"][self.current_project]
        return None

    def _on_project_selected(self):
        self.current_project = self.project_var.get()
        self.cfg["last_project"] = self.current_project
        save_config(self.cfg)
        self._update_cli_command()
        self._update_round_display()
        self.status_var.set(f"已切換到專案：{self.current_project}")

    def _update_cli_command(self):
        proj = self._get_project()
        if not proj:
            return
        folder = proj.get("folder", "")
        code = proj.get("code_folder", "")
        code_path = os.path.join(folder, code) if code else folder

        cmd = f"cd \"{code_path}\"\ncopilot --allow-all"
        self.cli_cmd_text.config(state=tk.NORMAL)
        self.cli_cmd_text.delete("1.0", tk.END)
        self.cli_cmd_text.insert("1.0", cmd)
        self.cli_cmd_text.config(state=tk.DISABLED)

    def _update_round_display(self):
        proj = self._get_project()
        if proj:
            r = proj.get("current_round", 1)
            self.work_round_label.config(text=f"第 {r} 輪")

    def _show_opening(self, role):
        proj = self._get_project()
        if not proj:
            messagebox.showwarning("提示", "請先選擇或建立專案")
            return

        shared = "../_共用文件"

        extra_a = ""
        for i, f in enumerate(proj.get("shared_files", []), start=4):
            if f not in ["CLAUDE.md", "AI_常見錯誤備忘.md", "PROJECT_STATE.md",
                         "AI_執行前核對清單.md", "DECISIONS.md"]:
                extra_a += f"\n{i}. @{shared}/{f}"

        extra_c = ""
        for i, f in enumerate(proj.get("extra_c_files", []), start=6):
            extra_c += f"\n{i}. @{f}"

        if role == "A":
            text = A_TEMPLATE.format(iron_rules=IRON_RULES, shared=shared,
                                     extra_a_files=extra_a)
            hint = "貼到窗口 A（架構師）"
        elif role == "B":
            text = B_TEMPLATE.format(iron_rules=IRON_RULES, shared=shared)
            hint = "貼到窗口 B（審查員）"
        elif role == "C":
            text = C_TEMPLATE.format(iron_rules=IRON_RULES, shared=shared,
                                     extra_c_files=extra_c)
            hint = "貼到窗口 C（執行者）"
        else:
            text = D_TEMPLATE.format(iron_rules=IRON_RULES, shared=shared)
            hint = "貼到窗口 D（秘書）"

        self.opening_text.config(state=tk.NORMAL)
        self.opening_text.delete("1.0", tk.END)
        self.opening_text.insert("1.0", text)
        self.opening_text.config(state=tk.DISABLED)
        self.launch_hint.config(text=f"→ {hint}")

    # ══════════════════════════════════
    # 建立專案
    # ══════════════════════════════════
    def _create_project(self):
        name = self.setup_name_var.get().strip()
        base = self.setup_path_var.get().strip()
        code = self.setup_code_var.get().strip()

        if not name:
            messagebox.showwarning("提示", "請輸入專案名稱")
            return
        if not base or not os.path.isdir(base):
            messagebox.showwarning("提示", "專案路徑不存在")
            return

        proj_root = os.path.join(base, name)
        date = datetime.now().strftime("%Y-%m-%d")
        created = []

        # 建立子資料夾
        dirs = [
            "_共用文件",
            "_窗口A_規劃", "_窗口A_規劃/歷史",
            "_窗口B_審查",
            "_窗口C_執行",
            "_共識",
        ]
        for d in dirs:
            p = os.path.join(proj_root, d)
            if not os.path.exists(p):
                os.makedirs(p, exist_ok=True)
                created.append(f"[資料夾] {d}")

        # 建立核心文件
        shared = os.path.join(proj_root, "_共用文件")
        files = {
            os.path.join(shared, "CLAUDE.md"):
                CLAUDE_MD_TEMPLATE.format(project_name=name, code_folder=code, date=date),
            os.path.join(shared, "AI_常見錯誤備忘.md"):
                ERROR_MEMO_TEMPLATE.format(project_name=name),
            os.path.join(shared, "AI_執行前核對清單.md"):
                CHECKLIST_TEMPLATE.format(project_name=name),
            os.path.join(shared, "DECISIONS.md"):
                DECISIONS_TEMPLATE.format(project_name=name),
            os.path.join(shared, "PROJECT_STATE.md"):
                PROJECT_STATE_TEMPLATE.format(project_name=name, date=date),
            os.path.join(proj_root, "_共識", "CONSENSUS.md"):
                CONSENSUS_TEMPLATE.format(project_name=name),
        }
        for fp, content in files.items():
            if not os.path.exists(fp):
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(content)
                created.append(f"[文件] {os.path.relpath(fp, proj_root)}")

        # 解析共用規格檔
        shared_files = [s.strip() for s in self.setup_shared_var.get().split(",") if s.strip()]
        extra_c = [s.strip() for s in self.setup_extra_c_var.get().split(",") if s.strip()]

        # 存到 config
        self.cfg.setdefault("projects", {})[name] = {
            "folder": proj_root,
            "code_folder": code,
            "current_round": 1,
            "current_step": 1,
            "shared_files": shared_files,
            "extra_a_files": [],
            "extra_b_files": [],
            "extra_c_files": extra_c,
        }
        self.cfg["last_project"] = name
        save_config(self.cfg)

        # 更新 UI
        self.current_project = name
        self.project_var.set(name)
        projects = list(self.cfg.get("projects", {}).keys())
        self.project_combo.config(values=projects)
        self._on_project_selected()

        # 顯示結果
        result = f"專案「{name}」建立完成！\n路徑：{proj_root}\n\n"
        if created:
            result += "新建項目：\n" + "\n".join(f"  {c}" for c in created)
        else:
            result += "（所有資料夾和文件都已存在，無需建立）"

        self.setup_result.config(state=tk.NORMAL)
        self.setup_result.delete("1.0", tk.END)
        self.setup_result.insert("1.0", result)
        self.setup_result.config(state=tk.DISABLED)

        self.status_var.set(f"專案「{name}」已建立")

    # ══════════════════════════════════
    # PROJECT_STATE.md 更新
    # ══════════════════════════════════
    def _update_project_state_file(self):
        proj = self._get_project()
        if not proj:
            return
        state_path = os.path.join(proj["folder"], "_共用文件", "PROJECT_STATE.md")
        if not os.path.exists(state_path):
            return

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                content = f.read()

            r = proj.get("current_round", 1)
            date = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 更新輪次
            import re
            content = re.sub(
                r"## 當前輪次：第 \d+ 輪",
                f"## 當前輪次：第 {r} 輪",
                content)
            content = re.sub(
                r"最後更新：.*",
                f"最後更新：{date}",
                content)

            with open(state_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    # ══════════════════════════════════
    # 新建專案對話框（從頂部 bar 觸發）
    # ══════════════════════════════════
    def _new_project_dialog(self):
        self.nb.select(self.tab_setup)

    # ══════════════════════════════════
    # 設定對話框
    # ══════════════════════════════════
    def _settings_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("設定")
        dlg.transient(self.root)
        dlg.grab_set()
        self._center_dialog(dlg, 480, 400)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        pad = ttkb.Frame(dlg, padding=16)
        pad.pack(fill=BOTH, expand=True)

        ttkb.Label(pad, text="設定", font=("", 14, "bold")).pack(anchor=W, pady=(0, 12))

        # 主題
        row1 = ttkb.Frame(pad)
        row1.pack(fill=X, pady=4)
        ttkb.Label(row1, text="主題：", width=12).pack(side=LEFT)
        theme_var = tk.StringVar(value=self.cfg.get("theme", "darkly"))
        themes = ["darkly", "superhero", "cyborg", "vapor", "solar",
                  "cosmo", "flatly", "journal", "litera", "minty", "pulse"]
        ttkb.Combobox(row1, textvariable=theme_var, values=themes,
                      state="readonly", width=20).pack(side=LEFT)

        # 專案列表管理
        ttkb.Label(pad, text="已建立的專案：", font=("", 11)).pack(anchor=W, pady=(16, 4))

        proj_list = tk.Listbox(pad, height=6)
        proj_list.pack(fill=X, pady=(0, 4))
        for name in self.cfg.get("projects", {}):
            proj_list.insert(tk.END, name)

        def delete_proj():
            sel = proj_list.curselection()
            if not sel:
                return
            pname = proj_list.get(sel[0])
            if messagebox.askyesno("確認", f"從設定中移除專案「{pname}」？\n（不會刪除實際檔案）"):
                del self.cfg["projects"][pname]
                if self.cfg.get("last_project") == pname:
                    self.cfg["last_project"] = ""
                save_config(self.cfg)
                proj_list.delete(sel[0])
                projects = list(self.cfg.get("projects", {}).keys())
                self.project_combo.config(values=projects)

        def edit_proj():
            sel = proj_list.curselection()
            if not sel:
                messagebox.showinfo("提示", "請先選擇一個專案")
                return
            pname = proj_list.get(sel[0])
            self._edit_project_dialog(dlg, pname)

        ttkb.Button(pad, text="編輯專案設定", bootstyle="info-outline",
                    command=edit_proj).pack(anchor=W, pady=(4, 0))

        def apply_settings():
            new_theme = theme_var.get()
            if new_theme != self.cfg.get("theme"):
                self.cfg["theme"] = new_theme
                save_config(self.cfg)
                messagebox.showinfo("提示", "主題變更將在下次啟動時生效。")
            dlg.destroy()

        # 底部按鈕（左：移除，右：確定）
        bottom_row = ttkb.Frame(pad)
        bottom_row.pack(side=BOTTOM, fill=X, pady=(12, 0))
        ttkb.Button(bottom_row, text="從列表移除選中專案", bootstyle="danger-outline",
                    command=delete_proj).pack(side=LEFT)
        ttkb.Button(bottom_row, text="確定", bootstyle="success",
                    command=apply_settings).pack(side=RIGHT)

    # ── 編輯專案設定 ──
    def _edit_project_dialog(self, parent, pname):
        proj = self.cfg["projects"][pname]
        dlg = tk.Toplevel(parent)
        dlg.title(f"編輯專案：{pname}")
        dlg.transient(parent)
        dlg.grab_set()
        self._center_dialog(dlg, 550, 400)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        pad = ttkb.Frame(dlg, padding=16)
        pad.pack(fill=BOTH, expand=True)

        ttkb.Label(pad, text=f"專案：{pname}", font=("", 13, "bold")).pack(anchor=W, pady=(0, 12))

        # 路徑
        r1 = ttkb.Frame(pad)
        r1.pack(fill=X, pady=2)
        ttkb.Label(r1, text="路徑：", width=14).pack(side=LEFT)
        folder_var = tk.StringVar(value=proj.get("folder", ""))
        ttkb.Entry(r1, textvariable=folder_var, width=40).pack(side=LEFT, fill=X, expand=True)

        # 代碼資料夾
        r2 = ttkb.Frame(pad)
        r2.pack(fill=X, pady=2)
        ttkb.Label(r2, text="代碼資料夾：", width=14).pack(side=LEFT)
        code_var = tk.StringVar(value=proj.get("code_folder", ""))
        ttkb.Entry(r2, textvariable=code_var, width=40).pack(side=LEFT, fill=X, expand=True)

        # 輪次
        r3 = ttkb.Frame(pad)
        r3.pack(fill=X, pady=2)
        ttkb.Label(r3, text="當前輪次：", width=14).pack(side=LEFT)
        round_var = tk.StringVar(value=str(proj.get("current_round", 1)))
        ttkb.Entry(r3, textvariable=round_var, width=10).pack(side=LEFT)

        # 共用檔案
        r4 = ttkb.Frame(pad)
        r4.pack(fill=X, pady=2)
        ttkb.Label(r4, text="共用規格檔：", width=14).pack(side=LEFT)
        shared_var = tk.StringVar(value=", ".join(proj.get("shared_files", [])))
        ttkb.Entry(r4, textvariable=shared_var, width=50).pack(side=LEFT, fill=X, expand=True)

        # C 額外檔案
        r5 = ttkb.Frame(pad)
        r5.pack(fill=X, pady=2)
        ttkb.Label(r5, text="C 額外讀檔：", width=14).pack(side=LEFT)
        extra_c_var = tk.StringVar(value=", ".join(proj.get("extra_c_files", [])))
        ttkb.Entry(r5, textvariable=extra_c_var, width=50).pack(side=LEFT, fill=X, expand=True)

        def save_proj():
            proj["folder"] = folder_var.get().strip()
            proj["code_folder"] = code_var.get().strip()
            try:
                proj["current_round"] = int(round_var.get().strip())
            except ValueError:
                pass
            proj["shared_files"] = [s.strip() for s in shared_var.get().split(",") if s.strip()]
            proj["extra_c_files"] = [s.strip() for s in extra_c_var.get().split(",") if s.strip()]
            self.cfg["projects"][pname] = proj
            save_config(self.cfg)
            self.status_var.set(f"專案「{pname}」設定已更新")
            dlg.destroy()

        ttkb.Button(pad, text="儲存", bootstyle="success",
                    command=save_proj).pack(side=BOTTOM, anchor=E, pady=(12, 0))

    # ══════════════════════════════════
    # Run
    # ══════════════════════════════════
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = App()
    app.run()
