# todo-cat 🐱🌱

A stress-free local To-Do for macOS: an always-on-top floating panel, Outlook events imported as tasks every morning, a Pomodoro timer, AI-drafted retros and an Obsidian dashboard — plus a cat that walks along the top of the panel while you work.

Built with Python (pyobjc) + WKWebView. No server, no account; everything lives on your Mac and in your notes folder.

> Built for and by one designer, pair-programming with Claude. It works on any Mac (see Install), but treat it as a well-loved personal tool rather than a polished product.

## Features
- **Floating panel** — add / edit / delete / complete tasks, category dropdown, drag to move, resize, opacity, Korean/English UI
- **Calendar import** — at 08:00 today's events become *Meeting* tasks with their duration (via macOS Calendar/EventKit, or an ICS link)
- **Pomodoro** — focus/break timer with the cat pacing beside you, singing-bowl sound at the end, remaining time in the menu bar
- **Obsidian automation** — Daily Log (WORK SESSIONS / FOCUS / UNFINISHED / NEXT STEPS), a living Dashboard with a 16-week heatmap, monthly review page, and an 18:00 bilingual (ko/en) AI retro via Claude Code CLI
- **Cat pet** — sits on the panel when idle, walks for 60 s after you interact, opens its eyes when you add a task and blushes when you complete one, settles into a loaf after 5 min without panel use (cats with loaf frames). Pick one or more cats in Settings → Cats
- **Native citizen** — Dock icon, menu bar item, standard app menu (⌘C/⌘V work), close/minimize traffic lights, launches at login

## Layout
```
todo-cat/
├── app/          panel.py (app: windows, menu bar, pet, calendar, scheduler)
│                 panel.html (single-file UI: Todo / Pomodoro / Settings, ko·en)
│                 todo.py (data core, Obsidian writers, AI retro, CLI)
├── assets/       pets/<cat>/ per cat: sitting + expressions, 8 walk frames, 8 loaf frames (+ mirrored)
│                 pomo_zen.png · singing-bowl.mp3
├── tools/        mkframes.py, mksit.py — regenerate cat frames from source artwork (per cat folder)
├── install/      setup.sh · Info.plist · AppIcon.icns · LaunchAgent template
├── skill/        todo-cat/ — Claude skill: deploy, maintain, extend
├── state/        runtime state (settings, caches, pid) — git-ignored
└── README · CHANGELOG · CLAUDE.md
```
Paths inside the app are resolved from the file location (`ROOT = parents[1]`), so the repo can live anywhere as long as `install/setup.sh` is used to (re)create the app bundle.

## Configuration
`install/setup.sh` writes `config.json` (git-ignored) at the repo root:
```json
{ "vault_path": "~/Documents/MyVault", "vault_name": "MyVault",
  "lang": "en", "import_hour": 8, "eod_hour": 18, "claude_bin": "" }
```
- `vault_path` — where `Tracker/` (tasks, logs, retros, dashboard) is written. Any folder works; with an Obsidian vault the links and embeds come alive.
- `vault_name` — Obsidian vault name for `obsidian://` deep links; leave empty to open files with the default Markdown app.
- `lang` — default UI language (`en` / `ko`), changeable in Settings.
- `import_hour` / `eod_hour` — when events become tasks and when the day auto-closes.
- `claude_bin` — path to the Claude Code CLI if it is not on `PATH` (AI retro only).

## Data (not in the repo)
- `<vault>/Tracker/tasks.json`, `Tracker/{Log,Monthly,Retros}/`, `Dashboard.md`, `assets/heatmap.svg`
- Settings, tokens and caches: `state/` (git-ignored)

## Install
Requirements: macOS 14+ and [python.org Python 3.13](https://www.python.org/downloads/macos/) (Homebrew Python lacks the GUI binary). After installing it, run `/Applications/Python 3.13/Install Certificates.command` once — otherwise HTTPS calendar (ICS) links fail with `CERTIFICATE_VERIFY_FAILED`. Optional: Obsidian, a calendar account in macOS Calendar, [Claude Code](https://docs.claude.com/en/docs/claude-code) CLI for the AI retro.
```bash
git clone https://github.com/hyojinyang-ai/todo-cat ~/.claude-todo && ~/.claude-todo/install/setup.sh
```
The installer detects your Obsidian vaults, writes `config.json`, builds `~/Applications/To-Do.app`, and registers it to launch at login. Then add your calendar account in System Settings → Internet Accounts (calendar on), click **Re-check calendar source** in the panel and allow calendar access.

### Regenerating the cat
Each cat lives in `assets/pets/<cat>/` and is listed in `PETS` in `app/panel.py` (name, window size, optional Pomodoro image). To swap in your own cat: `python3 tools/mksit.py <sitting-cat.png> <cat>` and `python3 tools/mkframes.py <walk-sprite-sheet.png> <cat>` (8 frames in a row, walking right). White backgrounds become transparent automatically. Both tools have the frame/eye positions of their source artwork hard-coded — measure yours and adjust them. Loaf frames (`loaf1..8`, sitting → loaf) are optional; without them the cat just keeps sitting.

## Maintaining with Claude
`skill/todo-cat/` is a Claude skill (Claude.ai Projects / Claude Code). Loaded in a fresh conversation, Claude already knows the install and deploy procedure, the architecture and the list of pitfalls.
- Claude Code: `CLAUDE.md` at the repo root loads automatically; symlink the skill to `~/.claude/skills/todo-cat`.
- Claude.ai: paste `skill/todo-cat/SKILL.md` into the project instructions or connect the repo as project knowledge.
- History: `CHANGELOG.md`.

## Development notes
- Smoke test for the Pomodoro completion path (real WebKit bridge): `python3 tests/smoke_pomodoro_end.py` — exit 0 means no crash; it plays the end-of-session sound once
- Redeploy: `skill/todo-cat/scripts/deploy.sh` (kills all instances, clears the pid file, restarts via launchd)
- Images must be **RGBA PNG** — palette PNGs lose alpha on macOS
- Never load SVG with NSImage (fills are ignored) — draw with AppKit or use PNG. Obsidian renders SVG fine, which is why the heatmap is SVG.

## License
MIT — see `LICENSE`. The cat artwork was generated for this project and is shared under the same terms.
