#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UX Inbox feed — the designer's open work and research follow-ups from ux-inbox, kept in sync as to-dos.

Feed:  an iCalendar file of VTODOs (ux-inbox lib/feeds.mjs). Settings → "UX Inbox feed" takes an
       http(s):// or webcal:// link or a file path. The live link (http://localhost:5310/feeds/<you>.ics)
       only answers while the inbox server runs, so when it fails the published file
       <UX Inbox folder>/docs/feeds/<you>.ics is read instead.
Sync:  by UID into tasks.json (source "ux-inbox", external_uid, url). New UID → add; changed title → update;
       feed COMPLETED → done; UID gone and task still open → removed. The feed never reopens a task you ticked.
       Nothing is removed unless the feed was read and parsed as a VCALENDAR (a login page never wipes tasks).
Tick-back: ticking a synced task writes ONE event file into <UX Inbox folder>/data/edits/events/
       (the shared log, same format as ux-inbox lib/eventlog.mjs): item → status.corrected/confirmed to Done,
       finding → finding.resolved. Unticking writes the matching undo. Feed-made changes never write back.
No pyobjc here: panel.py and todo.py call in, tests import it directly.
"""
import json
import os
import re
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "state" / "settings.json"
STATUS = ROOT / "state" / "uxfeed_status.json"
SOURCE = "ux-inbox"
REASON = "Ticked off in todo-cat"
CATEGORY = {"item": "Design", "finding": "Research"}


def settings():
    try:
        c = json.loads(SETTINGS.read_text())
    except Exception:
        c = {}
    return {"feed": str(c.get("uxinbox_feed", "") or "").strip(),
            "folder": str(c.get("uxinbox_dir", "") or "").strip()}


# ── reading the feed ──

def _read_bytes(src):
    if src.startswith("webcal://"):
        src = "https://" + src[9:]
    if re.match(r"^https?://", src):
        with urllib.request.urlopen(src, timeout=15) as r:
            return r.read()
    return Path(src).expanduser().read_bytes()


def parse(raw):
    """VCALENDAR bytes → (designer, [todo dicts]). Raises ValueError on anything else (e.g. a login page)."""
    import icalendar
    if not raw.lstrip().startswith(b"BEGIN:VCALENDAR"):
        raise ValueError("not an iCalendar file (a login page?)")
    cal = icalendar.Calendar.from_ical(raw)
    designer = str(cal.get("X-UXINBOX-DESIGNER", "") or "")
    out = []
    for c in cal.walk("VTODO"):
        kind = str(c.get("X-UXINBOX-KIND", "item"))
        out.append({
            "uid": str(c.get("UID")),
            "title": str(c.get("SUMMARY", "")).strip() or "(untitled)",
            "url": str(c.get("URL", "") or ""),
            "kind": kind if kind in CATEGORY else "item",
            "completed": str(c.get("STATUS", "")).upper() == "COMPLETED",
            "item_id": str(c.get("X-UXINBOX-ID", "") or ""),
            "suggested": str(c.get("X-UXINBOX-SUGGESTED", "") or ""),
            "study_id": str(c.get("X-UXINBOX-STUDY", "") or ""),
            "finding_id": str(c.get("X-UXINBOX-FINDING", "") or ""),
        })
    return designer, out


def fallback_path(feed, folder):
    """The published file for the same designer: <folder>/docs/feeds/<slug>.ics, slug read from the link."""
    m = re.search(r"/feeds/([a-z0-9-]+)\.ics$", feed)
    if not (m and folder):
        return None
    p = Path(folder).expanduser() / "docs" / "feeds" / f"{m.group(1)}.ics"
    return str(p) if p.exists() else None


def fetch(feed, folder):
    """(designer, todos, where it came from). Live first, then the published file. Raises if neither reads."""
    try:
        d, t = parse(_read_bytes(feed))
        return d, t, feed
    except Exception as live:
        fb = fallback_path(feed, folder)
        if not fb or fb == feed:
            raise
        try:
            d, t = parse(_read_bytes(fb))
        except Exception:
            raise live
        return d, t, fb


# ── sync into tasks.json ──

def _now():
    return datetime.now().astimezone().isoformat()


def sync(db, designer, todos):
    """Apply the feed to a todo.load() db in place. Returns counts. Only ever touches source=="ux-inbox" tasks."""
    mine = {t.get("external_uid"): t for t in db["tasks"] if t.get("source") == SOURCE}
    seen = set()
    n = {"added": 0, "updated": 0, "done": 0, "removed": 0}
    orders = [t.get("order", -t["id"]) for t in db["tasks"] if not t["done"]]
    bottom = max(orders) + 1 if orders else 0
    for f in todos:
        seen.add(f["uid"])
        meta = {k: f[k] for k in ("kind", "item_id", "suggested", "study_id", "finding_id")}
        t = mine.get(f["uid"])
        if t is None:
            if f["completed"]:
                continue          # closed before it ever reached this list
            db["seq"] += 1
            t = {"id": db["seq"], "title": f["title"], "category": CATEGORY[f["kind"]],
                 "created_at": _now(), "done": False, "done_at": None,
                 "order": bottom, "source": SOURCE, "external_uid": f["uid"], "url": f["url"],
                 "designer": designer, **meta}
            bottom += 1
            db["tasks"].append(t)
            mine[f["uid"]] = t
            n["added"] += 1
            continue
        changed = False
        for k, v in (("title", f["title"]), ("url", f["url"]), ("designer", designer or t.get("designer", "")), *meta.items()):
            if t.get(k) != v:
                t[k] = v
                changed = True
        n["updated"] += changed
        # feed says closed → tick it, unless you reopened it here after the feed closed it once
        if f["completed"] and not t["done"] and not t.get("reopened"):
            t["done"], t["done_at"], t["done_by"] = True, _now(), "feed"
            n["done"] += 1
        # NEEDS-ACTION while ticked here: left alone — the feed never reopens a task you ticked
    keep = []
    for t in db["tasks"]:
        if t.get("source") == SOURCE and t.get("external_uid") not in seen and not t["done"]:
            n["removed"] += 1
            continue
        keep.append(t)
    db["tasks"] = keep
    return n


def run(load, save, feed=None, folder=None):
    """Fetch + sync + save. load/save are todo.load/todo.save. Records the outcome in state/uxfeed_status.json."""
    s = settings()
    feed = s["feed"] if feed is None else feed
    folder = s["folder"] if folder is None else folder
    if not feed:
        return None
    try:
        designer, todos, src = fetch(feed, folder)
    except Exception as e:
        st = {"ok": False, "at": _now(), "error": str(e)[:160]}
        _status(st)
        return st
    db = load()                      # read-modify-write kept short: the network part is already done
    n = sync(db, designer, todos)
    save(db)
    st = {"ok": True, "at": _now(), "from": src, "designer": designer, "count": len(todos), **n}
    _status(st)
    return st


def _status(st):
    try:
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps(st, ensure_ascii=False))
    except Exception:
        pass


def last_status():
    try:
        return json.loads(STATUS.read_text())
    except Exception:
        return None


# ── tick-back: one event file in the inbox's shared log ──

NAME = re.compile(r"^\d{8}T\d{6}\.\d{6}Z-ev_[A-Za-z0-9-]+\.json$")


def events_dir(folder):
    d = Path(folder).expanduser() / "data" / "edits" / "events"
    if not d.is_dir():
        raise FileNotFoundError(f"{d} is not a UX Inbox event log")
    return d


def write_event(folder, actor, etype, payload):
    """Write one event exactly as ux-inbox lib/eventlog.mjs does: <ts>.<frac>Z-<id>.json, atomic rename."""
    d = events_dir(folder)
    now = datetime.now(timezone.utc)
    e = {"id": f"ev_{uuid.uuid4()}", "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "actor": actor, "type": etype, "payload": payload}
    name = f"{now.strftime('%Y%m%dT%H%M%S')}.{now.microsecond:06d}Z-{e['id']}.json"
    assert NAME.match(name), name
    tmp = d / f".{name}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, d / name)
    return e


def tick_back(t, flag, folder=None):
    """Called by todo.set_done for a ux-inbox task, before it saves. Mutates t (tick_event_id). Never raises."""
    if t.get("source") != SOURCE:
        return None
    folder = settings()["folder"] if folder is None else folder
    actor = t.get("designer") or ""
    try:
        if not (folder and actor):
            raise ValueError("UX Inbox folder or designer not set")
        if flag:
            t.pop("reopened", None)
            if t.get("tick_event_id"):
                return None
            if t.get("kind") == "finding":
                e = write_event(folder, actor, "finding.resolved",
                                {"studyId": t["study_id"], "findingId": t["finding_id"], "reason": REASON})
            else:
                sug = t.get("suggested") or ""
                e = write_event(folder, actor, "status.confirmed" if sug == "Done" else "status.corrected",
                                {"itemId": t["item_id"], "status": "Done", "suggested": sug, "reason": REASON})
            t["tick_event_id"] = e["id"]
            t.pop("tick_error", None)
            return e
        # unticked
        ev = t.pop("tick_event_id", None)
        if not ev:
            if t.pop("done_by", None) == "feed":
                t["reopened"] = True   # the feed closed it, you reopened it: the feed won't close it again
            return None
        t.pop("done_by", None)
        if t.get("kind") == "finding":
            return write_event(folder, actor, "finding.undone", {"undoes": ev})
        return write_event(folder, actor, "status.undone", {"itemId": t["item_id"], "undoes": ev})
    except Exception as e:
        t["tick_error"] = str(e)[:160]
        return None
