# Changelog

Everything here was built pair-programming with Claude. Dates are actual working days.

## 2026-10-05
### Changed
- **Research to-dos have context**: ▸ opens the product and severity (e.g. *Decido · Blocker*), the study, the suggested fix, where it came from (a project or one of your items) and a link to the study.
- **Ticking a UX item hands it over for review**: it moves to *In review* in the inbox (not Done) and leaves the feed, which now only carries items *In design* or *Ready* (plus research follow-ups for those). Jira and monday are not touched.

### Added
- **Links in the accordion**: a UX to-do's accordion opens with its links — the UX plans row it came from, Figma/Miro/doc links on the row, links added in the inbox and linked studies — each a chip that opens in the browser. To-dos with links but no open checks get the accordion too.
- **DoD checks as an accordion**: a UX to-do has a ▸ and a count (e.g. `1/25`). Open it to see the checks still to do, under their DoD headings (epics: their readiness checks). Ticking a check marks it met in the inbox ("Marked met by …"); unticking undoes it. Open/closed is remembered; checks don't count as separate to-dos.
- **UX Inbox feed**: Settings → *UX Inbox* takes a subscribe link (or `.ics` file path) from ux-inbox. Your open design work comes in as **Design** to-dos and open blocker/major research findings as **Research** to-dos, each with a small **UX** badge that opens it in the inbox. Synced on the same refresh as the calendar (every 15 min, ↻, opening the panel) and with *Sync now*; kept in step by UID, so no duplicates. The live link (`http://localhost:5310/feeds/<you>.ics`) is read first; when the inbox server is off, the published `docs/feeds/<you>.ics` in the *UX Inbox folder* is read instead. Synced to-dos land below your own.
- **Ticking off writes back**: ticking a UX to-do moves the item to In review in the inbox (reason "Ticked off in todo-cat") or the finding resolved, as one event file in the inbox's shared log; unticking undoes it. The feed never reopens a task you ticked, and a failed read never removes anything.

## 2026-10-01
### Changed
- **Panel is a normal window by default** — it goes behind whatever app you click and comes forward when you click it or its Dock icon. New Settings → Appearance → *Always on top* toggle restores the floating behaviour.
- **Cats follow the panel**: they are child windows now, so closing (✕) or minimizing the panel hides them and reopening brings them back; they still render above the panel.

## 2026-09-29
### Added
- **Drag-and-drop reordering** of the to-do list: grab a row (a ⋮⋮ handle appears on hover) and drop it where you want; the order is saved (`order` field) and survives restarts. New items still land at the top. Completed items are not draggable.

## 2026-09-28
### Added
- Settings → **Pomodoro → End-of-session sound**: pick any macOS system sound (or None) from a dropdown; the choice previews immediately and there is a ▶ button to replay it. Stored per user in settings; `config.json` `sound` remains the default for new installs.
- `sound` in `config.json`: end-of-session sound is now a short macOS system sound (Purr by default, half volume) or any file you point to. The bundled singing-bowl.mp3 is gone.
- **Todo and Pomodoro pages restyled to match Settings**: schedule / to-do / done lists as cards under small group headers, add-item box as a card, centered footer; Pomodoro page gets the same header, a timer card and a *Session* group with title/description rows (focus, break, today's count).
- **Settings page redesigned** with hierarchy: three groups (Appearance · Calendar · Cat) as cards, each row with a title and a one-line description, controls aligned right; segmented control for language, switch-style toggles, swatch row for accent, slider with value for opacity.
- **Accent colour** in Settings: six swatches plus a custom colour picker; recolours the UI live and the Obsidian heatmap uses the same colour on its next refresh.
### Changed
- Removed the "Done" button from Settings — every setting applies on change; use ← or Esc to go back.
- **No duplicate schedule entries.** A calendar event that was already imported as a to-do no longer reappears in "Today's schedule" when its calendar ID changes on re-sync: events are matched by title (and time) against today's to-dos and against the titles imported at 08:00, not only by ID. The import itself also skips same-title events.
- **Rule 1 narrowed to the Pomodoro page.** Desktop cats no longer sit down when a Pomodoro starts; they keep sitting/walking/loafing independently of the timer. The singing-bowl cat remains the Pomodoro-page visual.
### Added
- **Choose your cats**: Settings → Cats shows one or more cats on the panel. Cats are auto-discovered: every `assets/pets/<cat>/` folder with a `cat.png` is a cat (name from the folder, window size from the widest frame, optional `pomo.png`). Only Sprout ships with the repo; other folders are git-ignored so cat packs can be dropped in. Each cat has its own window, position, direction and loaf state.
- **Loaf**: after `loaf_after` seconds (config, default 300) without clicking or typing in the panel, cats that have loaf frames settle into a loaf (8 frames, ~2 s) and get up again (reverse, ~1 s) on the next panel interaction. Adding/completing a task interrupts the loaf with the alert/happy face. No loaf during a Pomodoro.

### Changed
- **Rule: a Pomodoro shows the singing-bowl cat, never the walking cat.** Pomodoro page now animates the sitting cat (gentle sway + floating notes) instead of the walk cycle; the desktop pet also sits with the bowl for the whole work session. Recorded as product rule #1 in CLAUDE.md / SKILL.md.
- Cat artwork moved to `assets/pets/<cat>/` (same file names per cat: `cat`, `pet_alert`, `pet_happy`, `walk1..8`, optional `loaf1..8`, each with `_flip`). The Pomodoro rule applies to every cat: the default cat shows the singing-bowl cat, cats without a Pomodoro image just sit. `tools/mksit.py` / `tools/mkframes.py` take the cat folder as a second argument.

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
