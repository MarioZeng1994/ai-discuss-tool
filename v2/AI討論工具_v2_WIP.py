# -*- coding: utf-8 -*-
"""
AI 協作流程控制器
- 三窗口工作流程（架構師 A / 審查員 B / 執行者 C）
- 一鍵產生 CLI 指令 → 複製到剪貼簿 → 貼到 Copilot CLI / Claude CLI / Codex CLI / 其他AI
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

# CLI 指令清單：每個工具的所有常用指令 (指令, 說明)
CLI_COMMANDS = {
    "Copilot": [
        ("copilot", "啟動互動模式"),
        ("copilot -p \"prompt\"", "非互動模式，執行完直接結束"),
        ("copilot --allow-all", "全自動，跳過所有工具確認"),
        ("copilot --yolo", "同上，--allow-all 的別名"),
        ("copilot --allow-all-tools", "允許所有工具（腳本/CI 用途）"),
        ("copilot --allow-tool \"shell(npm run *)\"", "只允許特定 pattern 的工具"),
        ("copilot --deny-tool \"shell(rm *)\"", "封鎖特定工具（優先於 allow）"),
        ("copilot --allow-all-paths", "允許存取所有路徑（非互動模式必要）"),
        ("copilot --model claude-opus-4-6", "指定模型"),
        ("copilot --resume", "恢復上次 session"),
        ("copilot --continue", "直接繼續最近一次 session"),
        ("copilot --stream off", "關閉串流，完成後一次輸出"),
        ("copilot --experimental", "開啟實驗性功能"),
    ],
    "Claude": [
        ("claude", "啟動互動模式"),
        ("claude \"prompt\"", "帶初始 prompt 啟動"),
        ("claude -p \"prompt\"", "非互動模式，執行完直接結束"),
        ("claude -c", "繼續最近一次對話"),
        ("claude -r \"session-id\"", "指定 session ID 恢復"),
        ("claude --dangerously-skip-permissions", "全自動（YOLO mode）"),
        ("claude --permission-mode plan", "只規劃不執行，最安全"),
        ("claude --allowedTools \"Bash,Read,Edit\"", "指定允許的工具清單"),
        ("claude --model opus", "指定模型（opus/sonnet/haiku）"),
        ("claude --max-turns 3", "限制最多幾輪（非互動模式用）"),
        ("claude --add-dir ../lib", "加入額外可存取目錄"),
        ("claude --append-system-prompt \"用繁體中文\"", "追加 system prompt"),
        ("claude --verbose", "顯示詳細 debug log"),
    ],
    "Codex": [
        ("codex", "啟動互動模式"),
        ("codex exec \"prompt\"", "非互動模式，自動執行到結束"),
        ("codex --full-auto", "全自動低摩擦模式"),
        ("codex --yolo", "完全繞過審批與沙箱"),
        ("codex -a on-request", "審批模式：只在必要時問（預設）"),
        ("codex --sandbox workspace-write", "沙箱模式：允許寫入 workspace"),
        ("codex --model gpt-5-codex", "指定模型"),
        ("codex --resume", "恢復上次 session"),
        ("codex --cd /path/to/project", "指定工作目錄"),
        ("codex --json", "輸出 JSON 格式（腳本用）"),
    ],
}


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
IRON_RULES = """重點鐵規則「{ending_rule}」!!!
在每輪對話中必須遵守的行為規則：{ending_rule}。
我不會代碼，你跟我溝通使用自然語言（中文白話）。

品質要求（每次回覆都遵守）：
- 做任何決定前，先完整思考所有相關因素，不要跳步驟
- 不確定的事情寧可問業主，絕不亂猜
- 回覆前自我檢查：「我有沒有遺漏什麼？有沒有跟規格書矛盾？」
- 引用具體的行號、函式名、檔案路徑，不要說模糊的「那個地方」
- 如果任務複雜，先列出步驟清單，再逐步執行，每步完成後回報

規格合規要求（改代碼前必做）：
- 改任何 CSS / JS / 圖表前，先確認視覺樣式規格書的對應章節
- 使用任何報表名詞或標籤前，先對照全報表名詞手冊的統一用語
- 字體大小、顏色值、閾值等具體數值，不確定就查規格書，不要猜"""

# ──────────────────────────────────────
# 窗口開場指令模板
# ──────────────────────────────────────
A_TEMPLATE = """{iron_rules}

你今天是架構師。
先讀以下文件（全部讀完再說話）：
1. @{shared}/{memory_file}
2. @{shared}/AI_常見錯誤備忘.md
3. @{shared}/PROJECT_STATE.md  ← 特別注意「歷史未完成項」
（以下包含視覺規格書等，全部讀完再說話——規格書的具體數值要記住，後面寫進 SPEC）
{extra_a_files}
⚠️ 特別提醒：如果上面有視覺樣式規格書，請記錄關鍵數值，本輪 SPEC 的「視覺規格摘錄」必須包含真實數字。

讀完後，我會把本輪所有需求丟給你。

收到需求後，你的第一件事永遠是「任務分割與評估」，不是寫規格書。

⚠️⚠️⚠️ 重要：業主可能一次丟很多需求（5項、10項、甚至20+項含子項），這是正常的。
不管業主丟多少需求，你都要自動完成以下分割流程。

━━ 任務分割流程（必做）━━

Step 1：逐條拆解
業主的需求可能混在一起、有巢狀子項（如 6-2-1）、有些是新功能有些是修 bug。
你要把它們拆成獨立的工程任務，每個任務是一個可獨立完成的改動單元。

Step 2：逐條分析（用表格呈現）
| # | 任務摘要 | 類型 | 改動範圍 | 依賴 | 風險 | 工程量 |
|---|---------|------|---------|------|------|--------|
| 1 | xxx | 新功能/Bug修復/樣式 | 哪些檔案/函式 | 需先完成# | 高/中/低 | 大/中/小 |

Step 3：分輪建議
- 本輪做哪些（最多 5 個🔴必做 + 2 個🟡盡量）
- 下輪做哪些（說明原因：工程量太大 / 有前置依賴 / 風險需隔離）
- 暫緩的（說明原因）

分輪原則：
1. 有依賴關係的，先做前置任務
2. 風險高的單獨一輪（避免連鎖出錯）
3. 同類型的放一起（多個樣式調整放同輪）
4. 一輪超過 5 個🔴會導致完成度嚴重下降，寧可多分幾輪
5. 如果業主需求少於 5 項且都不複雜，全部放本輪即可，不用硬拆

Step 4：風險預警
- 跟歷史未完成項有關的任務，特別標注
- 可能互相衝突的任務，特別標注
- 改動範圍大的任務，說明「改錯了會影響什麼」

━━━━━━━━━━━━━━━━━━━

把以上分析存到 _窗口A_規劃/任務評估_本輪.md。
等我確認本輪要做哪些後，才開始寫規格書。
規格書存到 _窗口A_規劃/SPEC_本輪.md。

⚠️ 如果規格書包含任何圖表需求（圓餅/環形圖/Chart.js/字體大小）：
SPEC_本輪.md 必須加入「視覺規格摘錄」段落，把關鍵數值直接寫進去，例如：

## 視覺規格摘錄（圖表相關）
- 圓餅/環形圖 canvas：320px，cutout：60%
- centerText：標題 bold 15px，數值 bold 20px
- leaderPlugin 閾值：< 0.5%
- datalabels bar 內：11px weight 500，line：12px weight 700

不要只寫「依照視覺樣式規格書」——要把實際數字寫進規格書，讓 C 不需要翻規格書就能確認。

鐵律：{ending_rule}。"""

B_TEMPLATE = """{iron_rules}

你今天是審查員，工作是挑毛病，不是幫忙修。

⚠️ 審查範圍：只限 SPEC_本輪.md 這一份規格書。
不要去讀或審查專案的代碼（.py / .js / .html 等）。
不要翻 app/main.py、adapters/ 等程式碼檔案。
你的工作只是看規格書寫得好不好，讓工程師能照著做。

先讀：
1. @{shared}/{memory_file}  ← 了解專案背景
2. @{shared}/AI_常見錯誤備忘.md  ← 過去踩過的坑
3. @_窗口A_規劃/SPEC_本輪.md  ← ★ 你唯一要審查的東西

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

鐵律：{ending_rule}。"""

C_TEMPLATE = """{iron_rules}

你今天是執行工程師。
先讀（全部讀完再說話）：
1. @{shared}/{memory_file}
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

⚠️ 如果本輪包含圖表（圓餅/甜甜圈/環形圖/Chart.js bar/line/doughnut）：
「執行前確認」必須包含「圖表規格確認」段落，格式如下：

