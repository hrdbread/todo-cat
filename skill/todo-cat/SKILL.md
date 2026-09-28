---
name: todo-cat
description: Install, deploy, maintain and extend the todo-cat macOS app — a floating To-Do panel (pyobjc + WKWebView) with a walking cat pet, Outlook calendar import, Pomodoro, and Obsidian dashboard/retro automation. Use this skill whenever the user mentions todo-cat, the To-Do panel app, the cat pet, "~/.claude-todo", panel.py / panel.html / todo.py, Daily Log / Dashboard / retro files in the Obsidian Tracker folder, or asks to fix, change, add a feature to, redeploy, or reinstall their to-do app — even if they just say "the app" or "the cat". Also use it for any macOS pyobjc floating-window, TCC/calendar-permission, LaunchAgent, or Dock/app-bundle question that resembles this project.
---

# todo-cat

Open-source personal productivity app (GitHub `hyojinyang-ai/todo-cat`), usually cloned to `~/.claude-todo`. Reply in the user's language, concisely; offer options when a request is ambiguous.

## Product rules (decided by the user — do not "improve" them away)
1. **A Pomodoro means the cat sits with the singing bowl.** While a work session runs, both the Pomodoro page and the desktop pet show the singing-bowl cat (`assets/pomo_zen.png`, gently swaying with floating notes on the page). The walk cycle is reserved for to-do activity only; it never plays during a Pomodoro.
2. The pet sits idle on the panel and walks only for 60 s after a to-do interaction (add/complete/edit/click/typing). Pomodoro ticks and calendar refreshes are not activity.
3. Obsidian output (Daily Log, Dashboard, retro) is bilingual ko/en; the UI follows the language setting.

## What it is (30 seconds)
- **Floating panel** (`app/panel.py` + `app/panel.html`): always-on-top, all Spaces, non-activating. Pages: Todo / Pomodoro / Settings (ko·en).
- **Data core** (`app/todo.py`): tasks in `<vault>/Tracker/tasks.json` (vault from `config.json`); writes Obsidian **Daily Log / Monthly / Dashboard / Retros**.
- **Automation** (scheduler thread in `app/panel.py`): 08:00 Outlook events → Meeting todos; 18:00 bilingual AI retro + log/dashboard refresh; midnight rollover; 15-min calendar refresh.
- **Cat pet**: transparent window above the panel; sits when idle, walks 60 s after any interaction; expressions on add/done. Pomodoro page reuses the frames.
- **App identity**: `~/Applications/To-Do.app` (bundle id `com.todocat.app`), LaunchAgent `com.todocat.panel`, menu bar item, Dock icon.

Read `references/architecture.md` before editing code. Read `references/pitfalls.md` before touching images, permissions, or the app bundle — every item there cost real debugging time.

## Fresh install (new Mac)
```bash
git clone https://github.com/hyojinyang-ai/todo-cat ~/.claude-todo && ~/.claude-todo/install/setup.sh
```
`setup.sh` detects Obsidian vaults and writes `config.json`. Then: System Settings → Internet Accounts → add your calendar account (calendar on) → click **[일정 소스 다시 확인]** in the panel → allow calendar access. Optionally drag `To-Do.app` to the Dock.

## Change → deploy (every time)
1. Edit with a Python patch script: `s.replace(old, new, 1)` guarded by `assert old in s`. Never rely on silent no-ops.
2. `python3 -m py_compile ~/.claude-todo/app/panel.py ~/.claude-todo/app/todo.py`
3. Restart with `scripts/deploy.sh` (kills **all** instances, clears the pid file, kickstarts via launchd). `launchctl kickstart -k` alone is not enough.
4. Verify: `pgrep -f panel.py`, `tail /tmp/claude-panel.log`. After touching the bridge or Pomodoro code run `python3 tests/smoke_pomodoro_end.py` (real WebKit → pyobjc round-trip; exit 0 = alive). For image work, render a check sheet on a checkerboard and look at it with `read_file` (downscale with `sips -Z 700` first).
5. `git add -A && git commit -m "<what/why>" && git push`. Keep `CHANGELOG.md` current for user-visible changes.

## Common requests → where to look
| Request | Touch |
|---|---|
| UI text, layout, new page/control | `app/panel.html` (`L` strings ko **and** en, `render()`, `post({action})`) |
| New action from UI | `app/panel.html` → `app/panel.py` `Bridge.userContentController_didReceiveScriptMessage_` |
| Categories | `app/todo.py` `CATS` (name → (color, Korean label)); everything else follows |
| Daily Log / Dashboard / Monthly format | `app/todo.py` `write_daily_log`, `write_dashboard`, `write_monthly_page`, `write_heatmap_svg` |
| Retro prompt / language | `app/todo.py` `retro()` (single call, ko then `---` then en; preserves user notes) |
| Schedules (08:00, 18:00, rollover) | `app/panel.py` `scheduler()`; markers `state/imported.json`, `state/eod.json` |
| Pet behaviour / speed / frames | `app/panel.py` `walker()`, `Bridge.set_pet/apply_pet_image`; frames via `tools/mkframes.py`, `tools/mksit.py` → `assets/{walk,cat}/` |
| Calendar source | `app/panel.py` `do_fetch` (ICS → EventKit → Graph) |
| Sound / images | `assets/` (cat/, walk/, pomo_zen.png, singing-bowl.mp3); originals stay in `~/Downloads` |

## Images: the only safe workflow
Ask the user to place source images in `~/Downloads` and give you the path — never move pixels through chat (base64 broke alpha twice). Process on the Mac with `NSBitmapImageRep` + `setColor_atX_y_` (see `tools/mksit.py`, `tools/mkframes.py`), keep **RGBA PNG**, verify visually. Details in `references/pitfalls.md`.

## Cost awareness
Running the app costs 0 tokens. One retro ≈ $0.05–0.10 (`claude -p`). Development chats are the real cost — keep changes small and start a fresh conversation per change.
