# Changelog

Everything here was built pair-programming with Claude. Dates are actual working days.

## 2026-09-28
### Changed
- **Rule: a Pomodoro shows the singing-bowl cat, never the walking cat.** Pomodoro page now animates the sitting cat (gentle sway + floating notes) instead of the walk cycle; the desktop pet also sits with the bowl for the whole work session. Recorded as product rule #1 in CLAUDE.md / SKILL.md.

## 2026-09-25
### Fixed
- **App crashed when a Pomodoro session finished** (`NameError: notify` inside the WebKit message handler → pyobjc abort). Fixed the missing reference and wrapped the bridge callback so no Python exception can ever take the process down again; errors are now logged to `/tmp/claude-panel.log` instead.

## 2026-09-24
### Changed
- **Made shareable**: `config.json` (vault path/name, language, schedule hours, claude path) replaces hardcoded personal paths; neutral identifiers (`com.todocat.app`, `com.todocat.panel`); tools take the source image as an argument; timezone auto-detected; interactive `install/setup.sh` that detects Obsidian vaults; MIT license; personal details removed from docs; git history squashed and repository made public.
- **Repository restructured**: `app/` (code), `assets/{cat,walk}` (images + sound), `tools/` (frame generators), `install/` (setup + bundle template), `state/` (runtime json, git-ignored). All paths resolve from the file location; the app bundle wrapper now points to `app/panel.py`; setup is `install/setup.sh`.
- Repository cleanup: removed the unrelated Claude-usage SwiftBar widget and the retired SwiftBar menu plugin (`extras/`), stray `.bkit` state files, dead SwiftBar-menu code and unused constants/imports in `todo.py`, and the obsolete HTML dashboard. `todo.py` now prints usage when run without arguments and gained an `eod` command.
- Repository content translated to English: docs (README, CHANGELOG, CLAUDE.md), code comments and docstrings, shell scripts, Korean-only runtime strings, SwiftBar usage widget. The `ko` half of the UI language switch, Korean category labels and the deliberately bilingual Obsidian headings are unchanged.

## 2026-09-17
### Added
- `CHANGELOG.md` and the `skill/todo-cat/` Claude skill (SKILL.md, architecture & pitfalls references, `deploy.sh`); skill symlinked into `~/.claude/skills`

## 2026-09-16
### Added
- **18:00 end-of-day automation**: bilingual (ko→en) AI retro + Daily Log / Dashboard / Monthly refresh. Runs after wake if the Mac was asleep. Regeneration preserves the user's `✍️ 내 노트 / My notes` section
- **Obsidian Dashboard** (`Tracker/Dashboard.md`): 30-day ACTIVITY (actions, hours worked, active days, pomodoros), CATEGORIES bars, **16-week heatmap calendar (SVG)**, TIMELINE links
- **New Daily Log format**: WORK SESSIONS (bold title + `(~45m)` duration) / FOCUS / UNFINISHED / NEXT STEPS / RETRO embed; labels and summaries in ko and en
- Meeting durations stored on import (`minutes`) and counted in *Hours worked*
- Pet behaviour: **sits on the panel when idle**, walks for 60 s after any interaction (click, typing, add, complete, …)
### Fixed
- Noisy sitting-cat image → regenerated from the original artwork with direct pixel writes (`mksit.py`)

## 2026-09-15
### Added
- **Desktop cat pet**: transparent window, walks along the panel, faces its direction, expressions (add → eyes open, complete → blush)
- **8-frame walk cycle** from a user-provided sprite sheet → 16 frames via `mkframes.py`
- Pet window level `Floating+1` (feet never hidden), screen-edge clamping, faster stride
- Cat on the Pomodoro page: walking while focusing, **singing-bowl meditation cat** while idle/on break, **singing-bowl sound** when a session ends
- App renamed **To-Do**, pinned to the Dock, custom icon, menu bar ✓ item (task count / 🍅 timer), full main menu (To-Do / File / Edit / View / Window — ⌘C/⌘V work)
- Native close & minimize buttons, relaunch from the Dock, single-instance guard
- Category dropdown left of the input, click the dot/label to change category, new `Personal` category
- Pomodoro page: ⏱ timer, focus/break dropdowns above the timer, ▶⏸■ icon buttons, today's count and minutes, remaining time in the menu bar
- Settings page: opacity slider, ko/en switch, 08:00 import toggle, pet & walk toggles, ← / Esc navigation
- Resizable window, Inter + Pretendard fonts installed and applied
- Git repository `todo-cat` (private), `setup.sh`, `CLAUDE.md`
### Fixed
- Settings page would not close (`hidden` lost to `display:flex`)
- Close button disabled (missing `Closable` mask); Dock relaunch failed (Python binary launched without arguments → wrapper structure)
- Calendar permission: plain python has no usage description → `.app` bundle; `exec` stripped the bundle identity → binary copied inside the bundle; TCC responsible-process rule → request only from launchd
- Image alpha lost (palette PNG) and SVG fills ignored by macOS → RGBA PNG + AppKit drawing
- Stale process hijacking restarts (established the pkill + pid-file procedure)

## 2026-09-14
### Added
- Claude usage menu bar widget (SwiftBar; Enterprise spend limit + Claude Code credit; certifi SSL fix)
- Task core (`todo.py`), SwiftBar menu, HTML dashboard, `claude -p` retro saved to Obsidian
- **Floating panel app** (pyobjc + WKWebView): add / edit / delete / complete, always on top, all Spaces, login item (LaunchAgent)
- Outlook integration: Graph API blocked by org policy (53003) → **Exchange in macOS Calendar + EventKit**; ICS URL source also supported
- 08:00 daily import of events as Meeting tasks; midnight rollover (clear completed items from view, keep history)
