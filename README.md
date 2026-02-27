# AI 多窗口集中討論工具
“Windows 直接下載：到 Releases → v1.0.0 → 下載 ai-discuss-tool.exe.zip”
用一個桌面小工具，同時管理多個 AI「窗口」，用「主題 / 回合」把提問、回覆、完整紀錄存成檔案，方便回溯與整理。

> 這個 repo 同時提供：
> - 原始碼（可自己改）
> - Release 的 Windows `.exe`（可直接跑）

---

## 主要功能
- 建立 / 載入「主題」資料夾
- 支援多個 AI 成員（每個成員一個視窗）
- 每一輪可產生「提問 / 回覆 / 完整紀錄」檔案
- 深色主題（ttkbootstrap）
- Windows / macOS 可開啟輸出資料夾

---

## 安裝與執行（原始碼）
### 1) 建立環境
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2) 安裝依賴
```bash
pip install -r requirements.txt
```

### 3) 執行
```bash
python AI討論工具_最終版.py
```

---

## 打包成 Windows EXE（可選）
你可以用 PyInstaller 一鍵打包：

### 1) 安裝 PyInstaller
```bash
pip install pyinstaller
```

### 2) 直接跑打包腳本
```bash
python build_ai_tool.py
```

成功後會在 `dist/` 看到 `AI多窗口集中討論工具.exe`

> 注意：repo 內含 `玻璃球.ico` / `玻璃球.icns`（以及可選的 `玻璃球.png`），用於視窗/工作列圖示。

---

## 設定檔位置
程式會在桌面建立設定檔（用來記住上次載入的主題路徑等）：

- `~/Desktop/AI討論工具_config.json`

---

## 常見問題
### Q：我可以只用 exe，不裝 Python 嗎？
可以。你可以去 GitHub Releases 下載 `.exe` 直接執行。

### Q：為什麼我提供 exe 也想放原始碼？
因為很多人會對陌生 exe 有疑慮；同時提供原始碼，別人更敢用，也更容易有人幫你修 bug/加功能。

---

## License
MIT（你可以自由使用、修改、再發布）
