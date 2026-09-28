#!/bin/zsh
# todo-cat installer — run once after cloning:
#   git clone https://github.com/hyojinyang-ai/todo-cat ~/.claude-todo && ~/.claude-todo/install/setup.sh
# Re-running is safe (updates the app bundle and login item).
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"          # repo root
PYFW=/Library/Frameworks/Python.framework/Versions/3.13
PY="$PYFW/bin/python3"
APP="$HOME/Applications/To-Do.app"
LABEL="com.todocat.panel"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "▶ 1/6 Checking Python"
if [[ ! -x "$PY" ]]; then
  echo "python.org Python 3.13 is required (Homebrew Python lacks the GUI binary):"
  echo "  https://www.python.org/downloads/macos/"; exit 1
fi

echo "▶ 2/6 Installing dependencies"
"$PY" -m pip install --quiet --user pyobjc-core pyobjc-framework-Cocoa \
  pyobjc-framework-WebKit pyobjc-framework-EventKit msal icalendar \
  recurring-ical-events certifi

echo "▶ 3/6 Configuration"
if [[ ! -f "$HERE/config.json" ]]; then
  VAULTS=()
  OBS="$HOME/Library/Application Support/obsidian/obsidian.json"
  if [[ -f "$OBS" ]]; then
    while IFS= read -r v; do VAULTS+=("$v"); done < <("$PY" - "$OBS" <<'PYEOF'
import json, sys
for v in json.load(open(sys.argv[1])).get("vaults", {}).values():
    print(v.get("path", ""))
PYEOF
)
  fi
  if (( ${#VAULTS[@]} > 0 )); then
    echo "  Obsidian vaults found:"
    i=1; for v in "${VAULTS[@]}"; do echo "    $i) $v"; ((i++)); done
    echo "    0) don't use Obsidian — write plain Markdown to ~/Documents/todo-cat"
    read "choice?  Choose [1]: "; choice=${choice:-1}
  else
    choice=0
  fi
  if [[ "$choice" == "0" ]]; then
    VPATH="$HOME/Documents/todo-cat"; VNAME=""
  else
    VPATH="${VAULTS[$choice]}"; VNAME="$(basename "$VPATH")"
  fi
  read "lang?  UI language en/ko [en]: "; lang=${lang:-en}
  "$PY" - "$HERE/config.json" "$VPATH" "$VNAME" "$lang" <<'PYEOF'
import json, sys
cfg = {"vault_path": sys.argv[2], "vault_name": sys.argv[3], "lang": sys.argv[4],
       "import_hour": 8, "eod_hour": 18, "claude_bin": "", "loaf_after": 300}
json.dump(cfg, open(sys.argv[1], "w"), indent=2)
print("  wrote config.json →", cfg["vault_path"])
PYEOF
else
  echo "  config.json exists — keeping it"
fi
VPATH="$("$PY" -c "import json,os;print(os.path.expanduser(json.load(open('$HERE/config.json'))['vault_path']))")"
mkdir -p "$VPATH/Tracker/Retros" "$VPATH/Tracker/Log" "$VPATH/Tracker/Monthly" "$HERE/state"

echo "▶ 4/6 Creating app bundle ($APP)"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$HERE/install/Info.plist" "$APP/Contents/Info.plist"
cp "$HERE/install/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
cp -f "$PYFW/Resources/Python.app/Contents/MacOS/Python" "$APP/Contents/MacOS/To-Do-bin"
cat > "$APP/Contents/MacOS/To-Do" <<WRAP
#!/bin/zsh
exec "\$(dirname "\$0")/To-Do-bin" "$HERE/app/panel.py"
WRAP
chmod +x "$APP/Contents/MacOS/To-Do" "$APP/Contents/MacOS/To-Do-bin"
codesign -s - --force --deep "$APP" 2>/dev/null

echo "▶ 5/6 Registering login item"
sed "s|__HOME__|$HOME|g" "$HERE/install/$LABEL.plist" > "$AGENT"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENT"

echo "▶ 6/6 Starting"
pkill -f "app/panel.py" 2>/dev/null || true; rm -f "$HERE/state/panel.pid"
launchctl kickstart "gui/$(id -u)/$LABEL"
echo
echo "✅ todo-cat is running. Next:"
echo "   • Calendar: add your account in System Settings → Internet Accounts (calendar on),"
echo "     then click 'Re-check calendar source' in the panel and allow access."
echo "   • Dock: drag $APP from Finder onto the Dock."
echo "   • AI retro (optional): install Claude Code CLI and log in once (\`claude\`)."
