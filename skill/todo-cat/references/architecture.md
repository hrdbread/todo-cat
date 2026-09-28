# Architecture

## Processes & files
```
~/Applications/To-Do.app/Contents/MacOS/To-Do        zsh wrapper → exec To-Do-bin ~/.claude-todo/                                       repo root; code resolves ROOT = Path(__file__).parents[1]
   app/panel.py app/panel.html app/todo.py
   assets/pets/<cat>/{cat,pet_alert,pet_happy,walk1..8,loaf1..8}[_flip].png  assets/pomo_zen.png  assets/singing-bowl.mp3
   tools/mkframes.py tools/mksit.py                  install/setup.sh install/Info.plist install/AppIcon.icns install/*.plist
   state/  settings.json cal_cache.json imported.json eod.json events_state.json pomo_log.json panel.pid msal_cache.bin  (ignored)
<vault>/Tracker/                                      vault path/name from config.json (no Obsidian → plain folder, files open with default app)
   tasks.json  Log/YYYY-MM-DD.md  Monthly/YYYY-MM.md  Dashboard.md  Retros/YYYY-MM-DD-Daily.md  assets/heatmap.svg
```

## app/panel.py
- `get_settings/set_setting` → `settings.json` (opacity, lang, import_events, pomo_work/break, pet_enabled, pet_walk).
- Calendar sources: `fetch_events_ics(url)` (ics_url.txt), `fetch_events_eventkit(interactive)` (EventKit; permission only prompts from the launchd-run bundle), `fetch_events(token)` (Graph; blocked by org CA 53003). `do_fetch()` tries in that order → `cal_cache.json`.
- `import_events_as_todos()` → Meeting todos titled `HH:MM Title` with `minutes`; hides the event from the schedule list (`events_state.json`).
- `Bridge(NSObject)`: JS↔Python. Actions: state, add, done, delete, title, cat, ev, connect, refresh_cal, dashboard, retro, setting, pomo_title, pomo_done, activity, quit. Every non-tick action refreshes `pet_active_until`.
  Menu selectors: togglePanel:, openDash:, dailyRetro:, quitApp:, newItem:, showSettings:, showPomo: (pyobjc: one trailing `_` per argument).
- `Panel(NSPanel)` canBecomeKeyWindow True. Style: Titled|FullSizeContentView|Nonactivating|Resizable|Miniaturizable|Closable; zoom button hidden; WKWebView inset 26 px from top (native drag strip).
- Pet: borderless `Panel`, clear bg, `NSFloatingWindowLevel + 1`, `NSImageView` scaling proportional. `walker()` thread @0.07 s: idle → sit at panel top; active → step 3.6 px, 8 frames, flip at edges, clamp to screen. `set_pet(state, revert_sec)` pauses walking while showing alert/happy.
- `scheduler()` thread @60 s: date change → `write_daily_log(yesterday)` + push; hour≥8 & not imported today → fetch+import; hour≥18 & not eod today → `todo.run_eod()`; every 15 ticks → refresh_cal.
- `main()`: Regular activation policy (Dock), `AppDelegate.applicationShouldHandleReopen`, status item + main menu, single-instance guard via `panel.pid`.

## app/panel.html
Single file. `L = {ko:{…}, en:{…}}`, `T()` current strings, `labels()` static labels, `render(state)` rebuilds lists. Pages toggled with `hidden` — CSS has `#set[hidden],#pomo[hidden]{display:none!important}` (plain `display:flex` would override `hidden`). Pomodoro state `P` lives in JS; posts `pomo_title` each tick and `pomo_done` on finish. Activity ping throttled to 5 s.

## app/todo.py
- `CATS` order = dropdown order. `add(title, cat, minutes=None)`, `set_done`, `delete`, `set_title`, `set_category`.
- Obsidian writers: `write_daily_log(day)` (WORK SESSIONS/FOCUS/UNFINISHED/NEXT STEPS/RETRO, ko·en), `write_monthly_page`, `write_dashboard` (30-day stats, category bars, heatmap embed, timeline), `write_heatmap_svg(weeks=16)`.
- `retro(kind)` → `claude -p` once, bilingual output, keeps `## ✍️ 내 노트` on regeneration. `run_eod()` = retro + write_daily_log. `dashboard()` refreshes then opens `obsidian://open?vault=HJ&file=Tracker/Dashboard`.
- Retro section extraction: `retro_section(day, ["요약"])`, `["Summary"]`, `["다음 기간 제안"]`, `["Suggestions for next period"]`.
