---
name: auto-resume-goal
description: Start or monitor a native Codex Goal, show its live side panel, and automatically resume after ordinary Codex quota recovers. Use for "$auto-resume-goal", "AutoResumeGoal", or a request to continue a specific Goal after quota resets. Also handles panel, status, and stop requests.
---

# AutoResumeGoal

Use Codex's native Goal for the objective, status, and completion. The bundled helper waits for ordinary quota outside the model session. It requires Linux, a systemd user manager, Python with `websockets`, and a local Codex App Server control socket that owns the selected chat.

## Start or inspect

Use the current chat by default. Confirm the intended chat ID before acting on a different chat. Run the helper from the skill directory with that chat ID. If the host provides `CODEX_THREAD_ID`, the helper can use it for the current chat. Use `--socket` when the owning App Server uses a different control socket.

```bash
python3 scripts/auto_resume_goal.py status --thread CHAT_UUID
python3 scripts/auto_resume_goal.py start --thread CHAT_UUID
python3 scripts/auto_resume_goal.py stop --thread CHAT_UUID
```

- If the user supplies an objective and asks to start an AutoResumeGoal, inspect the current native Goal first. Create a native Goal with `create_goal` only for an explicitly requested new objective when no unfinished Goal exists. Preserve the acceptance criteria and constraints. Supply a token budget only when requested. If the tool is unavailable, the user can create the Goal with `/goal` and then start the monitor.
- If the user asks to monitor an existing Goal, attach to that Goal. `start` requires native status `active` or `usageLimited`. If the Goal is paused, blocked, or budget-limited, inspect the blocker and use the native user controls when it is ready to resume.
- Check `status` after starting and report whether the service is active. If a monitor already exists, report its state. Start a monitor only for the selected Goal and when the user asks for automatic recovery or invokes this skill to start it. Report unsupported App Server or systemd access as a blocker.
- Continue active work in the original chat. If resuming work after an interruption, recover the last verified checkpoint and first unmet criterion from the original chat or project evidence. Preserve the existing scope and verification requirements.

## Open the side panel on start

When starting a Goal or attaching a monitor from the Codex desktop app, open the live panel as part of the same turn, before beginning the Goal's substantive work. Also open it when explicitly asked to show the panel, even for a paused Goal. Resolve paths against this skill directory.

1. Run `python3 panel/serve.py --open --thread CHAT_UUID` for the same chat as the monitor. Use the same `--socket` override, if any. The command starts or reuses a local panel service and prints its private loopback URL.
2. Open a browser tab beside the chat with `codex_app__open_in_codex`, using `placement: "right"` and `target: {type: "browser", url: <panel URL>}`. Leave the chat visible and keep the tab in the normal split view. Omit `threadId` for the current chat. If the user asks for a different chat, use that chat ID. Do not print the private URL in the user-facing reply. If the tool is unavailable, or opening fails, report that and give the monitor status separately.
3. Verify the tool reports the tab opened or queued. If the Goal is paused or the monitor could not start, the panel can still display the native state. Opening the panel does not resume a Goal or start monitoring on its own.

Use the user's requested panel language, or infer it from their messages in the target chat. Append `#zh-CN`, `#zh-TW`, `#en`, `#ja`, `#ko`, or `#vi` to the printed URL for Simplified Chinese, Traditional Chinese, English, Japanese, Korean, or Vietnamese. If the chat language is unclear or unsupported, use the printed URL as-is so the page can follow the browser's preferred supported language, falling back to English.

## Recovery and finish

The service captures the original Goal creation time and objective fingerprint. When it finds `usageLimited`, it reads ordinary quota and uses the reported reset time for exhausted windows. It checks the Goal's lifecycle once per minute while waiting. After the reset, it requires a fresh quota read confirming ordinary usage and verifies that the original chat is idle before setting the same Goal active through the native App Server. It verifies continuation using a turn-start event or a new turn on readback. It leaves the objective and budget intact and uses included usage only.

- **Complete the Goal** after every acceptance criterion is verified. Call the native `update_goal` with `complete`. Report the evidence and final token usage if the Goal has a token budget. The monitor exits once it sees the completed state.
- **Pause the Goal** when explicitly requested, via the native Pause control or the authorized `update_goal` pause action. The monitor exits on pause, blocked, budget limit, clear, or replacement. To monitor again after a manual resume, run `start` again.
- **Stop auto-resume only** with `stop`. The command stops the background service. The Goal keeps its native status. The user can remove a Goal using the native Clear control.
- **Inspect the monitor** with `status` and `journalctl --user -u codex-auto-resume-goal-CHAT_UUID.service`. If delivery could not be confirmed, check the native Goal and chat before rearming. The transient service can outlive the chat turn, and needs to be started again after a machine reboot.
