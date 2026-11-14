# AutoResumeGoal

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Tiếng Việt](README.vi.md)

**Resume a native Codex Goal in the same chat after your usage quota recovers.**

![AutoResumeGoal banner showing a paused Goal, a clock, and a play symbol](assets/hero-wordmark.webp)

[In action](#in-action) · [Quick start](#quick-start) · [How it works](#how-it-works) · [Troubleshooting](#troubleshooting) · [Validation](#validation)

AutoResumeGoal is an opt-in Codex skill for long-running Goals on Linux. A local systemd user service watches the Goal you choose. If Codex stops it because of a usage limit, the service waits for ordinary quota to become available, then resumes the same Goal with its original objective and budget.

> **Linux preview.** The monitor runs on Linux with systemd. The screenshots and validation below describe observed behavior on the development setup.

## In action

These screenshots show the live Codex side panel during monitoring, quota recovery, and confirmed continuation.

| Monitoring | Waiting for quota | Continuation confirmed |
| :---: | :---: | :---: |
| <img src="assets/screenshots/monitoring.png" width="250" alt="AutoResumeGoal monitoring an active native Goal"> | <img src="assets/screenshots/waiting-for-quota.png" width="250" alt="A usage-limited Goal with a scheduled quota recheck"> | <img src="assets/screenshots/resumed.png" width="250" alt="The Goal is active and the side panel displays the last confirmed continuation time"> |
| The native Goal is active. | The panel shows when quota will be checked again. | A new turn in the original chat has been confirmed. |

## Quick start

### Install the skill

On the Linux host where the Goal runs, install the skill in `~/.agents/skills`.

```bash
# Bash or Zsh
git clone https://github.com/realpan/auto-resume-skill.git
cd auto-resume-skill
mkdir -p "$HOME/.agents/skills"
cp -R skills/auto-resume-goal "$HOME/.agents/skills/"
```

Check for an existing copy before installing. Verify that `$auto-resume-goal` appears in the skill picker. If it does not appear, restart Codex. [Codex skill discovery](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

### Run the quota monitor

Skill discovery and quota monitoring have separate requirements. The commands above install the skill files. The background monitor needs a Linux environment with systemd and access to the App Server that owns the Goal.

### Linux

Use Linux with a running systemd user manager, Python 3.9+, and a signed-in Codex installation with Goals enabled. The selected chat must belong to the managed App Server that the monitor connects to.

After [installing the skill](#install-the-skill), install the helper dependency from the checkout:

```bash
python3 -m pip install -r requirements.txt
```

If your Python installation requires a virtual environment, install the dependency there and use that environment's Python to run the helper.

In Codex, start a Goal and enable monitoring in one request:

```text
$auto-resume-goal Migrate the date parser. Finish when the new parser handles all fixtures and the test suite passes.
```

| What you want to do | What to enter in Codex |
| --- | --- |
| Monitor the Goal in this chat | `$auto-resume-goal monitor this goal` |
| See the native Goal and monitor states | `$auto-resume-goal status` |
| Stop the monitor | `$auto-resume-goal stop` |
| Pause or clear the Goal itself | Use the native Goal controls |

### macOS or Windows with a remote Linux host

1. Connect Codex to a Linux host with systemd, open a project on that host, and start the Goal in the remote chat.
2. Run the [Linux installation steps](#linux) on the remote host as the user running Codex.
3. In the remote chat, run `$auto-resume-goal monitor this goal`, then `$auto-resume-goal status` to confirm the monitor is running. The side panel requires the desktop client to reach the remote loopback service. The status command and host journal work independently of the panel.

## How it works

1. **Bind to one Goal.** The service records the chat ID, Goal creation time, and objective fingerprint. Only one monitor runs per chat.
2. **Wait for quota.** When the Goal is `usageLimited`, the service reads ordinary quota. Exhausted windows' reset times tell it when to check again.
3. **Resume in the original chat.** A fresh quota response must confirm that ordinary usage is available. The service checks that the original chat is idle and the selected Goal still matches before requesting native activation.
4. **Verify the restart.** The service looks for a new turn in the original chat. If it cannot confirm delivery, it exits so you can inspect the chat.

The service exits when the Goal completes, pauses, becomes blocked, hits its own token budget, or is removed or changed. Stopping the monitor leaves the native Goal at its current state. An activation already submitted may still take effect. Monitoring must be started again after a reboot.

In Codex desktop environments that provide the panel-opening tool, the skill opens a live AutoResumeGoal tab beside the chat on the right when you start monitoring. The panel uses the requested or chat language when supported, then the browser's language preferences, with English as the fallback. It supports Simplified Chinese, Traditional Chinese, English, Japanese, Korean, and Vietnamese. The panel shows the native Goal state, monitor state, and recent recovery details. Its stop button stops the monitor. The tab is served by a private loopback service and requires the Codex browser to reach that host. You can also use the native Goal progress bar, the skill's status command, and systemd logs.

## Troubleshooting

| What you see | What to check |
| --- | --- |
| The helper cannot connect | Run `codex app-server daemon version`. Confirm the daemon owns the selected chat and check its control socket path. |
| The Goal is still waiting after the reset time | Check the monitor log. The timestamp schedules a fresh check. Codex must explicitly confirm ordinary usage and the chat must be idle. |
| Continuation could not be confirmed | Check the original chat and native Goal before restarting the monitor. |

The default socket is `${CODEX_HOME:-$HOME/.codex}/app-server-control/app-server-control.sock`. The helper accepts `--socket` for a different local control socket. The App Server must report `ordinaryUsageAllowed` and support native automatic activation via `thread/goal/set`. The development host runs CLI 0.167.1 and managed App Server 0.169.0.

From the checkout, you can also control the monitor directly:

```bash
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py status --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py start --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py stop --thread CHAT_UUID
journalctl --user -u codex-auto-resume-goal-CHAT_UUID.service
```

## Validation

```bash
python3 -m unittest discover -s tests -v
```

The tests cover reset scheduling, quota checks, Goal identity, retrying reads, uncertain continuation, and monitor exit. On November 14, 2026, the local monitor journal recorded two quota-wait and confirmed-continuation cycles for the same chat. The waiting and resumed screenshots show states from that run. The results apply to that development setup.

To validate another setup, select a Goal you already intend to run across a quota window and use the helper from this checkout.

1. When the Goal reaches `usageLimited`, confirm the log records a next check and the chat stays stopped while ordinary usage is unavailable.
2. After natural quota recovery, confirm the same Goal starts a new turn in the original chat.
3. Complete the Goal or stop monitoring and verify the service exits. When testing `stop`, check that the native Goal retains its status.

## Related projects

- [Codex Auto Resume](https://github.com/progressrdx/codex-auto-resume) documents an opt-in monitor for selected Codex desktop tasks on macOS and Windows.
- [unsnooze](https://github.com/saaranshM/unsnooze) provides session recovery across multiple agent CLIs and terminal environments.
- [Goal Ledger](https://github.com/kingbootoshi/goal-ledger) records checkpoints and evidence alongside Goal mode.

[Skill entry point](skills/auto-resume-goal/SKILL.md) · [Codex Goals](https://learn.chatgpt.com/docs/long-running-work) · [App Server protocol](https://learn.chatgpt.com/docs/app-server)

## License

[MIT](LICENSE)