## 圖表規格確認
- canvas 容器高度：[你的實際值] → 規格應為 320px ✓/✗
- cutout：[你的實際值] → 規格應為 60% ✓/✗
- centerText 標題字體：[你的實際值] → 規格應為 bold 15px ✓/✗
- centerText 數值字體：[你的實際值] → 規格應為 bold 20px ✓/✗
- leaderPlugin 閾值：[你的實際值] → 規格應為 < 0.5% ✓/✗（舊版是 2%，已更新，別用舊的）
- datalabels bar 內字體：[你的實際值] → 規格應為 11px weight 500 ✓/✗
- datalabels line 字體：[你的實際值] → 規格應為 12px weight 700 ✓/✗
- legend 字體：[你的實際值] → 規格應為 11px ✓/✗

填入你的實際值後，有任何 ✗ → 先修正再繼續，不要跳過。
數值不確定時，查對 @{shared}/圓餅_環形圖規格卡.md 和 @{shared}/字體大小規格卡.md。

完成後必須做以下 3 件事（缺一不可）：

1. 輸出「瀏覽器操作清單」存到 _窗口C_執行/操作清單_本輪.md：
   格式：「打開瀏覽器 → 做[X動作] → 應該看到[Y結果]」
   沒把握完成的項目，在旁邊標注 ⚠️ + 說明不確定的原因

2. 輸出 CHANGELOG 存到 _窗口C_執行/CHANGELOG_本輪.md：
   格式：「改了[函式名]的[哪個部分]，原因是[規格書第N點]」

3. 檢查 _共用文件 的規格書是否需要更新（視覺樣式規格書、全報表名詞手冊、全域時間規格書）：
   如果你新增或修改了任何樣式、格式、名詞，必須直接更新對應的規格書。不需要問我，直接改。

鐵律：
- {ending_rule}
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
- {ending_rule}"""

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

QUICK_C_TEMPLATE = """以下是本輪需求（快速模式，直接執行）：

{requirement}

執行前確認（列完後等我說「可以開始」再動代碼）：
- 列出你要改的地方（函式名 + 行號 + 改什麼）
- 確認改動不影響其他已完成的功能
- 有不確定的地方先問我，不要猜

完成後必須輸出：
1. 操作清單（_窗口C_執行/操作清單_本輪.md）
2. CHANGELOG（_窗口C_執行/CHANGELOG_本輪.md）"""

# ──────────────────────────────────────
# 初始化指令模板（讓 AI 客製化 MD 檔）
# ──────────────────────────────────────
INIT_PROMPT_TEMPLATE = """你好，我需要你幫我設定這個專案的 AI 協作環境。

# 專案資訊
- 專案名稱：{project_name}
- 代碼資料夾：{code_folder}
- 專案路徑：{project_path}
- 專案類型：{project_type}

# 業主背景
- 代碼能力：{user_level}
（請根據業主的程度調整溝通方式和文件的技術深度）

# 業主提供的專案描述
{project_desc}

# 你的任務
請根據上面的資訊，幫我完善以下文件（它們已經建立了基本框架，你需要補充具體內容）：

1. @_共用文件/CLAUDE.md  # AI 的長期記憶，補充「專案簡介」和「架構備註」
2. @_共用文件/AGENTS.md  # 同上，給 Codex 用的版本，內容要跟 CLAUDE.md 同步
3. @_共用文件/AI_常見錯誤備忘.md  # 如果你已經知道這類專案常見的踩坑，先寫幾條
4. @_共用文件/AI_執行前核對清單.md  # 根據專案特性，補充專案相關的核對項目
5. @_共用文件/DECISIONS.md  # 把業主描述中提到的決策記錄下來

請逐一讀取這些檔案，然後根據專案描述補充內容。
完成後告訴我你改了什麼，讓我確認。

# 完成後的下一步
設定檔完善後，請告訴業主：
1. 回到「AI 協作流程控制器」的「工作流程」Tab
2. 在 Step 1 寫第一個需求
3. 按照流程指引走 A → B → C 的完整流程
這樣就正式開始用 AI 多窗口協作了！"""

# ──────────────────────────────────────
# 核心文件模板（初始流程建立用）
# ──────────────────────────────────────
CLAUDE_MD_TEMPLATE = """# CLAUDE.md — AI 永久記憶（{project_name}）

> 這份文件是 AI 助手的「長期記憶」。每次開新對話，先讀這份文件。
> 注意：同目錄下有 AGENTS.md（給 Codex 用），兩份內容需保持同步。修改此文件時請一併更新 AGENTS.md。

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
- [ ] 如果涉及 CSS/樣式 → 我已查對視覺樣式規格書的對應章節（不靠記憶）
- [ ] 如果涉及圖表 → 我已完成圖表規格確認（canvas/字體/閾值逐項對照）
- [ ] 如果涉及報表名詞/標籤 → 我已查對全報表名詞手冊，用語一致
- [ ] 我的修改範圍不超出 CONSENSUS.md 所確認的內容
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

