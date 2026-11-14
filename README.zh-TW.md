# AutoResumeGoal

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Tiếng Việt](README.vi.md)

**額度恢復後，在原對話中自動繼續執行原生 Codex Goal。**

![AutoResumeGoal](assets/hero-wordmark.webp)

> 私人審閱預覽。監控服務在使用 systemd 的 Linux 上執行。

## 實際執行

面板顯示原生 Goal 的狀態、下次額度檢查時間，以及原對話最近一次確認啟動新輪次的時間。

| 監控中 | 等待額度恢復 | 已確認繼續執行 |
| :---: | :---: | :---: |
| <img src="assets/screenshots/monitoring.png" width="250" alt="監控中"> | <img src="assets/screenshots/waiting-for-quota.png" width="250" alt="等待額度恢復"> | <img src="assets/screenshots/resumed.png" width="250" alt="已確認繼續執行"> |

## 快速開始

在執行 Goal 的 Linux 主機上執行下列指令。私人儲存庫需要具備存取權限的 GitHub 帳號。安裝前請檢查是否已有同名技能。若技能選擇器未顯示 `$auto-resume-goal`，請重新啟動 Codex。

```bash
git clone https://github.com/realpan/auto-resume-skill.git
cd auto-resume-skill
mkdir -p "$HOME/.agents/skills"
cp -R skills/auto-resume-goal "$HOME/.agents/skills/"
python3 -m pip install -r requirements.txt
```

需要 Python 3.9+、執行中的 systemd 使用者管理程式，以及已登入並啟用 Goal 的 Codex。監控必須連線至持有原對話的 App Server。若使用虛擬環境，請使用該環境的 Python 安裝相依套件並執行指令碼。

```text
$auto-resume-goal 移轉日期剖析器。新剖析器能處理所有測試資料且測試套件通過後結束。
```

| 操作 | 輸入 |
| --- | --- |
| 監控目前的 Goal | `$auto-resume-goal monitor this goal` |
| 查看狀態 | `$auto-resume-goal status` |
| 停止監控 | `$auto-resume-goal stop` |

### 從 macOS 或 Windows 使用遠端 Linux 主機

在桌面端連線至使用 systemd 的 Linux 主機，開啟遠端專案，在遠端對話中啟動 Goal。以執行 Codex 的使用者身分在 Linux 主機上安裝技能，再於原對話開啟監控並檢查狀態。側邊面板需要桌面用戶端能存取遠端主機的回送服務。也可以使用狀態指令與服務日誌。

## 運作方式

服務綁定對話 ID、Goal 建立時間和目標指紋，每個對話只執行一個監控。進入 `usageLimited` 後，依已耗盡額度的重設時間安排複查。一般額度明確可用、原對話閒置且 Goal 仍相符時，恢復原 Goal，保留原目標和預算。確認原對話啟動新輪次後繼續監控。若無法確認結果，服務會退出，請檢查原對話。

Goal 完成、暫停、受阻、用盡自身預算、被移除或修改時，監控會退出。手動停止監控會保留 Goal 的原生狀態，已提交的恢復請求仍可能生效。主機重新開機後需再次啟用監控。

支援開啟面板的 Codex 桌面端會在對話右側顯示即時狀態。面板依指定語言、對話語言及瀏覽器偏好選取支援的語言，預設使用英文。支援簡體中文、繁體中文、英文、日文、韓文與越南文。

## 疑難排解

連線失敗時，確認執行中的 daemon 持有該對話，並檢查通訊端路徑。超過重設時間仍在等待時，檢查服務日誌、即時一般額度及對話是否閒置。續跑結果不明時，先檢查原對話再啟用監控。

預設通訊端為下方路徑，可用 `--socket` 指定其他本機通訊端。App Server 需回傳 `ordinaryUsageAllowed` 並支援透過 `thread/goal/set` 自動恢復。開發環境使用 CLI 0.167.1 和 App Server 0.169.0。

```bash
printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/app-server-control/app-server-control.sock"
codex app-server daemon version
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py status --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py start --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py stop --thread CHAT_UUID
journalctl --user -u codex-auto-resume-goal-CHAT_UUID.service
```

## 驗證

```bash
python3 -m unittest discover -s tests -v
```

測試涵蓋額度與重設時間、Goal 身分、讀取重試、續跑結果不明及監控退出。2026 年 11 月 14 日，開發環境在同一對話中記錄了兩次等待額度後確認繼續執行的過程。截圖來自這次執行。驗證其他環境時，請確認額度不可用時持續等待、自然恢復後原對話啟動新輪次，以及完成或手動停止後監控退出。手動停止時請檢查 Goal 狀態是否維持。

## 相關專案

[Codex Auto Resume](https://github.com/progressrdx/codex-auto-resume) · [unsnooze](https://github.com/saaranshM/unsnooze) · [Goal Ledger](https://github.com/kingbootoshi/goal-ledger)

[SKILL.md](skills/auto-resume-goal/SKILL.md) · [Codex Goals](https://learn.chatgpt.com/docs/long-running-work) · [App Server](https://learn.chatgpt.com/docs/app-server)
