# todo-cat — project instructions

## What this is
A stress-free To-Do app for macOS: always-on-top floating panel + Outlook events imported at 08:00 as Meeting tasks
+ Pomodoro + Obsidian Daily Log / Monthly / Dashboard / AI retro + a cat pet walking along the panel. Python (pyobjc) + WKWebView.
Reply in the user's language, concisely. When a request has several readings, offer options.

## Product rules (decided by the user — do not "improve" them away)
1. **A Pomodoro means the cat sits with the singing bowl.** While a work session runs, both the Pomodoro page and the desktop pet show the singing-bowl cat (`assets/pomo_zen.png`, gently swaying with floating notes on the page). The walk cycle is reserved for to-do activity only; it never plays during a Pomodoro.
2. The pet sits idle on the panel and walks only for 60 s after a to-do interaction (add/complete/edit/click/typing). Pomodoro ticks and calendar refreshes are not activity.
3. Obsidian output (Daily Log, Dashboard, retro) is bilingual ko/en; the UI follows the language setting.

## Locations
- Code: `~/.claude-todo/` (clone of GitHub `hyojinyang-ai/todo-cat`)
- App bundle: `~/Applications/To-Do.app` (`To-Do` = zsh wrapper → `To-Do-bin` = copy of the Python GUI binary; bundle id `com.todocat.app`)
- Login item: `~/Library/LaunchAgents/com.todocat.panel.plist`
- Config: `config.json` at repo root (vault_path, vault_name, lang, import_hour, eod_hour, claude_bin) — created by `install/setup.sh`, git-ignored
- Data (not in repo): `<vault>/Tracker/tasks.json`, `Tracker/{Log,Monthly,Retros}/`, `Dashboard.md`; settings/caches `~/.claude-todo/state/`
- Source images live in `~/Downloads`; ask for the path and process on the Mac. Never move pixels through chat (base64 corrupted files twice, wastes tokens).

## Files (repo layout: `app/` code · `assets/{cat,walk}` images · `tools/` generators · `install/` bundle + setup · `state/` runtime, ignored)
- `app/panel.py` app: `Bridge` (JS↔Python actions), panel + pet windows, status item, main menu, `walker()` (pet), `scheduler()` (midnight rollover · 08:00 import · 18:00 end-of-day · 15-min calendar refresh)
- `app/panel.html` single-file UI (asset URLs are `../assets/...`): three pages (todo / pomodoro / settings), `L` object for ko·en i18n, `post({action})` → Python, `render(state)` ← Python
- `app/todo.py` data core + `write_daily_log` / `write_monthly_page` / `write_dashboard` / `write_heatmap_svg` + `retro()` (`claude -p`, bilingual) + `run_eod()` + `dashboard()`. Categories in `CATS` (name → (color, Korean label)); vault/schedule from `CFG`
- `tools/mkframes.py` sprite sheet → 16 walk frames · `tools/mksit.py` sitting cat + expressions · `install/setup.sh` reinstall

## Change → deploy (always this order)
```
python3 -m py_compile ~/.claude-todo/app/panel.py ~/.claude-todo/app/todo.py
pkill -f panel.py; sleep 1; rm -f ~/.claude-todo/state/panel.pid
launchctl kickstart gui/$(id -u)/com.todocat.panel
```
(or `skill/todo-cat/scripts/deploy.sh`)
- `kickstart -k` alone is not enough: the single-instance guard yields to a surviving old process and the new code never appears. Always pkill + remove the pid file.
- After `codesign`, the calendar permission prompt may appear again — tell the user.
- Finish with `git add -A && git commit -m "..." && git push` (English message, what/why in one line) and update `CHANGELOG.md` for user-visible changes.

## Patch rules
- Edit files from a Python script with `s.replace(old, new, 1)` and `assert old in s` on every anchor (silent no-ops have bitten several times).
- Adding `L` strings: add to **both** ko and en, anchored on the real last key of each object.
- pyobjc: NSObject subclass methods carry one trailing `_` per argument (`runjs_`); helpers go outside the class or use `objc.python_method`.

## Known pitfalls
- **RGBA PNG only.** Palette (P) PNGs lose their alpha on macOS. To shrink, quantize RGB and re-attach the original alpha.
- **No SVG via NSImage** — fills are ignored, you get a silhouette. Draw with NSBezierPath or use PNG.
- macOS 14+ calendar permission needs a usage description in Info.plist **and** the request must come from the launchd-run bundle (TCC "responsible process"). Requests from a terminal or Claude-spawned process are silently denied.
- `exec` into a binary outside the bundle strips the app identity → keep the binary copy inside the bundle. The Dock launches the executable with no arguments → the executable must be a wrapper.
- Verify images by pixels: composite on a checkerboard, `sips -Z 700`, then `read_file`.
- Dock/menu bar need `NSApplicationActivationPolicyRegular`; the panel is a NonactivatingPanel, so clicking it does not switch the menu bar (activate via the Dock icon).
- Pet window at `NSFloatingWindowLevel + 1` so its feet are not covered; position relative to the panel and clamp to that screen's visible frame.

## Cost awareness
Running the app: 0 tokens. One AI retro ≈ $0.05–0.10. Development chats are the whole cost → small changes in short fresh conversations.