AGENTS_MD_TEMPLATE = """# AGENTS.md — Codex / 其他 AI 的記憶（{project_name}）

> 此文件供 OpenAI Codex CLI 或其他非 Claude 的 AI 工具讀取。
> 功能等同 CLAUDE.md，但格式適用於 Codex 的 AGENTS.md 慣例。
> 注意：同目錄下有 CLAUDE.md（給 Claude/Copilot 用），兩份內容需保持同步。修改此文件時請一併更新 CLAUDE.md。

## 專案簡介
- 專案名稱：{project_name}
- 代碼資料夾：{code_folder}
- 建立日期：{date}

## 行為規則
1. 每次回覆結尾都要確認下一步（問我「接下來要做什麼」或「這樣可以嗎」）
2. 用中文白話溝通，不用技術術語
3. 改代碼前先回報理解，等業主確認
4. 不做規格書外的修改

## 歷史踩坑記錄
（由 AI_常見錯誤備忘.md 詳細記錄）

## 架構備註
（隨專案進展補充）
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
        self._set_dark_titlebar(theme)

        # Icon
        self._setup_icon()

        # State
        self.current_project = self.cfg.get("last_project", "")
        self.workflow_step = 1  # 工作流程當前步驟
        self.has_charts_var = tk.BooleanVar(value=False)  # 本輪是否包含圖表/CSS修改
        self.is_quick_mode = tk.BooleanVar(value=False)  # 快速模式（跳過 A/B）
        self.user_level_var = tk.StringVar(value="完全不懂代碼")
        self.project_type_var = tk.StringVar(value="其他")
        self.round_type_var = tk.StringVar(value="功能新增")
        self._generated_init_prompt = ""  # 暫存預覽用的初始化指令

        # Build UI
        self._build_top_bar()
        self._build_notebook()
        self._build_status_bar()

        # Load project if exists
        if self.current_project and self.current_project in self.cfg.get("projects", {}):
            self._on_project_selected()

    # ── Windows Dark Titlebar ──
    @staticmethod
    def _set_dark_titlebar(theme_name):
        if not IS_WIN:
            return
        dark_themes = {"darkly", "cyborg", "solar", "superhero", "vapor"}
        try:
            import ctypes
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

    # ── Expand Text Dialog ──
    def _open_expand_dialog(self, source_text):
        """開啟放大編輯彈窗，編輯完畢後同步回原本的 Text widget"""
        dlg = tk.Toplevel(self.root)
        dlg.title("放大編輯")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.bind("<Escape>", lambda e: _on_ok())

        pad = ttkb.Frame(dlg, padding=10)
        pad.pack(fill=BOTH, expand=True)

        big_text = tk.Text(pad, wrap=tk.WORD,
                           font=("Consolas" if IS_WIN else "Menlo", 12))
        big_text.pack(fill=BOTH, expand=True, pady=(0, 8))

        # 複製原始內容
        content = source_text.get("1.0", tk.END)
        if content.endswith("\n"):
            content = content[:-1]
        big_text.insert("1.0", content)

        def _on_ok():
            new_content = big_text.get("1.0", tk.END)
            if new_content.endswith("\n"):
                new_content = new_content[:-1]
            source_text.delete("1.0", tk.END)
            source_text.insert("1.0", new_content)
            dlg.destroy()

        btn_row = ttkb.Frame(pad)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="確定", bootstyle="success",
                    command=_on_ok).pack(side=RIGHT)
        ttkb.Button(btn_row, text="取消", bootstyle="secondary-outline",
                    command=dlg.destroy).pack(side=RIGHT, padx=(0, 8))

        self._center_dialog(dlg, 750, 550)
        big_text.focus_set()

    # ── Scrollable Frame Helper ──
    def _make_scrollable(self, parent):
        """在 parent 內建立可捲動區域，回傳 (inner_frame, canvas)"""
        canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        vsb = ttkb.Scrollbar(parent, orient=VERTICAL, command=canvas.yview)
        inner = ttkb.Frame(canvas, padding=12)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        _busy = [False]

        def _sync(event=None):
            if _busy[0]:
                return
            _busy[0] = True
            try:
                cw = canvas.winfo_width()
                ch = canvas.winfo_height()
                rh = inner.winfo_reqheight()
                canvas.itemconfig(win_id, width=max(cw, 1),
                                  height=max(rh, ch))
                canvas.configure(scrollregion=canvas.bbox("all"))
            finally:
                _busy[0] = False

        inner.bind("<Configure>", _sync)
        canvas.bind("<Configure>", _sync)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        return inner, canvas

    def _setup_tab_scroll(self):
        """全域滑鼠滾輪：根據參考版本的邏輯處理捲動"""
        canvases = [self._setup_canvas, self._launch_canvas, self._work_canvas]

        def _on_mousewheel(event):
            try:
                w = self.root.winfo_containing(event.x_root, event.y_root)
                if w is None:
                    return
                # 取得當前分頁的 canvas
                tab_idx = self.nb.index(self.nb.select())
                canvas = canvases[tab_idx]
                # 若滑鼠在彈出視窗（Combobox 下拉等）上，不攔截
                if str(w.winfo_toplevel()) != str(canvas.winfo_toplevel()):
                    return
                # 若滑鼠在有焦點的 Text 上且該 Text 內容可捲 → 讓 Text 自己滾
                focused = self.root.focus_get()
                if isinstance(focused, tk.Text):
                    target = w
                    while target is not None:
                        if target is focused:
                            if focused.yview() != (0.0, 1.0):
                                return
                            break
                        try:
                            target = target.master
                        except Exception:
                            break
                # 檢查 canvas 內容是否需要捲動
                sr = canvas.cget("scrollregion")
                if sr:
                    parts = sr.split()
                    if len(parts) >= 4:
                        if float(parts[3]) <= canvas.winfo_height():
                            return
                # 檢查滑鼠是否在 canvas 範圍內
                mx = event.x_root - canvas.winfo_rootx()
                my = event.y_root - canvas.winfo_rooty()
                if 0 <= mx <= canvas.winfo_width() and 0 <= my <= canvas.winfo_height():
                    if IS_MAC:
                        delta = -1 * int(event.delta)
                    else:
                        delta = -1 * int(event.delta / 120)
                    if delta != 0:
                        canvas.yview_scroll(delta, 'units')
            except Exception:
                pass

        self.root.bind_all('<MouseWheel>', _on_mousewheel)

        # ── Combobox 滾輪攔截（參考既有專案經驗）──
        # 滑鼠在 Combobox 上滾輪 → 不切換選項，改成滾 canvas
        def _on_combobox_mousewheel(event):
            _on_mousewheel(event)
            return "break"

        self.root.bind_class("TCombobox", "<MouseWheel>", _on_combobox_mousewheel, add="+")

        # Combobox 下拉 Listbox 滾輪：只攔截 ComboboxPopdown 內的 Listbox
        def _is_popdown_listbox(widget):
            try:
                return widget.winfo_toplevel().winfo_class() == "ComboboxPopdown"
            except Exception:
                return False

        def _on_popdown_listbox_mousewheel(event):
            if not _is_popdown_listbox(event.widget):
                return
            try:
                if IS_MAC:
                    delta = -1 * int(event.delta)
                else:
                    delta = -1 * int(event.delta / 120)
                if delta != 0:
                    event.widget.yview_scroll(delta, 'units')
            except Exception:
                pass
            return "break"

        self.root.bind_class("Listbox", "<MouseWheel>", _on_popdown_listbox_mousewheel, add="+")

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

        self.tab_setup = ttkb.Frame(self.nb)
        self.tab_launch = ttkb.Frame(self.nb)
        self.tab_work = ttkb.Frame(self.nb)

        self.nb.add(self.tab_setup, text="  初始設定  ")
        self.nb.add(self.tab_launch, text="  啟動窗口  ")
        self.nb.add(self.tab_work, text="  工作流程  ")

        self._build_tab_setup()
        self._build_tab_launch()
        self._build_tab_work()
        self._setup_tab_scroll()

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
        inner, self._setup_canvas = self._make_scrollable(self.tab_setup)
        frm = inner

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

        # 技術欄位容器（整組一起顯示/隱藏，避免逐行 pack 導致畫面閃跳）
        self._tech_fields_frame = ttkb.Frame(frm)
        self._tech_fields_frame.pack(fill=X)

        row3 = ttkb.Frame(self._tech_fields_frame)
        row3.pack(fill=X, pady=4)
        ttkb.Label(row3, text="代碼資料夾：", width=12).pack(side=LEFT)
        self.setup_code_var = tk.StringVar(value="my_project")
        ttkb.Entry(row3, textvariable=self.setup_code_var, width=30).pack(side=LEFT, fill=X, expand=True)
        ttkb.Label(row3, text="（已有的程式碼放在這裡）", bootstyle="secondary").pack(side=LEFT, padx=4)

        row4 = ttkb.Frame(self._tech_fields_frame)
        row4.pack(fill=X, pady=4)
        ttkb.Label(row4, text="共用規格檔：", width=12).pack(side=LEFT)
        self.setup_shared_var = tk.StringVar(
            value="CLAUDE.md, AI_常見錯誤備忘.md, AI_執行前核對清單.md, PROJECT_STATE.md")
        ttkb.Entry(row4, textvariable=self.setup_shared_var, width=60).pack(side=LEFT, fill=X, expand=True)

        row5 = ttkb.Frame(self._tech_fields_frame)
        row5.pack(fill=X, pady=4)
        ttkb.Label(row5, text="C 額外讀檔：", width=12).pack(side=LEFT)
        self.setup_extra_c_var = tk.StringVar(value="adapters/html_dashboard_adapter.py")
        ttkb.Entry(row5, textvariable=self.setup_extra_c_var, width=60).pack(side=LEFT, fill=X, expand=True)

        # 說明
        self._setup_hint_label = ttkb.Label(frm, text="按「建立」後會自動建立資料夾結構和核心文件。\n"
                   "如果資料夾已存在，只會補建缺少的文件，不會覆蓋。",
                   bootstyle="info", wraplength=700)
        self._setup_hint_label.pack(anchor=W, pady=(12, 8))

        # 建立按鈕 + 預覽按鈕
        btn_step1_row = ttkb.Frame(frm)
        btn_step1_row.pack(fill=X, pady=8)
        ttkb.Button(btn_step1_row, text="Step 1：建立專案結構", bootstyle="success",
                    command=self._create_project).pack(side=LEFT)
        ttkb.Button(btn_step1_row, text="預覽專案結構", bootstyle="info-outline",
                    command=self._preview_project_structure).pack(side=LEFT, padx=(8, 0))

        # ── Step 2：使用者背景 + 專案描述 ──
        ttkb.Label(frm, text="Step 2：讓 AI 幫你客製化設定檔",
                   font=("", 12, "bold")).pack(anchor=W, pady=(8, 4))

        # 使用者程度
        level_row = ttkb.Frame(frm)
        level_row.pack(fill=X, pady=2)
        ttkb.Label(level_row, text="你的程度：", width=12).pack(side=LEFT)
        for lbl in ["完全不懂代碼", "略懂能看", "會寫代碼"]:
            ttkb.Radiobutton(level_row, text=lbl, variable=self.user_level_var,
                             value=lbl, bootstyle="info",
                             command=self._on_user_level_changed).pack(side=LEFT, padx=(0, 10))

        # 專案類型
        type_row = ttkb.Frame(frm)
        type_row.pack(fill=X, pady=2)
        ttkb.Label(type_row, text="專案類型：", width=12).pack(side=LEFT)
        type_choices = ["網站前端", "Python 工具/腳本", "數據分析報表", "自動化腳本", "手機 App", "其他"]
        type_combo = ttkb.Combobox(type_row, textvariable=self.project_type_var,
                                    values=type_choices, state="readonly", width=20)
        type_combo.pack(side=LEFT)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._update_desc_placeholder())

        # 專案描述
        desc_label_row = ttkb.Frame(frm)
        desc_label_row.pack(fill=X, pady=(6, 0))
        ttkb.Label(desc_label_row, text="用白話描述你的專案（越詳細，AI 幫你客製化得越好）：",
                   font=("", 10)).pack(side=LEFT)
        ttkb.Button(desc_label_row, text="放大編輯", bootstyle="info-outline",
                    command=lambda: self._open_expand_dialog(self.setup_desc_text)).pack(side=LEFT, padx=(8, 0))
        self.setup_desc_text = tk.Text(frm, height=4, wrap=tk.WORD,
                                       font=("Consolas" if IS_WIN else "Menlo", 10))
        self.setup_desc_text.pack(fill=X, pady=(0, 4))
        # 初始化：根據使用者程度隱藏技術欄位 + 更新描述引導文字
        self._on_user_level_changed()

        init_row = ttkb.Frame(frm)
        init_row.pack(fill=X, pady=(0, 4))
        ttkb.Button(init_row, text="產生初始化指令（預覽）", bootstyle="info",
                    command=self._generate_init_prompt).pack(side=LEFT)
        ttkb.Label(init_row,
                   text="← 建立完結構後，先預覽指令內容，再複製貼給 AI",
                   bootstyle="secondary", font=("", 9)).pack(side=LEFT, padx=(8, 0))

        # 結果/預覽顯示
        self.setup_result = tk.Text(frm, height=10, wrap=tk.WORD, state=tk.DISABLED,
                                    font=("Consolas" if IS_WIN else "Menlo", 10))
        self.setup_result.pack(fill=BOTH, expand=True, pady=(4, 0))

        # 預覽下方的複製按鈕
        self.setup_copy_row = ttkb.Frame(frm)
        self.setup_copy_row.pack(fill=X, pady=(4, 0))
        self.setup_copy_btn = ttkb.Button(self.setup_copy_row,
                                           text="複製上方指令到剪貼簿", bootstyle="success",
                                           command=self._copy_init_preview)
        # 初始隱藏，產生預覽後才顯示
        self.setup_copy_hint = ttkb.Label(self.setup_copy_row, text="", bootstyle="success")

    def _browse_project_path(self):
        path = filedialog.askdirectory(initialdir=DESKTOP)
        if path:
            self.setup_path_var.set(path)

    def _on_user_level_changed(self):
        """根據使用者程度顯示/隱藏技術欄位（單一容器，一次操作不閃跳）"""
        level = self.user_level_var.get()
        if level == "完全不懂代碼":
            self._tech_fields_frame.pack_forget()
            self.setup_code_var.set("my_project")
            self.setup_shared_var.set(
                "CLAUDE.md, AI_常見錯誤備忘.md, AI_執行前核對清單.md, PROJECT_STATE.md")
            self.setup_extra_c_var.set("")
        else:
            if not self._tech_fields_frame.winfo_ismapped():
                self._tech_fields_frame.pack(fill=X, before=self._setup_hint_label)
        self._update_desc_placeholder()

    def _update_desc_placeholder(self):
        """根據使用者程度和專案類型更新描述框的引導文字"""
        ptype = self.project_type_var.get()
        level = self.user_level_var.get()

        # 不懂代碼的人：用最白話的引導，不提任何技術名詞
        if level == "完全不懂代碼":
            placeholders = {
                "網站前端": "用你自己的話描述這個網站：\n- 這個網站是做什麼的？（例如：賣東西、展示作品、公司官網）\n- 使用者可以做什麼？（例如：登入、下單、看文章）\n- 有什麼特別的要求？",
                "Python 工具/腳本": "用你自己的話描述這個工具：\n- 這個工具幫你做什麼事？\n- 它要處理什麼資料？（例如：Excel 表格、文字檔）\n- 處理完要產出什麼？（例如：報表、圖表、整理好的檔案）",
                "數據分析報表": "用你自己的話描述報表需求：\n- 報表要呈現什麼內容？\n- 資料來源是什麼？（例如：每月的 Excel 檔案）\n- 要有什麼圖表？（例如：圓餅圖、長條圖）",
                "自動化腳本": "用你自己的話描述要自動化什麼：\n- 你每天/每週要重複做什麼事？\n- 希望電腦幫你自動完成哪些步驟？",
                "手機 App": "用你自己的話描述這個 App：\n- App 是做什麼的？（例如：記帳、點餐、管理客戶）\n- 使用者可以做什麼？\n- 有什麼特別的要求？",
                "其他": "用你自己的話描述你想做的東西：\n- 它是做什麼的？\n- 誰會用它？\n- 有什麼特別的要求？",
            }
        elif level == "略懂能看":
            placeholders = {
                "網站前端": "描述你的網站功能：\n- 這是什麼類型的網站？\n- 主要功能有哪些？\n- 是否需要登入、資料庫？\n- 技術不確定就寫「不確定，交給 AI 建議」",
                "Python 工具/腳本": "描述你的工具做什麼：\n- 這個工具的用途是什麼？\n- 讀取什麼檔案？輸出什麼結果？\n- 有沒有特別的需求？",
                "數據分析報表": "描述你的報表需求：\n- 要分析什麼數據？\n- 需要什麼圖表？\n- 要能篩選、排序嗎？",
                "自動化腳本": "描述要自動化什麼流程：\n- 目前手動做什麼事很花時間？\n- 希望自動化到什麼程度？",
                "手機 App": "描述你的 App 功能：\n- App 做什麼用的？\n- 有什麼核心功能？",
                "其他": "用白話描述你的專案：\n- 這個專案要做什麼？\n- 有什麼特別的需求？\n- 技術不確定的部分寫「不確定」就好",
            }
        else:  # 會寫代碼
            placeholders = {
                "網站前端": "描述你的網站功能，例如：\n- 這是什麼類型的網站？\n- 主要功能有哪些？\n- 是否需要登入、資料庫？\n- 用 React + Node.js 或純 HTML/CSS/JS",
                "Python 工具/腳本": "描述你的工具做什麼，例如：\n- 這是一個自動整理 Excel 報表的工具\n- 讀取多個 .xlsx 檔案，合併成一份摘要\n- 輸出 PDF 或 HTML 報表\n- 需要圖表（柱狀圖、圓餅圖等）",
                "數據分析報表": "描述你的報表需求，例如：\n- 用 Python 讀取 Excel/CSV 數據\n- 產生互動式 HTML 儀表板\n- 包含圖表（Chart.js / Plotly）\n- 需要篩選、排序功能",
                "自動化腳本": "描述要自動化什麼流程，例如：\n- 每天自動下載某網站的數據\n- 自動發送通知 email\n- 自動整理檔案到指定資料夾",
                "手機 App": "描述你的 App 功能，例如：\n- 記帳 App，記錄每天的花費\n- 有分類、統計、圖表功能\n- 用 React Native / Flutter",
                "其他": "用白話描述你的專案：\n- 這個專案要做什麼？\n- 用什麼技術？（不確定就寫「不確定」）\n- 有什麼特別的需求？",
            }

        placeholder = placeholders.get(ptype, placeholders["其他"])
        current = self.setup_desc_text.get("1.0", tk.END).strip()
        # 只在空白或還是預設值時才替換（收集所有級別的預設開頭來判斷）
        all_defaults = [
            "描述你的", "用你自己的話", "用白話描述",
        ]
        is_default = not current or any(current.startswith(d) for d in all_defaults)
        if is_default:
            self.setup_desc_text.delete("1.0", tk.END)
            self.setup_desc_text.insert("1.0", placeholder)

    def _copy_init_preview(self):
        """複製預覽中的初始化指令"""
        if self._generated_init_prompt:
            self._copy_to_clipboard(self._generated_init_prompt)
            self.setup_copy_hint.config(text="已複製！現在貼到 AI CLI 視窗")
            self.setup_copy_hint.pack(side=LEFT, padx=8)
            self.root.after(5000, lambda: self.setup_copy_hint.config(text=""))

    def _generate_init_prompt(self):
        name = self.setup_name_var.get().strip() or self.current_project
        code = self.setup_code_var.get().strip() or "my_project"
        base = self.setup_path_var.get().strip() or DESKTOP
        desc = self.setup_desc_text.get("1.0", tk.END).strip()

        if not name:
            messagebox.showwarning("提示", "請先填寫專案名稱")
            return
        if not desc or len(desc) < 10:
            messagebox.showwarning("提示", "請用白話描述你的專案（至少寫幾句話）")
            return

        proj_path = os.path.join(base, name)
        prompt = INIT_PROMPT_TEMPLATE.format(
            project_name=name,
            code_folder=code,
            project_path=proj_path,
            project_desc=desc,
            user_level=self.user_level_var.get(),
            project_type=self.project_type_var.get(),
        )
        self._generated_init_prompt = prompt

        # 顯示預覽（不自動複製）
        self.setup_result.config(state=tk.NORMAL)
        self.setup_result.delete("1.0", tk.END)
        self.setup_result.insert("1.0",
            "以下是將要貼給 AI 的指令（請確認後按下方「複製」按鈕）：\n"
            "─" * 40 + "\n\n"
            + prompt
        )
        self.setup_result.config(state=tk.DISABLED)

        # 顯示複製按鈕
        self.setup_copy_btn.pack(side=LEFT)
        self.status_var.set("已產生初始化指令，請預覽確認後按「複製」")

    # ══════════════════════════════════
    # Tab 2：啟動窗口
    # ══════════════════════════════════
    def _build_tab_launch(self):
        inner, self._launch_canvas = self._make_scrollable(self.tab_launch)
        frm = inner

        ttkb.Label(frm, text="啟動 CLI 窗口", font=("", 14, "bold")).pack(anchor=W, pady=(0, 8))

        # CLI 啟動指令
        cli_frame = ttkb.LabelFrame(frm, text="Step 1：啟動 CLI（複製後貼到終端機）")
        cli_frame.pack(fill=X, pady=(0, 12), padx=4, ipady=4, ipadx=4)

        # CLI 預設選擇按鈕
        preset_frame = ttkb.Frame(cli_frame)
        preset_frame.pack(fill=X, pady=(4, 4))
        for cli_name, style in [("Copilot", "info"), ("Claude", "warning"), ("Codex", "success")]:
            ttkb.Button(preset_frame, text=cli_name, bootstyle=style, width=10,
                        command=lambda n=cli_name: self._open_cli_picker(n)
                        ).pack(side=LEFT, padx=3)
        ttkb.Button(preset_frame, text="自訂指令", bootstyle="secondary", width=10,
                    command=self._enable_custom_cli
                    ).pack(side=LEFT, padx=3)

        self.cli_cmd_text = tk.Text(cli_frame, height=3, wrap=tk.WORD,
                                    font=("Consolas" if IS_WIN else "Menlo", 11))
        self.cli_cmd_text.pack(fill=X)
        self.cli_cmd_text.insert("1.0", "（請先選擇專案）")
        self.cli_cmd_text.config(state=tk.DISABLED)

        ttkb.Button(cli_frame, text="複製 CLI 啟動指令",
                    bootstyle="info", command=lambda: self._copy_text(self.cli_cmd_text)
                    ).pack(anchor=W, pady=(6, 0))

        # 開場指令按鈕 + 每個角色的 CLI 選擇
        ttkb.Label(frm, text="Step 2：選擇窗口角色（可各自選 CLI），複製開場指令",
                   font=("", 11)).pack(anchor=W, pady=(0, 8))

        cli_choices = ["Claude/Copilot", "Codex"]
        self.role_cli_vars = {}
        btn_frame = ttkb.Frame(frm)
        btn_frame.pack(fill=X, pady=(0, 8))

        for label, role, style in [
            ("A（架構師）", "A", "warning"),
            ("B（審查員）", "B", "danger"),
            ("C（執行者）", "C", "success"),
            ("D（秘書）", "D", "info"),
        ]:
            col = ttkb.Frame(btn_frame)
            col.pack(side=LEFT, padx=4, expand=True)
            ttkb.Button(col, text=label, bootstyle=style, width=14,
                        command=lambda r=role: self._show_opening(r)
                        ).pack()
            cli_var = tk.StringVar(value="Claude/Copilot")
            self.role_cli_vars[role] = cli_var
            ttkb.Combobox(col, textvariable=cli_var, values=cli_choices,
                          state="readonly", width=13).pack(pady=(2, 0))

        # 開場指令顯示
        self.opening_text = tk.Text(frm, height=20, wrap=tk.WORD,
                                    font=("Consolas" if IS_WIN else "Menlo", 10))
        self.opening_text.pack(fill=BOTH, expand=True)
        self.opening_text.insert("1.0", "← 點擊上方按鈕，產生對應窗口的開場指令")
        self.opening_text.config(state=tk.DISABLED)

        copy_frame = ttkb.Frame(frm)
        copy_frame.pack(fill=X, pady=(6, 0))
        ttkb.Button(copy_frame, text="複製開場指令", bootstyle="success",
                    command=lambda: self._copy_text(self.opening_text)).pack(side=LEFT)
        self.launch_hint = ttkb.Label(copy_frame, text="", bootstyle="success")
        self.launch_hint.pack(side=LEFT, padx=12)

        # 模型建議面板
        model_frame = ttkb.LabelFrame(frm, text="模型建議（參考用）")
        model_frame.pack(fill=X, pady=(12, 0), padx=4)
        model_info = (
            "A 架構師 → Claude Opus 4.6（規劃能力最強）\n"
            "B 審查員 → Claude Sonnet 4.6（審查夠用，省資源）\n"
            "C 執行者 → Claude Opus 4.6（寫代碼要用最強的）\n"
            "D 秘書   → Haiku 或 Sonnet（翻譯引導不需要最強）\n"
            "──────────────────────────────\n"
            "初學者：用 Copilot --allow-all 最簡單，一個指令搞定\n"
            "進階者：Claude CLI 可選模型（--model opus / sonnet）\n"
            "數學計算：Codex 比較適合，但寫前端代碼較弱"
        )
        ttkb.Label(model_frame, text=model_info, font=("", 9),
                   wraplength=700, justify=LEFT).pack(anchor=W, padx=8, pady=6)

    # ══════════════════════════════════
    # Tab 3：工作流程
    # ══════════════════════════════════
    def _build_tab_work(self):
        inner, self._work_canvas = self._make_scrollable(self.tab_work)
        frm = inner

        # 頂部：步驟指示 + 輪次 + 歷史按鈕
        top = ttkb.Frame(frm)
        top.pack(fill=X, pady=(0, 8))
        self.work_step_label = ttkb.Label(top, text="工作流程", font=("", 14, "bold"))
        self.work_step_label.pack(side=LEFT)
        self.work_round_label = ttkb.Label(top, text="", bootstyle="info")
        self.work_round_label.pack(side=RIGHT)
        ttkb.Button(top, text="歷史紀錄", bootstyle="info-outline",
                    command=self._show_history_dialog).pack(side=RIGHT, padx=(0, 8))

        # 中間：內容區（動態切換）
        self.work_content = ttkb.Frame(frm)
        self.work_content.pack(fill=BOTH, expand=True)

        # 初始化 Step 1
        self._build_work_step1()

    def _clear_work_content(self):
        for w in self.work_content.winfo_children():
            w.destroy()
        self._work_canvas.yview_moveto(0)

    # ── Step 1：輸入需求 ──
    def _build_work_step1(self):
        self._clear_work_content()
        self.workflow_step = 1
        self.work_step_label.config(text="Step 1 / 6：輸入需求")
        frm = self.work_content

        ttkb.Label(frm, text="把你的需求寫在下面（不管多少項都丟進來，A 會自動幫你分割排序）：",
                   font=("", 11)).pack(anchor=W, pady=(0, 4))

        # 模板按鈕
        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X, pady=(0, 4))
        ttkb.Button(btn_row, text="插入需求模板", bootstyle="outline",
                    command=self._insert_req_template).pack(side=LEFT, padx=(0, 4))
        ttkb.Button(btn_row, text="插入問題回報模板", bootstyle="warning-outline",
                    command=self._insert_issue_template).pack(side=LEFT, padx=(0, 4))
        ttkb.Button(btn_row, text="放大編輯", bootstyle="info-outline",
                    command=lambda: self._open_expand_dialog(self.req_text)).pack(side=LEFT)

        # 輪次類型
        type_row = ttkb.Frame(frm)
        type_row.pack(fill=X, pady=(0, 4))
        ttkb.Label(type_row, text="本輪性質：", font=("", 11)).pack(side=LEFT, padx=(0, 8))
        self.round_type_var.set("功能新增")
        for rt in ["功能新增", "功能優化", "Bug修復", "新模板開發", "樣式調整"]:
            ttkb.Radiobutton(type_row, text=rt, variable=self.round_type_var,
                             value=rt, bootstyle="info").pack(side=LEFT, padx=(0, 8))

        # 模式選擇
        mode_row = ttkb.Frame(frm)
        mode_row.pack(fill=X, pady=(0, 4))
        ttkb.Label(mode_row, text="模式：", font=("", 11)).pack(side=LEFT, padx=(0, 8))
        self.is_quick_mode.set(False)
        ttkb.Radiobutton(mode_row, text="完整模式（A→B→C，大任務用）",
                         variable=self.is_quick_mode, value=False,
                         bootstyle="success").pack(side=LEFT, padx=(0, 12))
        ttkb.Radiobutton(mode_row, text="快速模式（直接給C，小修補用）",
                         variable=self.is_quick_mode, value=True,
                         bootstyle="warning").pack(side=LEFT)
        ttkb.Label(mode_row, text="← 少於3項小改用快速", bootstyle="secondary",
                   font=("", 9)).pack(side=LEFT, padx=(8, 0))

        # 圖表/CSS 勾選（影響 Step 5 的自我核對提示）
        self.has_charts_var.set(False)  # 每輪重置
        chart_row = ttkb.Frame(frm)
        chart_row.pack(fill=X, pady=(2, 0))
        ttkb.Checkbutton(chart_row, text="本輪包含圖表 / CSS 視覺修改（啟用規格合規核對）",
                         variable=self.has_charts_var,
                         bootstyle="warning").pack(side=LEFT)
        ttkb.Label(chart_row, text="← 勾選後 Step 5 會附加規格自我核對要求",
                   bootstyle="secondary", font=("", 9)).pack(side=LEFT, padx=(8, 0))

        self.req_text = tk.Text(frm, height=14, wrap=tk.WORD,
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
        if self.is_quick_mode.get():
            self._go_quick_c()
            return
        self._clear_work_content()
        self.workflow_step = 2
        self.work_step_label.config(text="Step 2 / 6：貼到窗口 A（架構師）")
        frm = self.work_content

        ttkb.Label(frm, text="把以下指令複製，貼到窗口 A（架構師）：",
                   font=("", 11)).pack(anchor=W, pady=(0, 4))

        rtype = self.round_type_var.get()
        type_hint = ""
        if rtype == "新模板開發":
            type_hint = "\n（本輪是「新模板開發」，可能需要新的檔案結構和樣式設計，請特別留意）\n"
        elif rtype == "Bug修復":
            type_hint = "\n（本輪是「Bug修復」，重點是找到問題根源、精確修復，不要順便改其他東西）\n"
        elif rtype == "樣式調整":
            type_hint = "\n（本輪是「樣式調整」，重點是 CSS/視覺修改，請確認視覺樣式規格書）\n"
        elif rtype == "功能優化":
            type_hint = "\n（本輪是「功能優化」，是改善現有功能，不是新增功能）\n"

        full_prompt = (
            f"【本輪類型：{rtype}】{type_hint}\n"
            f"以下是本輪所有需求，請先做「任務分割與評估」（拆解→分析表格→分輪建議→風險預警），\n"
            f"不管需求多少項都要自動分割排序，等我確認後再寫規格書。\n\n{req}"
        )
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

        rtype = self.round_type_var.get()
        full_prompt = f"【本輪類型：{rtype}】\n\n以下是本輪需求，請進行任務評估：\n\n{self.current_req}"
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

        base_prompt = "CONSENSUS.md 已更新完成，請開始執行。\n先做「執行前確認」，列出你要改的所有地方，等我說「可以開始」。"
        if self.has_charts_var.get():
            chart_addon = (
                "\n\n⚠️【本輪含圖表/CSS修改】\n"
                "執行前確認必須包含「圖表規格確認」段落，逐項填入你的代碼實際值：\n"
                "- canvas 容器高度：[實際值] → 規格 320px\n"
                "- centerText 標題字體：[實際值] → 規格 bold 15px\n"
                "- centerText 數值字體：[實際值] → 規格 bold 20px\n"
                "- leaderPlugin 閾值：[實際值] → 規格 < 0.5%\n"
                "- datalabels bar 內：[實際值] → 規格 11px weight 500\n"
                "- datalabels line：[實際值] → 規格 12px weight 700\n"
                "- legend：[實際值] → 規格 11px\n\n"
                "完成代碼後，提交前必須輸出「規格合規核對表」確認所有數值符合規格。\n"
                "有任何 ✗ → 修正後重新輸出，不要只說「我知道了」。"
            )
            prompt = base_prompt + chart_addon
        else:
            prompt = base_prompt
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

    # ── 快速模式：直接給 C ──
    def _go_quick_c(self):
        self._clear_work_content()
        self.workflow_step = 2
        self.work_step_label.config(text="Step 2 / 3：貼到窗口 C（快速模式）")
        frm = self.work_content

        ttkb.Label(frm, text="快速模式：直接把以下指令複製，貼到窗口 C（執行者）：",
                   font=("", 11)).pack(anchor=W, pady=(0, 4))

        rtype = self.round_type_var.get()
        base = f"【本輪類型：{rtype}】\n\n" + QUICK_C_TEMPLATE.format(requirement=self.current_req)
        if self.has_charts_var.get():
            chart_addon = (
                "\n\n⚠️【本輪含圖表/CSS修改】\n"
                "執行前確認必須包含「圖表規格確認」段落，逐項填入你的代碼實際值：\n"
                "- canvas 容器高度：[實際值] → 規格 320px\n"
                "- centerText 標題字體：[實際值] → 規格 bold 15px\n"
                "- centerText 數值字體：[實際值] → 規格 bold 20px\n"
                "- leaderPlugin 閾值：[實際值] → 規格 < 0.5%\n"
                "- datalabels bar 內：[實際值] → 規格 11px weight 500\n"
                "- datalabels line：[實際值] → 規格 12px weight 700\n"
                "- legend：[實際值] → 規格 11px\n\n"
                "完成代碼後，提交前必須輸出「規格合規核對表」確認所有數值符合規格。\n"
                "有任何 ✗ → 修正後重新輸出，不要只說「我知道了」。"
            )
            prompt = base + chart_addon
        else:
            prompt = base

        self.step_quick_c_text = tk.Text(frm, wrap=tk.WORD,
                                         font=("Consolas" if IS_WIN else "Menlo", 10))
        self.step_quick_c_text.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.step_quick_c_text.insert("1.0", prompt)
        self.step_quick_c_text.config(state=tk.DISABLED)

        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=self._build_work_step1).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="複製", bootstyle="info",
                    command=lambda: self._copy_text(self.step_quick_c_text)).pack(side=LEFT)
        ttkb.Button(btn_row, text="C 完成了 → 前往 Step 3 / 3 驗收 →", bootstyle="success",
                    command=lambda: self._go_step6(from_quick=True)).pack(side=RIGHT)

    # ── Step 6：驗收 ──
    def _go_step6(self, from_quick=False):
        self._from_quick = from_quick
        self._clear_work_content()
        self.workflow_step = 6
        step_label = "Step 3 / 3：驗收結果" if from_quick else "Step 6 / 6：驗收結果"
        self.work_step_label.config(text=step_label)
        frm = self.work_content

        ttkb.Label(frm, text="執行者已完成改代碼。\n"
                   "請打開瀏覽器，按照操作清單（_窗口C_執行/操作清單_本輪.md）逐項測試。\n"
                   "測試完畢後，在下方記錄結果：",
                   font=("", 11), wraplength=700).pack(anchor=W, pady=(0, 8))

        verify_top_row = ttkb.Frame(frm)
        verify_top_row.pack(fill=X, pady=(0, 4))
        ttkb.Button(verify_top_row, text="放大編輯", bootstyle="info-outline",
                    command=lambda: self._open_expand_dialog(self.verify_text)).pack(side=LEFT)

        self.verify_text = tk.Text(frm, height=12, wrap=tk.WORD,
                                   font=("Consolas" if IS_WIN else "Menlo", 10))
        self.verify_text.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.verify_text.insert("1.0", ISSUE_TEMPLATE)

        back_cmd = self._go_quick_c if from_quick else self._go_step5
        btn_row = ttkb.Frame(frm)
        btn_row.pack(fill=X)
        ttkb.Button(btn_row, text="← 回上一步", bootstyle="secondary-outline",
                    command=back_cmd).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(btn_row, text="有問題 — 複製回報給 C（舊視窗）",
                    bootstyle="danger",
                    command=self._step6_report_issues).pack(side=LEFT, padx=(0, 4))
        ttkb.Button(btn_row, text="圖表問題 — 開新 C 視窗",
                    bootstyle="warning",
                    command=self._step6_new_c_window).pack(side=LEFT)
        ttkb.Button(btn_row, text="全部通過 — 本輪完成 ✔", bootstyle="success",
                    command=self._round_complete).pack(side=RIGHT)

    def _step6_report_issues(self):
        issues = self.verify_text.get("1.0", tk.END).strip()
        if issues:
            self._copy_to_clipboard(issues)
            self.status_var.set("已複製問題回報，貼到窗口 C")
        if getattr(self, '_from_quick', False):
            self._go_quick_c()  # 快速模式回到 quick C
        else:
            self._go_step5()  # 完整模式回到 Step 5

    def _step6_new_c_window(self):
        """圖表修正：複製含規格提醒的問題回報，建議開新 C 視窗（舊視窗歷史過長會稀釋規格注意力）"""
        issues = self.verify_text.get("1.0", tk.END).strip()
        proj = self._get_project()
        shared = "../_共用文件"

        spec_reminder = (
            "\n\n【圖表修正任務 — 請先查對規格卡再動代碼】\n"
            f"修正前必須查對：\n"
            f"  @{shared}/圓餅_環形圖規格卡.md\n"
            f"  @{shared}/字體大小規格卡.md\n\n"
            "修正後輸出「規格合規核對表」，填入代碼實際值 vs 規格值，確認全部 ✓ 才算完成。"
        )
        full_msg = (issues if issues else "（請填入驗收問題）") + spec_reminder

        self._copy_to_clipboard(full_msg)
        messagebox.showinfo(
            "圖表修正 — 開新 C 視窗",
            "已複製含規格提醒的問題回報。\n\n"
            "建議步驟：\n"
            "1. 到「啟動窗口」Tab → 點「窗口 C（執行者）」→ 複製開場指令\n"
            "2. 開新 Claude/Copilot 視窗，貼入開場指令\n"
            "3. 再把剛才複製的問題回報（含規格提醒）貼進去\n\n"
            "這樣新視窗的規格注意力最高，不會被舊對話歷史稀釋。"
        )

    def _round_complete(self):
        proj = self._get_project()
        if proj:
            old_round = proj.get("current_round", 1)
            # 存歷史紀錄
            history = proj.setdefault("round_history", [])
            history.append({
                "round": old_round,
                "requirement": getattr(self, 'current_req', '（無記錄）'),
                "round_type": self.round_type_var.get(),
                "mode": "快速" if self.is_quick_mode.get() else "完整",
                "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            proj["current_round"] = old_round + 1
            self.cfg["projects"][self.current_project] = proj
            save_config(self.cfg)
            self._update_project_state_file()
            # 自動備份
            self._backup_project(silent=True)

        messagebox.showinfo("完成",
            f"本輪（第 {old_round} 輪）完成！已自動備份。\n"
            f"下一輪：第 {proj.get('current_round', 2)} 輪")
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
        self._fill_setup_from_project()
        self.status_var.set(f"已切換到專案：{self.current_project}")

    def _fill_setup_from_project(self):
        """把專案設定回填到初始設定 Tab 的欄位"""
        proj = self._get_project()
        if not proj:
            return
        self.setup_name_var.set(self.current_project)
        folder = proj.get("folder", "")
        if folder:
            # 路徑是 base/name，取 base
            parent = os.path.dirname(folder)
            self.setup_path_var.set(parent if parent else folder)
        self.setup_code_var.set(proj.get("code_folder", ""))
        self.setup_shared_var.set(", ".join(proj.get("shared_files", [])))
        self.setup_extra_c_var.set(", ".join(proj.get("extra_c_files", [])))

    def _update_cli_command(self):
        proj = self._get_project()
        if not proj:
            return
        folder = proj.get("folder", "")
        code = proj.get("code_folder", "")
        code_path = os.path.join(folder, code) if code else folder

        cli_cmd = proj.get("cli_preset_cmd", "copilot --allow-all")
        cli_desc = proj.get("cli_preset_desc", "全自動，跳過所有工具確認")
        cmd = f"cd \"{code_path}\"  # 切換到專案資料夾\n{cli_cmd}  # {cli_desc}"
        self.cli_cmd_text.config(state=tk.NORMAL)
        self.cli_cmd_text.delete("1.0", tk.END)
        self.cli_cmd_text.insert("1.0", cmd)
        self.cli_cmd_text.config(state=tk.DISABLED)

    def _open_cli_picker(self, cli_name):
        """點了 Copilot/Claude/Codex 按鈕，跳出該工具的所有指令讓使用者選"""
        proj = self._get_project()
        if not proj:
            messagebox.showwarning("提示", "請先選擇專案")
            return

        commands = CLI_COMMANDS.get(cli_name, [])
        if not commands:
            return

        picker = tk.Toplevel(self.root)
        picker.withdraw()
        picker.title(f"選擇 {cli_name} 指令")
        picker.resizable(True, True)
        picker.transient(self.root)
        picker.grab_set()
        picker.bind("<Escape>", lambda e: picker.destroy())

        ttkb.Label(picker, text=f"{cli_name} — 點選要使用的指令",
                   font=("", 12, "bold")).pack(anchor=W, padx=12, pady=(12, 8))

        list_frame = ttkb.Frame(picker)
        list_frame.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

        scrollbar = ttkb.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        listbox = tk.Listbox(list_frame, font=("Consolas" if IS_WIN else "Menlo", 10),
                             yscrollcommand=scrollbar.set, activestyle="dotbox",
                             selectmode=tk.SINGLE)
        listbox.pack(fill=BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        for cmd, desc in commands:
            listbox.insert(tk.END, f"{cmd}  # {desc}")

        def on_select(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            chosen_cmd, chosen_desc = commands[idx]
            proj["cli_preset_cmd"] = chosen_cmd
            proj["cli_preset_desc"] = chosen_desc
            save_config(self.cfg)
            self._update_cli_command()
            self.status_var.set(f"已選擇：{chosen_cmd}")
            picker.destroy()

        listbox.bind("<Double-Button-1>", on_select)
        ttkb.Button(picker, text="確認選擇", bootstyle="success",
                    command=on_select).pack(pady=(0, 12))

        picker.update_idletasks()
        w, h = 700, min(400, 80 + len(commands) * 22)
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        picker.geometry(f"{w}x{h}+{x}+{y}")
        picker.deiconify()

    def _enable_custom_cli(self):
        """讓指令框變成可編輯，使用者自己打"""
        proj = self._get_project()
        if not proj:
            messagebox.showwarning("提示", "請先選擇專案")
            return
        folder = proj.get("folder", "")
        code = proj.get("code_folder", "")
        code_path = os.path.join(folder, code) if code else folder

        self.cli_cmd_text.config(state=tk.NORMAL)
        self.cli_cmd_text.delete("1.0", tk.END)
        self.cli_cmd_text.insert("1.0", f"cd \"{code_path}\"\n")
        self.status_var.set("自訂模式：請在指令框中輸入你要的 CLI 指令")

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

        ending = self.cfg.get("ending_rule", "每次回覆結尾都要確認下一步")
        iron = IRON_RULES.format(ending_rule=ending)

        # 根據角色選的 CLI 決定記憶檔名
        role_cli = self.role_cli_vars.get(role, tk.StringVar(value="Claude/Copilot")).get()
        memory_file = "AGENTS.md" if role_cli == "Codex" else "CLAUDE.md"

        if role == "A":
            text = A_TEMPLATE.format(iron_rules=iron, shared=shared,
                                     extra_a_files=extra_a, ending_rule=ending,
                                     memory_file=memory_file)
            hint = "貼到窗口 A（架構師）"
        elif role == "B":
            text = B_TEMPLATE.format(iron_rules=iron, shared=shared, ending_rule=ending,
                                     memory_file=memory_file)
            hint = "貼到窗口 B（審查員）"
        elif role == "C":
            text = C_TEMPLATE.format(iron_rules=iron, shared=shared,
                                     extra_c_files=extra_c, ending_rule=ending,
                                     memory_file=memory_file)
            hint = "貼到窗口 C（執行者）"
        else:
            text = D_TEMPLATE.format(iron_rules=iron, shared=shared, ending_rule=ending,
                                     memory_file=memory_file)
            hint = "貼到窗口 D（秘書）"

        self.opening_text.config(state=tk.NORMAL)
        self.opening_text.delete("1.0", tk.END)
        self.opening_text.insert("1.0", text)
        self.opening_text.config(state=tk.DISABLED)
        self.launch_hint.config(text=f"→ {hint}")

    # ══════════════════════════════════
    # 預覽 / 建立專案
    # ══════════════════════════════════
    def _preview_project_structure(self):
        """預覽專案結構，標示已建立 / 未建立"""
        name = self.setup_name_var.get().strip()
        base = self.setup_path_var.get().strip()
        code = self.setup_code_var.get().strip() or "my_project"

        if not name:
            # 也試試從已選專案取
            proj = self._get_project()
            if proj:
                name = self.current_project
                folder = proj.get("folder", "")
                base = os.path.dirname(folder) if folder else base
                code = proj.get("code_folder", code)
            else:
                messagebox.showwarning("提示", "請先輸入專案名稱，或從上方選擇已有的專案")
                return

        proj_root = os.path.join(base, name)
        root_exists = os.path.isdir(proj_root)

        dirs = [
            "_共用文件",
            "_窗口A_規劃",
            "_窗口A_規劃/歷史",
            "_窗口B_審查",
            "_窗口C_執行",
            "_共識",
        ]
        files = [
            "_共用文件/CLAUDE.md",
            "_共用文件/AI_常見錯誤備忘.md",
            "_共用文件/AI_執行前核對清單.md",
            "_共用文件/DECISIONS.md",
            "_共用文件/PROJECT_STATE.md",
            "_共用文件/AGENTS.md",
            "_共識/CONSENSUS.md",
        ]

        lines = []
        lines.append(f"專案路徑：{proj_root}")
        lines.append("")
        if root_exists:
            lines.append(f"📁 {name}/  ✅ 已建立")
        else:
            lines.append(f"📁 {name}/  ❌ 尚未建立（按「建立專案結構」可建立）")

        lines.append("")
        lines.append("── 資料夾 ──")
        for d in dirs:
            full = os.path.join(proj_root, d)
            mark = "✅" if os.path.isdir(full) else "❌"
            lines.append(f"  📂 {d}/  {mark}")

        lines.append("")
        code_path = os.path.join(proj_root, code) if code else ""
        if not code_path or not os.path.isdir(code_path):
            code_path_alt = os.path.join(base, code) if base else ""
            if code_path_alt and os.path.isdir(code_path_alt):
                code_mark = "✅"
                lines.append(f"  📂 {code}/  {code_mark}  （代碼資料夾，位於 {code_path_alt}）")
            else:
                lines.append(f"  📂 {code}/  ❌  （代碼資料夾，需自行準備）")
        else:
            lines.append(f"  📂 {code}/  ✅  （代碼資料夾）")

        lines.append("")
        lines.append("── 自動生成的文件 ──")
        for f in files:
            full = os.path.join(proj_root, f)
            mark = "✅" if os.path.isfile(full) else "❌"
            lines.append(f"  📄 {f}  {mark}")

        lines.append("")
        n_missing = sum(1 for d in dirs if not os.path.isdir(os.path.join(proj_root, d)))
        n_missing += sum(1 for f in files if not os.path.isfile(os.path.join(proj_root, f)))
        if not root_exists:
            lines.append(f"💡 專案尚未建立。按「建立專案結構」會自動建立所有 {n_missing + 1} 個項目。")
        elif n_missing > 0:
            lines.append(f"💡 有 {n_missing} 個項目尚未建立，按「建立專案結構」會自動補建。")
        else:
            lines.append("✅ 所有資料夾和文件都已存在，可直接使用。")

        # 彈窗顯示
        dlg = tk.Toplevel(self.root)
        dlg.title("專案結構預覽")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.withdraw()
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        txt = tk.Text(dlg, wrap=tk.WORD, font=("Consolas" if IS_WIN else "Menlo", 11),
                      width=60, height=28)
        txt.pack(fill=BOTH, expand=True, padx=10, pady=10)
        txt.insert("1.0", "\n".join(lines))
        txt.config(state=tk.DISABLED)

        ttkb.Button(dlg, text="關閉", bootstyle="secondary",
                    command=dlg.destroy).pack(pady=(0, 10))

        self._center_dialog(dlg, 580, 520)

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
            os.path.join(shared, "AGENTS.md"):
                AGENTS_MD_TEMPLATE.format(project_name=name, code_folder=code, date=date),
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

        # 顯示結果 + 下一步引導
        result = f"專案「{name}」建立完成！\n路徑：{proj_root}\n\n"
        if created:
            result += "新建項目：\n" + "\n".join(f"  {c}" for c in created)
        else:
            result += "（所有資料夾和文件都已存在，無需建立）"

        result += "\n\n" + "=" * 40
        result += "\n接下來請照這個順序做：\n"
        result += "─" * 40 + "\n"
        result += (
            "Step A：開 AI CLI 視窗\n"
            "  1. 到上方「啟動窗口」Tab\n"
            "  2. 點 Copilot / Claude / Codex（選你有的）\n"
            "  3. 複製 CLI 啟動指令\n"
            "  4. 開一個終端機，貼上去，按 Enter\n\n"
            "Step B：讓 AI 客製化設定檔\n"
            "  1. 回到這個「初始設定」Tab\n"
            "  2. 在上面選你的程度和專案類型\n"
            "  3. 在描述框寫清楚你的專案（越詳細越好）\n"
            "  4. 按「產生初始化指令（預覽）」\n"
            "  5. 看一下預覽內容沒問題 → 按「複製」\n"
            "  6. 貼到剛才開好的 AI CLI 視窗\n"
            "  7. AI 會幫你填好 CLAUDE.md 等設定檔\n\n"
            "Step C：開始工作\n"
            "  1. AI 設定完成後，到「工作流程」Tab\n"
            "  2. 在 Step 1 寫你的第一個需求\n"
            "  3. 按照流程走就對了！\n"
        )

        self.setup_result.config(state=tk.NORMAL)
        self.setup_result.delete("1.0", tk.END)
        self.setup_result.insert("1.0", result)
        self.setup_result.config(state=tk.DISABLED)

        self.status_var.set(f"專案「{name}」已建立 — 請看下方的下一步引導")

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
    # 歷史紀錄對話框
    # ══════════════════════════════════
    def _show_history_dialog(self):
        proj = self._get_project()
        if not proj:
            messagebox.showinfo("提示", "請先選擇專案")
            return
        history = proj.get("round_history", [])
        if not history:
            messagebox.showinfo("歷史紀錄", "目前沒有任何輪次紀錄。\n完成一輪工作後就會自動記錄。")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"歷史紀錄 — {self.current_project}")
        dlg.transient(self.root)
        dlg.grab_set()
        self._center_dialog(dlg, 650, 450)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        pad = ttkb.Frame(dlg, padding=12)
        pad.pack(fill=BOTH, expand=True)

        ttkb.Label(pad, text=f"專案「{self.current_project}」的輪次紀錄",
                   font=("", 13, "bold")).pack(anchor=W, pady=(0, 8))

        text = tk.Text(pad, wrap=tk.WORD, font=("Consolas" if IS_WIN else "Menlo", 10))
        scrollbar = ttkb.Scrollbar(pad, command=text.yview)
        text.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        text.pack(fill=BOTH, expand=True)

        for h in reversed(history):
            req_preview = h.get("requirement", "")[:200]
            if len(h.get("requirement", "")) > 200:
                req_preview += "..."
            text.insert(tk.END,
                f"第 {h.get('round', '?')} 輪 — {h.get('completed_at', '?')}\n"
                f"  類型：{h.get('round_type', '?')}  |  模式：{h.get('mode', '?')}\n"
                f"  需求：{req_preview}\n"
                f"{'─' * 50}\n"
            )
        text.config(state=tk.DISABLED)

        ttkb.Button(pad, text="關閉", bootstyle="secondary",
                    command=dlg.destroy).pack(anchor=E, pady=(8, 0))

    # ══════════════════════════════════
    # 備份功能
    # ══════════════════════════════════
    def _backup_project(self, silent=False):
        """備份專案的文件（_共用文件、_窗口A_規劃、_窗口B_審查、_窗口C_執行、_共識）"""
        import shutil
        proj = self._get_project()
        if not proj:
            if not silent:
                messagebox.showinfo("提示", "請先選擇專案")
            return

        proj_root = proj.get("folder", "")
        if not proj_root or not os.path.isdir(proj_root):
            if not silent:
                messagebox.showwarning("錯誤", f"專案路徑不存在：{proj_root}")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        backup_dir = os.path.join(proj_root, "_備份", timestamp)
        dirs_to_backup = ["_共用文件", "_窗口A_規劃", "_窗口B_審查", "_窗口C_執行", "_共識"]
        backed_up = []

        for d in dirs_to_backup:
            src = os.path.join(proj_root, d)
            if os.path.isdir(src):
                dst = os.path.join(backup_dir, d)
                shutil.copytree(src, dst)
                backed_up.append(d)

        if backed_up:
            if not silent:
                messagebox.showinfo("備份完成",
                    f"已備份到：\n{backup_dir}\n\n"
                    f"備份內容：\n" + "\n".join(f"  {d}" for d in backed_up))
            self.status_var.set(f"備份完成：{timestamp}")
        else:
            if not silent:
                messagebox.showinfo("提示", "沒有找到可備份的資料夾")

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
        self._center_dialog(dlg, 580, 480)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        pad = ttkb.Frame(dlg, padding=16)
        pad.pack(fill=BOTH, expand=True)

        ttkb.Label(pad, text="設定", font=("", 14, "bold")).pack(anchor=W, pady=(0, 12))

        # 主題
        row1 = ttkb.Frame(pad)
        row1.pack(fill=X, pady=4)
        ttkb.Label(row1, text="主題：", width=14).pack(side=LEFT)
        theme_var = tk.StringVar(value=self.cfg.get("theme", "darkly"))
        themes = ["darkly", "superhero", "cyborg", "vapor", "solar",
                  "cosmo", "flatly", "journal", "litera", "minty", "pulse"]
        ttkb.Combobox(row1, textvariable=theme_var, values=themes,
                      state="readonly", width=20).pack(side=LEFT)

        # 結尾規則（自訂 AI 回覆結尾的行為）
        row_end = ttkb.Frame(pad)
        row_end.pack(fill=X, pady=4)
        ttkb.Label(row_end, text="結尾規則：", width=14).pack(side=LEFT)
        ending_var = tk.StringVar(value=self.cfg.get("ending_rule", "每次回覆結尾都要確認下一步"))
        ttkb.Entry(row_end, textvariable=ending_var, width=45).pack(side=LEFT, fill=X, expand=True)
        ttkb.Label(pad, text="（這段文字會自動帶入所有角色的開場指令，告訴 AI 每次回覆結尾要做什麼）",
                   bootstyle="secondary", font=("", 9)).pack(anchor=W, pady=(0, 4))

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

        proj_btn_row = ttkb.Frame(pad)
        proj_btn_row.pack(fill=X, pady=(4, 0))
        ttkb.Button(proj_btn_row, text="編輯專案設定", bootstyle="info-outline",
                    command=edit_proj).pack(side=LEFT, padx=(0, 8))
        ttkb.Button(proj_btn_row, text="備份專案文件", bootstyle="warning-outline",
                    command=self._backup_project).pack(side=LEFT)

        def apply_settings():
            changed = False
            new_theme = theme_var.get()
            if new_theme != self.cfg.get("theme"):
                self.cfg["theme"] = new_theme
                changed = True
            new_ending = ending_var.get().strip()
            if new_ending and new_ending != self.cfg.get("ending_rule", "每次回覆結尾都要確認下一步"):
                self.cfg["ending_rule"] = new_ending
                changed = True
            if changed:
                save_config(self.cfg)
                messagebox.showinfo("提示", "設定已儲存。主題變更將在下次啟動時生效。")
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
