# AutoResumeGoal

[English](../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Tiếng Việt](README.vi.md)

**利用枠が回復すると、同じチャットで Codex の Goal を自動で再開します。**

![AutoResumeGoal](../assets/hero-wordmark.webp)

> Linux 向けプレビュー版です。監視サービスは systemd を使用する Linux で動作します。

## 動作例

サイドパネルに Goal の状態、次回の利用枠確認時刻、元のチャットで新しいターンの開始を確認した時刻が表示されます。

| 監視中 | 利用枠の回復待ち | 再開を確認 |
| :---: | :---: | :---: |
| <img src="../assets/screenshots/monitoring.png" width="250" alt="監視中"> | <img src="../assets/screenshots/waiting-for-quota.png" width="250" alt="利用枠の回復待ち"> | <img src="../assets/screenshots/resumed.png" width="250" alt="再開を確認"> |

## クイックスタート

Goal を実行する Linux ホストで以下のコマンドを実行します。非公開リポジトリのクローンにはアクセス権のある GitHub アカウントが必要です。インストール前に既存のコピーを確認してください。スキル一覧に `$auto-resume-goal` が表示されない場合は、Codex を再起動します。

```bash
git clone https://github.com/realpan/auto-resume-skill.git
cd auto-resume-skill
mkdir -p "$HOME/.agents/skills"
cp -R skills/auto-resume-goal "$HOME/.agents/skills/"
python3 -m pip install -r requirements.txt
```

Python 3.9 以上、稼働中の systemd ユーザーマネージャー、ログイン済みで Goal が有効な Codex が必要です。元のチャットを管理している App Server に接続してください。仮想環境を使う場合は、その環境の Python で依存パッケージのインストールとヘルパーの実行を行います。

```text
$auto-resume-goal 日付パーサーを移行してください。新しいパーサーがすべてのテストデータを処理し、テストがすべて通れば完了です。
```

| 操作 | 入力 |
| --- | --- |
| 現在の Goal を監視 | `$auto-resume-goal monitor this goal` |
| 状態を確認 | `$auto-resume-goal status` |
| 監視を停止 | `$auto-resume-goal stop` |

### macOS または Windows からリモート Linux ホストを使う

デスクトップ版 Codex で systemd が動作する Linux ホストに接続し、リモートプロジェクトを開きます。リモートチャットで Goal を開始し、Codex を実行するユーザーで Linux 側にスキルをインストールします。同じチャットで監視を開始し、状態を確認してください。サイドパネルの表示には、デスクトップからリモートのループバックサービスへの接続が必要です。状態確認コマンドとサービスログも利用できます。

## 仕組み

監視はチャット ID、Goal の作成時刻、目標のフィンガープリントに紐づき、チャットごとに一つだけ動作します。`usageLimited` では利用枠のリセット時刻を使って次回確認を予定します。通常の利用枠が使え、チャットがアイドル状態で Goal が一致する場合、元の目標と予算を保持したまま再開します。元のチャットで新しいターンを確認できない場合は監視を終了します。

Goal の完了、一時停止、ブロック、予算の使い切り、削除、変更で監視を終了します。手動で監視を停止しても Goal の状態は維持されます。送信済みの再開要求は反映されることがあります。ホストを再起動した後は監視を再度開始してください。

対応する Codex デスクトップ環境では状態パネルがチャットの右側に表示されます。指定言語、チャットの言語、ブラウザーの設定の順に選び、該当しない場合は英語になります。対応言語は簡体字中国語、繁体字中国語、英語、日本語、韓国語、ベトナム語です。

## トラブルシューティング

接続できない場合は、稼働中のデーモンが元のチャットを管理しているか、ソケットのパスが正しいかを確認します。リセット後も待機中ならログ、現在の利用枠、チャットの状態を確認します。再開を確認できない場合は、監視を再起動する前に元のチャットを確認してください。

既定のソケットは以下のとおりです。`--socket` で別のローカルソケットを指定できます。App Server は `ordinaryUsageAllowed` を返し、`thread/goal/set` による自動再開をサポートする必要があります。開発環境は CLI 0.167.1 と App Server 0.169.0 を使用しています。

```bash
printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/app-server-control/app-server-control.sock"
codex app-server daemon version
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py status --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py start --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py stop --thread CHAT_UUID
journalctl --user -u codex-auto-resume-goal-CHAT_UUID.service
```

## 検証

```bash
python3 -m unittest discover -s tests -v
```

テストは利用枠、リセット時刻、Goal の識別、読み取りの再試行、再開未確認時の処理、監視終了を対象にしています。2026 年 11 月 14 日に開発環境で、同じチャットで利用枠の回復を待って再開を確認する流れを 2 回記録しました。画像はその実行例です。別の環境では、利用枠が不足している間は待機し、自然回復後に元のチャットで新しいターンが始まり、完了または手動停止で監視が終了することを確認してください。手動停止では Goal の状態も確認します。

## 関連プロジェクト

[Codex Auto Resume](https://github.com/progressrdx/codex-auto-resume) · [unsnooze](https://github.com/saaranshM/unsnooze) · [Goal Ledger](https://github.com/kingbootoshi/goal-ledger)

[SKILL.md](../skills/auto-resume-goal/SKILL.md) · [Codex Goals](https://learn.chatgpt.com/docs/long-running-work) · [App Server](https://learn.chatgpt.com/docs/app-server)

## ライセンス

[MIT](../LICENSE)
