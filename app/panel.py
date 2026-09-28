#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
todo-cat floating panel — always-on-top To-Do + today's calendar events + cat pet.
Data: <vault>/Tracker/tasks.json (vault from config.json, shared with todo.py)
"""
import json
import objc
import os
import subprocess
import sys
import threading
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # repo root (~/.claude-todo)
APP, ASSETS, STATE = ROOT / "app", ROOT / "assets", ROOT / "state"
sys.path.insert(0, str(APP))
import todo  # data core

from AppKit import (NSApplication, NSApplicationActivationPolicyRegular,
                    NSImageView, NSWindowStyleMaskBorderless,
                    NSWindowStyleMaskClosable,
                    NSImage, NSMenu, NSMenuItem, NSStatusBar,
                    NSVariableStatusItemLength,
                    NSBackingStoreBuffered, NSColor, NSFloatingWindowLevel,
                    NSMakeRect, NSPanel, NSScreen,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorFullScreenAuxiliary,
                    NSWindowStyleMaskFullSizeContentView,
                    NSWindowStyleMaskNonactivatingPanel,
                    NSWindowStyleMaskMiniaturizable,
                    NSWindowStyleMaskResizable,
                    NSWindowStyleMaskTitled)
from Foundation import NSObject, NSURL
from PyObjCTools import AppHelper
from WebKit import WKWebView, WKWebViewConfiguration

HOME = STATE                                     # runtime state dir (git-ignored)
HTML = APP / "panel.html"
EV_STATE = STATE / "events_state.json"
CAL_CACHE = STATE / "cal_cache.json"
MSAL_CACHE = STATE / "msal_cache.bin"
PIDFILE = STATE / "panel.pid"

CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"  # public client id of Microsoft Graph CLI
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPES = ["Calendars.Read"]
def _local_tz():
    try:
        return os.readlink("/etc/localtime").split("zoneinfo/")[-1]
    except Exception:
        return "UTC"


TZ = _local_tz()
WD_KO = ["월", "화", "수", "목", "금", "토", "일"]


def jload(p, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def jsave(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False))


SETTINGS = HOME / "settings.json"
# desktop cats: assets/pets/<key>/ → (name shown in Settings, pet window size in pt,
# Pomodoro image under assets/ or None = just sit). The first one is the default.
PETS = {"sprout": ("Sprout", (119, 108), "pomo_zen.png"),
        "ham": ("Ham", (119, 108), None),
        "sweetie": ("Sweetie", (108, 108), None)}


def get_settings():
    c = jload(SETTINGS, {})
    return {"opacity": float(c.get("opacity", 1.0)),
            "lang": c.get("lang", todo.CFG["lang"]),
            "import_events": bool(c.get("import_events", True)),
            "pomo_work": int(c.get("pomo_work", 25)),
            "pomo_break": int(c.get("pomo_break", 5)),
            "pet_enabled": bool(c.get("pet_enabled", True)),
            "pet_walk": bool(c.get("pet_walk", True)),
            "pets": [k for k in c.get("pets", [next(iter(PETS))]) if k in PETS]
            or [next(iter(PETS))]}


def set_setting(k, v):
    c = jload(SETTINGS, {})
    c[k] = v
    jsave(SETTINGS, c)


def ev_state():
    return jload(EV_STATE, {}).get(date.today().isoformat(), {})


def set_ev_state(eid, st):
    allst = jload(EV_STATE, {})
    day = allst.setdefault(date.today().isoformat(), {})
    if st:
        day[eid] = st
    else:
        day.pop(eid, None)
    jsave(EV_STATE, allst)


def msal_app():
    import msal
    cache = msal.SerializableTokenCache()
    if MSAL_CACHE.exists():
        cache.deserialize(MSAL_CACHE.read_text())
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY,
                                       token_cache=cache)
    return app, cache


def save_cache(cache):
    if cache.has_state_changed:
        MSAL_CACHE.write_text(cache.serialize())


def get_token_silent():
    app, cache = msal_app()
    accts = app.get_accounts()
    if not accts:
        return None
    r = app.acquire_token_silent(SCOPES, account=accts[0])
    save_cache(cache)
    return (r or {}).get("access_token")


def fetch_events(token):
    t = date.today()
    s = f"{t.isoformat()}T00:00:00"
    e = f"{(t + timedelta(days=1)).isoformat()}T00:00:00"
    url = ("https://graph.microsoft.com/v1.0/me/calendarview"
           f"?startDateTime={s}&endDateTime={e}"
           "&$select=id,subject,start,end,isAllDay"
           "&$orderby=start/dateTime&$top=50")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Prefer": f'outlook.timezone="{TZ}"'})
    with urllib.request.urlopen(req, timeout=20) as r:
        items = json.loads(r.read().decode()).get("value", [])
    evs = []
    for it in items:
        st = it["start"]["dateTime"][11:16]
        en = it["end"]["dateTime"][11:16]
        evs.append({"id": it["id"][-40:], "title": it.get("subject") or "(No title)",
                    "time": "All day" if it.get("isAllDay") else st,
                    "end": "" if it.get("isAllDay") else en})
    jsave(CAL_CACHE, {"date": date.today().isoformat(),
                      "fetched": datetime.now().isoformat(), "events": evs})
    return evs


def cached_events():
    c = jload(CAL_CACHE, {})
    if c.get("date") == date.today().isoformat():
        return c.get("events", [])
    return []


ICS_FILE = HOME / "ics_url.txt"


def fetch_events_ics(url):
    import icalendar
    import recurring_ical_events
    if url.startswith("webcal://"):
        url = "https://" + url[9:]
    raw = urllib.request.urlopen(url, timeout=25).read()
    cal = icalendar.Calendar.from_ical(raw)
    t = date.today()
    d0 = datetime(t.year, t.month, t.day).astimezone()
    evs_raw = recurring_ical_events.of(cal).between(d0, d0 + timedelta(days=1))
    evs = []
    for ev in evs_raw:
        st = ev.get("DTSTART").dt
        en = ev.get("DTEND").dt if ev.get("DTEND") else st
        allday = not isinstance(st, datetime)
        evs.append({"id": (str(ev.get("UID"))[:24] + str(st))[-40:],
                    "title": str(ev.get("SUMMARY", "(No title)")),
                    "time": "All day" if allday else st.astimezone().strftime("%H:%M"),
                    "end": "" if allday else en.astimezone().strftime("%H:%M")})
    evs.sort(key=lambda x: x["time"])
    jsave(CAL_CACHE, {"date": t.isoformat(),
                      "fetched": datetime.now().isoformat(), "events": evs})
    return evs


def fetch_events_eventkit(interactive):
    import EventKit
    from Foundation import NSDate
    ET = 0
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(ET)
    store = EventKit.EKEventStore.alloc().init()
    if status not in (3, 4):
        if not interactive:
            raise RuntimeError("No calendar permission")
        got, done = {}, threading.Event()

        def cb(granted, err):
            got["g"] = bool(granted)
            done.set()
        if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
            store.requestFullAccessToEventsWithCompletion_(cb)
        else:
            store.requestAccessToEntityType_completion_(ET, cb)
        done.wait(120)
        if not got.get("g"):
            raise RuntimeError("Calendar access denied (System Settings > Privacy > Calendars)")
    cals = store.calendarsForEntityType_(ET)
    if not cals or not len(cals):
        raise RuntimeError("No calendar accounts in macOS Calendar")
    t = date.today()
    s0 = datetime(t.year, t.month, t.day).astimezone().timestamp()
    pred = store.predicateForEventsWithStartDate_endDate_calendars_(
        NSDate.dateWithTimeIntervalSince1970_(s0),
        NSDate.dateWithTimeIntervalSince1970_(s0 + 86400), None)
    out = []
    for ev in store.eventsMatchingPredicate_(pred) or []:
        allday = bool(ev.isAllDay())
        sd = datetime.fromtimestamp(ev.startDate().timeIntervalSince1970())
        ed = datetime.fromtimestamp(ev.endDate().timeIntervalSince1970())
        out.append({"id": str(ev.eventIdentifier())[-40:],
                    "title": str(ev.title() or "(No title)"),
                    "time": "All day" if allday else sd.strftime("%H:%M"),
                    "end": "" if allday else ed.strftime("%H:%M")})
    out.sort(key=lambda x: x["time"])
    jsave(CAL_CACHE, {"date": t.isoformat(),
                      "fetched": datetime.now().isoformat(), "events": out})
    return out


def build_state(cal_status):
    db = todo.load()
    open_t, done_t, total = todo.today_stats(db)
    t = date.today()
    est = ev_state()
    events = []
    for ev in cached_events():
        s = est.get(ev["id"], "")
        if s == "hidden":
            continue
        events.append({**ev, "done": s == "done"})
    cfg = get_settings()
    if cfg["lang"] == "en":
        wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        mn = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        dl = f"{wd[t.weekday()]}, {mn[t.month - 1]} {t.day}"
        labels = {k: k for k in todo.CATS}
    else:
        dl = f"{t.month}월 {t.day}일 {WD_KO[t.weekday()]}요일"
        labels = {k: v[1] for k, v in todo.CATS.items()}
    return {
        "date_label": dl, "settings": cfg,
        "done": len(done_t), "total": total,
        "events": events, "cal_status": cal_status,
        "pomo_today": pomo_today(),
        "cats": {k: v[0] for k, v in todo.CATS.items()},
        "cat_labels": labels,
        "pet_list": [[k, v[0]] for k, v in PETS.items()],
        "open": [{"id": x["id"], "title": x["title"], "cat": x["category"]}
                 for x in sorted(open_t, key=lambda x: x["id"], reverse=True)],
        "closed": [{"id": x["id"], "title": x["title"], "cat": x["category"]}
                   for x in done_t]}


IMPORTED = HOME / "imported.json"
POMO_LOG = HOME / "pomo_log.json"
EOD = HOME / "eod.json"


def pomo_today():
    d = jload(POMO_LOG, {}).get(date.today().isoformat(), {})
    if isinstance(d, int):
        d = {"count": d, "min": d * 25}
    return {"count": int(d.get("count", 0)), "min": int(d.get("min", 0))}


def pomo_inc(mins):
    log = jload(POMO_LOG, {})
    k = date.today().isoformat()
    cur = log.get(k, {})
    if isinstance(cur, int):
        cur = {"count": cur, "min": cur * 25}
    cur["count"] = int(cur.get("count", 0)) + 1
    cur["min"] = int(cur.get("min", 0)) + int(mins)
    log[k] = cur
    jsave(POMO_LOG, log)


def do_fetch(interactive=False):
    url = ICS_FILE.read_text().strip() if ICS_FILE.exists() else ""
    if url:
        fetch_events_ics(url)
        return "connected"
    try:
        fetch_events_eventkit(interactive)
        return "connected"
    except Exception as ek:
        tok = get_token_silent()
        if tok:
            fetch_events(tok)
            return "connected"
        if interactive:
            return f"error:{str(ek)[:120]}"
        return "none"


def import_events_as_todos():
    t = date.today().isoformat()
    imp = jload(IMPORTED, {})
    ids = set(imp.get("ids", [])) if imp.get("date") == t else set()
    est = ev_state()
    for ev in cached_events():
        if ev["id"] in ids or ev["id"] in est:
            continue
        prefix = (ev["time"] + " ") if ev["time"] else ""
        mins = None
        try:
            if ev.get("end") and ":" in ev.get("time", ""):
                h1, m1 = map(int, ev["time"].split(":"))
                h2, m2 = map(int, ev["end"].split(":"))
                mins = max(0, (h2 * 60 + m2) - (h1 * 60 + m1))
        except Exception:
            mins = None
        todo.add(prefix + ev["title"], "Meeting", mins)
        set_ev_state(ev["id"], "hidden")
        ids.add(ev["id"])
    jsave(IMPORTED, {"date": t, "ids": sorted(ids)})


class Pet:
    """One desktop cat: its window, images and animation state."""

    def __init__(self, key, win, view, imgs, direction=1):
        self.key, self.win, self.view, self.imgs = key, win, view, imgs
        self.state = "idle"
        self.dir = direction
        self.step = 0
        self.frame = 0
        self.pause = 0.0
        self.moving = False
        self.timer = None
        self.loaf = 0          # 0 = not loafing, 1..8 = loaf frame shown
        self.loaf_dir = 0      # +1 settling down, -1 getting up, 0 = still
        self.loaf_next = 0.0
        self.pomo = False      # Pomodoro work session running

    def apply_image(self):
        if self.state == "idle" and self.pomo:
            base = "zen"       # rule: Pomodoro → singing-bowl cat (cats without one just sit)
        elif self.state == "idle" and self.loaf:
            base = f"loaf{self.loaf}"
        elif self.state == "idle" and self.moving:
            base = f"walk{(self.frame % 8) + 1}"
        else:
            base = self.state
        flip = "_flip" if self.dir < 0 else ""
        key = base if base == "zen" else base + flip
        img = self.imgs.get(key) or self.imgs.get(self.state + flip) or self.imgs.get(self.state)
        if img is not None:
            AppHelper.callAfter(lambda: self.view.setImage_(img))

    def set(self, state, revert_sec=None):
        self.state = state
        if state != "idle":
            self.loaf = self.loaf_dir = 0   # an expression interrupts the loaf
        if revert_sec:
            import time as _t
            self.pause = _t.time() + revert_sec
        self.apply_image()
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if revert_sec:
            self.timer = threading.Timer(revert_sec, lambda: self.set("idle"))
            self.timer.daemon = True
            self.timer.start()


class Bridge(NSObject):
    def init(self):
        self = objc.super(Bridge, self).init()
        self.webview = None
        self.panel = None
        self.status = None
        self.pomo_text = ""
        self.pets = []                    # one Pet per cat in PETS (shown or not)
        self.pet_active_until = 0.0
        self.pomo_running = False
        import time as _t
        self.pet_last_touch = _t.time()   # last panel interaction
        self.cal_status = "connected" if cached_events() else "none"
        return self

    def push(self):
        state = build_state(self.cal_status)
        js = f"render({json.dumps(state, ensure_ascii=False)})"

        def ui():
            self.webview.evaluateJavaScript_completionHandler_(js, None)
            if self.status is not None:
                self.status.button().setTitle_(
                    self.pomo_text or f" {state['done']}/{state['total']}")
        AppHelper.callAfter(ui)

    def active_pets(self):
        chosen = get_settings()["pets"]
        return [p for p in self.pets if p.key in chosen]

    def set_pet(self, state, revert_sec=None):
        for p in self.active_pets():
            p.set(state, revert_sec)

    def show_pets(self):
        s = get_settings()
        for p in self.pets:
            on = s["pet_enabled"] and p.key in s["pets"]
            AppHelper.callAfter(
                lambda w=p.win, on=on: w.orderFrontRegardless() if on else w.orderOut_(None))

    def togglePanel_(self, sender):
        if self.panel.isVisible():
            self.panel.orderOut_(None)
        else:
            self.panel.makeKeyAndOrderFront_(None)

    def openDash_(self, sender):
        threading.Thread(target=todo.dashboard, daemon=True).start()

    def dailyRetro_(self, sender):
        threading.Thread(target=todo.retro, args=("daily",),
                         daemon=True).start()

    def runjs_(self, code):
        self.panel.makeKeyAndOrderFront_(None)
        AppHelper.callAfter(
            lambda: self.webview.evaluateJavaScript_completionHandler_(
                code, None))

    def newItem_(self, sender):
        self.runjs_('document.getElementById("set").hidden=true;'
                 'document.getElementById("pomo").hidden=true;'
                 'document.getElementById("inp").focus();')

    def showSettings_(self, sender):
        self.runjs_('document.getElementById("pomo").hidden=true;'
                 'document.getElementById("set").hidden=false;')

    def showPomo_(self, sender):
        self.runjs_('document.getElementById("set").hidden=true;'
                 'document.getElementById("pomo").hidden=false;'
                 'pomoUI();')

    def quitApp_(self, sender):
        NSApplication.sharedApplication().terminate_(None)

    def refresh_cal(self, interactive=False):
        def work():
            try:
                self.cal_status = do_fetch(interactive)
            except Exception as e:
                self.cal_status = f"error:{str(e)[:120]}"
            self.push()
        threading.Thread(target=work, daemon=True).start()

    def device_login(self):
        try:
            app, cache = msal_app()
            flow = app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(flow.get("error_description", "device flow rejected"))
            self.cal_status = {"code": flow["user_code"],
                               "url": flow["verification_uri"]}
            self.push()
            subprocess.run(["open", flow["verification_uri"]])
            r = app.acquire_token_by_device_flow(flow)
            save_cache(cache)
            if "access_token" in r:
                fetch_events(r["access_token"])
                self.cal_status = "connected"
            else:
                self.cal_status = f"error:{r.get('error_description', 'login failed')[:120]}"
        except Exception as e:
            self.cal_status = f"error:{str(e)[:120]}"
        self.push()

    def userContentController_didReceiveScriptMessage_(self, ucc, msg):
        # An exception escaping this callback aborts the whole process (pyobjc → ObjC throw).
        try:
            self.handle_message(msg)
        except Exception:
            import traceback
            print("[bridge] unhandled exception:", file=sys.stderr)
            traceback.print_exc()

    def handle_message(self, msg):
        b = msg.body()
        a = str(b.get("action", ""))
        if a not in ("state", "pomo_title", "refresh_cal"):
            import time as _t
            self.pet_active_until = _t.time() + 60   # walk for 60 s after any interaction
            self.pet_last_touch = _t.time()
            for p in self.pets:
                if p.loaf or p.loaf_dir > 0:
                    p.loaf_dir = -1                   # get up (loaf in reverse) before walking
        if a == "activity":
            return
        if a == "state":
            self.push()
            self.refresh_cal()
        elif a == "add":
            todo.add(str(b["title"]), str(b["cat"]))
            self.set_pet("alert", 2.5)
            self.push()
        elif a == "done":
            todo.set_done(int(b["id"]), bool(b["flag"]))
            if bool(b["flag"]):
                self.set_pet("happy", 2.5)
            self.push()
        elif a == "delete":
            todo.delete(int(b["id"])); self.push()
        elif a == "cat":
            todo.set_category(int(b["id"]), str(b["cat"])); self.push()
        elif a == "title":
            todo.set_title(int(b["id"]), str(b["title"])); self.push()
        elif a == "ev":
            set_ev_state(str(b["id"]), str(b["state"])); self.push()
        elif a == "connect":
            self.refresh_cal(interactive=True)
        elif a == "refresh_cal":
            self.refresh_cal()
        elif a == "dashboard":
            threading.Thread(target=todo.dashboard, daemon=True).start()
        elif a == "retro":
            threading.Thread(target=todo.retro, args=(str(b["kind"]),),
                             daemon=True).start()
        elif a == "setting":
            k, v = str(b["key"]), b["value"]
            if k == "pets":
                v = [str(x) for x in v]   # JS array arrives as NSArray (not JSON-serialisable)
            set_setting(k, v)
            if k == "opacity":
                AppHelper.callAfter(
                    lambda: self.panel.setAlphaValue_(float(v)))
            if k == "pet_walk":
                for p in self.pets:
                    AppHelper.callAfter(
                        lambda w=p.win: w.setMovableByWindowBackground_(not v))
            if k in ("pet_enabled", "pets"):
                self.show_pets()
            self.push()
        elif a == "pomo_title":
            self.pomo_text = str(b.get("text", ""))
            running = self.pomo_text.startswith("🍅")   # work session (☕ = break)
            if running != self.pomo_running:
                self.pomo_running = running
                for p in self.pets:
                    p.pomo = running
                    p.apply_image()
            if self.status is not None:
                txt = self.pomo_text
                AppHelper.callAfter(
                    lambda: self.status.button().setTitle_(txt or " "))
        elif a == "pomo_done":
            mode = str(b.get("mode", "work"))
            ko = get_settings()["lang"] == "ko"
            if mode == "work":
                pomo_inc(int(b.get("mins", 25)))
                todo.notify("집중 세션 완료! 잠깐 쉬어가세요 ☕" if ko
                       else "Focus session done! Take a break ☕", "Pomodoro")
            else:
                todo.notify("휴식 끝 — 다시 집중할 시간이에요 🍅" if ko
                       else "Break over — time to focus 🍅", "Pomodoro")
            snd = ASSETS / "singing-bowl.mp3"
            subprocess.Popen(["afplay", str(snd) if snd.exists()
                              else "/System/Library/Sounds/Glass.aiff"])
            self.push()
        elif a == "quit":
            NSApplication.sharedApplication().terminate_(None)


class AppDelegate(NSObject):
    panel = objc.ivar()

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, flag):
        if self.panel is not None:
            self.panel.makeKeyAndOrderFront_(None)
        return True


class Panel(NSPanel):
    def canBecomeKeyWindow(self):
        return True



def main():
    HOME.mkdir(exist_ok=True)
    if PIDFILE.exists():
        try:
            os.kill(int(PIDFILE.read_text().strip()), 0)
            sys.exit(0)  # already running — keep the existing instance
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    PIDFILE.write_text(str(os.getpid()))
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    w, h = 336, 560
    scr = NSScreen.mainScreen().visibleFrame()
    rect = NSMakeRect(scr.origin.x + scr.size.width - w - 20,
                      scr.origin.y + scr.size.height - h - 20, w, h)
    style = (NSWindowStyleMaskTitled | NSWindowStyleMaskFullSizeContentView |
             NSWindowStyleMaskNonactivatingPanel |
             NSWindowStyleMaskResizable |
             NSWindowStyleMaskMiniaturizable |
             NSWindowStyleMaskClosable)
    panel = Panel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, style, NSBackingStoreBuffered, False)
    panel.setTitle_("")
    panel.setTitlebarAppearsTransparent_(True)
    panel.setLevel_(NSFloatingWindowLevel)
    panel.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces |
                                 NSWindowCollectionBehaviorFullScreenAuxiliary)
    panel.setHidesOnDeactivate_(False)
    panel.setMovableByWindowBackground_(False)
    panel.setBackgroundColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(
        0.961, 0.965, 0.949, 1.0))
    z = panel.standardWindowButton_(2)  # hide zoom button only
    if z:
        z.setHidden_(True)
    panel.setReleasedWhenClosed_(False)
    if not panel.setFrameUsingName_("todoCatPanel"):
        panel.setFrame_display_(rect, True)
    panel.setFrameAutosaveName_("todoCatPanel")
    panel.setMinSize_((300, 360))
    panel.setMaxSize_((560, 1500))
    panel.setAlphaValue_(get_settings()["opacity"])

    bridge = Bridge.alloc().init()
    bridge.panel = panel
    delegate.panel = panel
    conf = WKWebViewConfiguration.alloc().init()
    conf.userContentController().addScriptMessageHandler_name_(bridge, "app")
    cb = panel.contentView().bounds()
    web = WKWebView.alloc().initWithFrame_configuration_(
        NSMakeRect(0, 0, cb.size.width, cb.size.height - 26), conf)
    web.setAutoresizingMask_(18)  # width | height
    try:
        web.setValue_forKey_(False, "drawsBackground")
    except Exception:
        pass
    bridge.webview = web
    panel.contentView().addSubview_(web)
    web.loadFileURL_allowingReadAccessToURL_(
        NSURL.fileURLWithPath_(str(HTML)),
        NSURL.fileURLWithPath_(str(ROOT)))
    status = NSStatusBar.systemStatusBar().statusItemWithLength_(
        NSVariableStatusItemLength)
    status.button().setImage_(
        NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "checkmark.circle", "To-Do"))
    ko = get_settings()["lang"] == "ko"
    men = NSMenu.alloc().init()

    def mi(title, sel):
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, sel, "")
        it.setTarget_(bridge)
        men.addItem_(it)
    mi("패널 보이기/숨기기" if ko else "Show/Hide panel", "togglePanel:")
    mi("대시보드" if ko else "Dashboard", "openDash:")
    mi("Daily 회고" if ko else "Daily retro", "dailyRetro:")
    men.addItem_(NSMenuItem.separatorItem())
    mi("종료" if ko else "Quit", "quitApp:")
    status.setMenu_(men)
    bridge.status = status

    def addmi(menu, title, sel, key, target=None):
        it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, sel, key)
        if target is not None:
            it.setTarget_(target)
        menu.addItem_(it)
        return it

    mm = NSMenu.alloc().init()
    # To-Do (application menu)
    appit = NSMenuItem.alloc().init()
    mm.addItem_(appit)
    am = NSMenu.alloc().init()
    addmi(am, "To-Do에 관하여" if ko else "About To-Do",
          "orderFrontStandardAboutPanel:", "")
    am.addItem_(NSMenuItem.separatorItem())
    addmi(am, "설정…" if ko else "Settings…", "showSettings:", ",", bridge)
    am.addItem_(NSMenuItem.separatorItem())
    addmi(am, "To-Do 가리기" if ko else "Hide To-Do", "hide:", "h")
    am.addItem_(NSMenuItem.separatorItem())
    addmi(am, "To-Do 종료" if ko else "Quit To-Do", "terminate:", "q")
    appit.setSubmenu_(am)
    # File
    fit = NSMenuItem.alloc().init()
    mm.addItem_(fit)
    fm = NSMenu.alloc().initWithTitle_("파일" if ko else "File")
    addmi(fm, "새 항목" if ko else "New Item", "newItem:", "n", bridge)
    addmi(fm, "닫기" if ko else "Close", "performClose:", "w")
    fit.setSubmenu_(fm)
    # Edit (clipboard shortcuts)
    eit = NSMenuItem.alloc().init()
    mm.addItem_(eit)
    em = NSMenu.alloc().initWithTitle_("편집" if ko else "Edit")
    addmi(em, "실행 취소" if ko else "Undo", "undo:", "z")
    addmi(em, "실행 복귀" if ko else "Redo", "redo:", "Z")
    em.addItem_(NSMenuItem.separatorItem())
    addmi(em, "오려두기" if ko else "Cut", "cut:", "x")
    addmi(em, "복사하기" if ko else "Copy", "copy:", "c")
    addmi(em, "붙여넣기" if ko else "Paste", "paste:", "v")
    addmi(em, "전체 선택" if ko else "Select All", "selectAll:", "a")
    eit.setSubmenu_(em)
    # View
    vit = NSMenuItem.alloc().init()
    mm.addItem_(vit)
    vm = NSMenu.alloc().initWithTitle_("보기" if ko else "View")
    addmi(vm, "포모도로" if ko else "Pomodoro", "showPomo:", "p", bridge)
    addmi(vm, "대시보드" if ko else "Dashboard", "openDash:", "d", bridge)
    vit.setSubmenu_(vm)
    # Window
    wit = NSMenuItem.alloc().init()
    mm.addItem_(wit)
    wm = NSMenu.alloc().initWithTitle_("윈도우" if ko else "Window")
    addmi(wm, "최소화" if ko else "Minimize", "performMiniaturize:", "m")
    wit.setSubmenu_(wm)
    app.setWindowsMenu_(wm)
    app.setMainMenu_(mm)
    panel.makeKeyAndOrderFront_(None)

    # ── desktop pets (one window per cat) ──
    # place inside the visible frame of the screen that holds the panel
    pf = panel.frame()
    tgt = NSScreen.mainScreen()
    for sc in NSScreen.screens():
        f = sc.frame()
        if (f.origin.x <= pf.origin.x < f.origin.x + f.size.width
                and f.origin.y <= pf.origin.y < f.origin.y + f.size.height):
            tgt = sc
            break
    vf = tgt.visibleFrame()
    for i, (key, (_name, (pw, ph), zen)) in enumerate(PETS.items()):
        px = min(max(pf.origin.x - pw - 14 - i * 60, vf.origin.x + 10),
                 vf.origin.x + vf.size.width - pw - 10)
        py = min(max(pf.origin.y + 40, vf.origin.y + 10),
                 vf.origin.y + vf.size.height - ph - 10)
        prect = NSMakeRect(px, py, pw, ph)
        pet = Panel.alloc().initWithContentRect_styleMask_backing_defer_(
            prect, NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered, False)
        pet.setOpaque_(False)
        pet.setBackgroundColor_(NSColor.clearColor())
        pet.setLevel_(NSFloatingWindowLevel + 1)  # always above the panel
        pet.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces |
                                   NSWindowCollectionBehaviorFullScreenAuxiliary)
        pet.setHidesOnDeactivate_(False)
        pet.setMovableByWindowBackground_(not get_settings()["pet_walk"])
        pet.setHasShadow_(False)
        autosave = "catPet3" if i == 0 else f"catPet3_{key}"   # default cat keeps its saved spot
        if pet.setFrameUsingName_(autosave):
            sf = pet.frame()
            ok = any((sc.visibleFrame().origin.x - 5 <= sf.origin.x
                      and sf.origin.x + pw
                      <= sc.visibleFrame().origin.x + sc.visibleFrame().size.width + 5
                      and sc.visibleFrame().origin.y - 5 <= sf.origin.y
                      and sf.origin.y + ph
                      <= sc.visibleFrame().origin.y + sc.visibleFrame().size.height + 5)
                     for sc in NSScreen.screens())
            pet.setFrame_display_(NSMakeRect(sf.origin.x, sf.origin.y, pw, ph)
                                  if ok else prect, True)
        else:
            pet.setFrame_display_(prect, True)
        pet.setFrameAutosaveName_(autosave)
        pv = NSImageView.alloc().initWithFrame_(pet.contentView().bounds())
        pv.setAutoresizingMask_(18)
        pv.setImageScaling_(3)  # proportionally up-or-down
        imgs = {}
        for ik, fn in (("idle", "cat.png"), ("alert", "pet_alert.png"),
                       ("happy", "pet_happy.png"),
                       ("idle_flip", "cat_flip.png"),
                       ("alert_flip", "pet_alert_flip.png"),
                       ("happy_flip", "pet_happy_flip.png"),
                       *[(f"walk{j}", f"walk{j}.png") for j in range(1, 9)],
                       *[(f"walk{j}_flip", f"walk{j}_flip.png") for j in range(1, 9)],
                       *[(f"loaf{j}", f"loaf{j}.png") for j in range(1, 9)],
                       *[(f"loaf{j}_flip", f"loaf{j}_flip.png") for j in range(1, 9)]):
            im = NSImage.alloc().initWithContentsOfFile_(str(ASSETS / "pets" / key / fn))
            if im:
                imgs[ik] = im
        if zen:
            im = NSImage.alloc().initWithContentsOfFile_(str(ASSETS / zen))
            if im:
                imgs["zen"] = im
        if "idle" in imgs:
            pv.setImage_(imgs["idle"])
        pet.contentView().addSubview_(pv)
        bridge.pets.append(Pet(key, pet, pv, imgs, direction=1 if i % 2 == 0 else -1))
        fr = pet.frame()
        print(f"[pet] {key} frame=({fr.origin.x:.0f},{fr.origin.y:.0f} "
              f"{fr.size.width:.0f}x{fr.size.height:.0f}) imgs={len(imgs)}",
              file=sys.stderr)
    bridge.show_pets()

    def walker():
        import time as _t
        LOAF_AFTER = 300   # seconds without panel use before the cats settle into a loaf
        while True:
            _t.sleep(0.07)
            try:
                if not get_settings()["pet_walk"]:
                    continue
                if not get_settings()["pet_enabled"]:
                    continue
                if not panel.isVisible():
                    continue
                pets_on = bridge.active_pets()
                for n, p in enumerate(pets_on):
                    step_pet(p, pets_on[:n], _t.time(), LOAF_AFTER)
            except Exception:
                pass

    def step_pet(p, before, now, loaf_after):
        """One animation tick for one cat. `before` = cats earlier in the list (they have right of way)."""
        if now < p.pause:
            if p.moving:
                p.moving = False
                p.apply_image()
            return
        pf = panel.frame()
        cf = p.win.frame()
        left = pf.origin.x + 6
        right = pf.origin.x + pf.size.width - cf.size.width - 6
        if right <= left:
            return
        if (not p.loaf and not p.loaf_dir and not p.pomo
                and p.state == "idle" and now > bridge.pet_active_until
                and now - bridge.pet_last_touch > loaf_after):
            p.loaf_dir = 1
        if p.loaf_dir and now >= p.loaf_next:
            p.loaf = min(max(p.loaf + p.loaf_dir, 0), 8)
            settling = p.loaf_dir > 0
            if p.loaf in (0, 8):
                p.loaf_dir = 0
                print(f"[pet] {p.key} " + ("loafing" if p.loaf else "up"), file=sys.stderr)
            p.loaf_next = now + (0.25 if settling else 0.12)
            p.apply_image()
        # sitting on top of another cat? keep walking until there is space (if the panel has room)
        crowded = False
        if not p.loaf and not p.loaf_dir and before:
            room = pf.size.width - 12 > cf.size.width + sum(o.win.frame().size.width for o in before)
            for o in before:
                of = o.win.frame()
                if (room and abs((cf.origin.x + cf.size.width / 2) - (of.origin.x + of.size.width / 2))
                        < (cf.size.width + of.size.width) * 0.35):
                    crowded = True
        if (now > bridge.pet_active_until and not crowded) or p.pomo or p.loaf or p.loaf_dir:
            # idle, Pomodoro or loaf: sit still, follow the panel if it moves
            if p.moving:
                p.moving = False
                p.apply_image()
            sx = min(max(cf.origin.x, left), right)
            sy = pf.origin.y + pf.size.height - 5
            if abs(sx - cf.origin.x) > 0.5 or abs(sy - cf.origin.y) > 0.5:
                AppHelper.callAfter(
                    lambda w=p.win, x=sx, y=sy: w.setFrameOrigin_((x, y)))
            return
        if not p.moving:
            p.moving = True
            p.apply_image()
        nx = cf.origin.x + p.dir * 3.6
        if nx < left:
            nx, p.dir = left, 1
            p.apply_image()
        elif nx > right:
            nx, p.dir = right, -1
            p.apply_image()
        p.step = (p.step + 1) % 8
        if p.step != p.frame:
            p.frame = p.step
            p.apply_image()
        bob = -1 if p.step in (2, 3, 6, 7) else 0
        ny = pf.origin.y + pf.size.height - 5 + bob
        # if the panel hugs the top edge, lower the cat so it stays fully visible
        for sc in NSScreen.screens():
            v = sc.visibleFrame()
            if (v.origin.x <= pf.origin.x < v.origin.x + v.size.width
                    and v.origin.y <= pf.origin.y + pf.size.height
                    <= v.origin.y + v.size.height + 1):
                top = v.origin.y + v.size.height
                if ny + cf.size.height > top:
                    ny = top - cf.size.height
                break
        AppHelper.callAfter(
            lambda w=p.win, x=nx, y=ny: w.setFrameOrigin_((x, y)))
    threading.Thread(target=walker, daemon=True).start()

    def scheduler():
        import time as _t
        last_day = date.today()
        tick = 0
        while True:
            _t.sleep(60)
            tick += 1
            nd = date.today()
            if nd != last_day:
                try:
                    todo.write_daily_log(last_day)
                except Exception:
                    pass
                last_day = nd
                bridge.push()
            cfg = get_settings()
            imp = jload(IMPORTED, {})
            if (cfg["import_events"] and datetime.now().hour >= int(todo.CFG["import_hour"])
                    and imp.get("date") != nd.isoformat()):
                try:
                    bridge.cal_status = do_fetch(False)
                except Exception:
                    pass
                import_events_as_todos()
                bridge.push()
            eod = jload(EOD, {})
            if (datetime.now().hour >= int(todo.CFG["eod_hour"])
                    and eod.get("date") != nd.isoformat()):
                jsave(EOD, {"date": nd.isoformat(),
                            "ran": datetime.now().isoformat()})
                threading.Thread(target=todo.run_eod, daemon=True).start()
            elif tick % 15 == 0:
                bridge.refresh_cal()
    threading.Thread(target=scheduler, daemon=True).start()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
