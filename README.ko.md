# AutoResumeGoal

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Tiếng Việt](README.vi.md)

**사용량 한도가 회복되면 같은 채팅에서 Codex Goal을 자동으로 재개합니다.**

![AutoResumeGoal](assets/hero-wordmark.webp)

> 비공개 검토 버전입니다. 모니터는 systemd를 사용하는 Linux에서 실행됩니다.

## 실행 화면

측면 패널에서 Goal 상태, 다음 한도 확인 시간, 원래 채팅에서 새 턴이 시작된 것을 마지막으로 확인한 시간을 볼 수 있습니다.

| 모니터링 중 | 사용량 한도 회복 대기 중 | 재개 확인 |
| :---: | :---: | :---: |
| <img src="assets/screenshots/monitoring.png" width="250" alt="모니터링 중"> | <img src="assets/screenshots/waiting-for-quota.png" width="250" alt="사용량 한도 회복 대기 중"> | <img src="assets/screenshots/resumed.png" width="250" alt="재개 확인"> |

## 빠른 시작

Goal이 실행되는 Linux 호스트에서 다음 명령을 실행합니다. 비공개 저장소를 복제하려면 접근 권한이 있는 GitHub 계정이 필요합니다. 설치 전에 기존 사본을 확인하세요. 스킬 선택기에 `$auto-resume-goal`이 나타나지 않으면 Codex를 다시 시작합니다.

```bash
git clone https://github.com/realpan/auto-resume-skill.git
cd auto-resume-skill
mkdir -p "$HOME/.agents/skills"
cp -R skills/auto-resume-goal "$HOME/.agents/skills/"
python3 -m pip install -r requirements.txt
```

Python 3.9 이상, 실행 중인 systemd 사용자 관리자, 로그인 및 Goal 활성화가 완료된 Codex가 필요합니다. 원래 채팅을 관리하는 App Server에 연결하세요. 가상 환경을 사용하는 경우 해당 환경의 Python으로 의존성을 설치하고 도우미를 실행합니다.

```text
$auto-resume-goal 날짜 파서를 마이그레이션하세요. 새 파서가 모든 테스트 데이터를 처리하고 테스트가 모두 통과하면 완료하세요.
```

| 작업 | 입력 |
| --- | --- |
| 현재 Goal 모니터링 | `$auto-resume-goal monitor this goal` |
| 상태 확인 | `$auto-resume-goal status` |
| 모니터링 중지 | `$auto-resume-goal stop` |

### macOS 또는 Windows에서 원격 Linux 호스트 사용

데스크톱 Codex에서 systemd가 실행 중인 Linux 호스트에 연결하고 원격 프로젝트를 엽니다. 원격 채팅에서 Goal을 시작한 다음 Codex를 실행하는 사용자로 Linux에 스킬을 설치합니다. 같은 채팅에서 모니터링을 시작하고 상태를 확인하세요. 측면 패널을 보려면 데스크톱 클라이언트에서 원격 루프백 서비스에 연결할 수 있어야 합니다. 상태 명령과 서비스 로그도 사용할 수 있습니다.

## 작동 방식

모니터는 채팅 ID, Goal 생성 시각, 목표 지문에 연결되며 채팅당 하나만 실행됩니다. `usageLimited`가 되면 소진된 한도의 초기화 시간을 기준으로 다음 확인을 예약합니다. 일반 사용량을 쓸 수 있고 채팅이 유휴 상태이며 Goal이 일치하면 원래 목표와 예산을 보존한 채 재개합니다. 원래 채팅에서 새 턴을 확인하지 못하면 모니터링을 종료합니다.

Goal이 완료, 일시 정지, 차단, 예산 소진, 삭제 또는 변경되면 모니터가 종료됩니다. 모니터링을 수동으로 중지해도 Goal 상태는 유지됩니다. 이미 전송된 재개 요청은 적용될 수 있습니다. 호스트 재부팅 후에는 모니터링을 다시 시작해야 합니다.

패널 열기를 지원하는 Codex 데스크톱 환경에서는 채팅 오른쪽에 실시간 패널이 표시됩니다. 지정 언어, 채팅 언어, 브라우저 설정 순으로 지원 언어를 선택하며 기본값은 영어입니다. 중국어 간체와 번체, 영어, 일본어, 한국어, 베트남어를 지원합니다.

## 문제 해결

연결에 실패하면 실행 중인 데몬이 해당 채팅을 관리하는지 확인하고 소켓 경로를 점검하세요. 초기화 시간이 지나도 대기 중이면 로그와 현재 일반 사용 한도, 채팅의 유휴 상태를 확인하세요. 재개 여부가 불명확하면 모니터를 다시 시작하기 전에 원래 채팅을 확인하세요.

기본 소켓은 아래 경로이며 `--socket`으로 다른 로컬 소켓을 지정할 수 있습니다. App Server는 `ordinaryUsageAllowed`를 반환하고 `thread/goal/set`을 통한 자동 재개를 지원해야 합니다. 개발 환경은 CLI 0.167.1 및 App Server 0.169.0을 사용합니다.

```bash
printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/app-server-control/app-server-control.sock"
codex app-server daemon version
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py status --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py start --thread CHAT_UUID
python3 skills/auto-resume-goal/scripts/auto_resume_goal.py stop --thread CHAT_UUID
journalctl --user -u codex-auto-resume-goal-CHAT_UUID.service
```

## 검증

```bash
python3 -m unittest discover -s tests -v
```

테스트는 사용량 한도와 초기화 시간, Goal 식별, 읽기 재시도, 재개 여부가 불명확할 때의 처리, 모니터 종료를 다룹니다. 2026년 11월 14일 개발 환경의 같은 채팅에서 한도 회복을 기다린 뒤 재개를 확인한 사례가 두 번 기록됐습니다. 스크린샷은 해당 실행을 보여 줍니다. 다른 환경에서는 한도 회복 전 대기, 자연 회복 후 원래 채팅의 새 턴, 완료 또는 수동 중지 후 모니터 종료를 확인하세요. 수동 중지 시 Goal 상태가 유지되는지도 확인합니다.

## 관련 프로젝트

[Codex Auto Resume](https://github.com/progressrdx/codex-auto-resume) · [unsnooze](https://github.com/saaranshM/unsnooze) · [Goal Ledger](https://github.com/kingbootoshi/goal-ledger)

[SKILL.md](skills/auto-resume-goal/SKILL.md) · [Codex Goals](https://learn.chatgpt.com/docs/long-running-work) · [App Server](https://learn.chatgpt.com/docs/app-server)
