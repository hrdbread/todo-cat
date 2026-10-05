#!/usr/bin/env python3
"""UX Inbox feed: parse, sync rules, live→file fallback and the tick-back event files.
Plain python3 (no pyobjc): `python3 tests/test_uxfeed.py`. Works in a temp dir only — never touches
tasks.json, settings or the inbox's real event log. Exit 0 = all passed."""
import json, re, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import uxfeed

TMP = Path(tempfile.mkdtemp(prefix="todocat-uxfeed-"))
uxfeed.STATUS = TMP / "status.json"


def feed(*todos, designer="Stefan Twerdochlib"):
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//EN", f"X-UXINBOX-DESIGNER:{designer}"]
    for uid, title, status, kind, extra in todos:
        L += ["BEGIN:VTODO", f"UID:{uid}", "DTSTAMP:20261005T080000Z", f"SUMMARY:{title}", f"STATUS:{status}",
              f"URL:https://example.test/#{uid}", f"X-UXINBOX-KIND:{kind}", *extra, "END:VTODO"]
    L.append("END:VCALENDAR")
    return ("\r\n".join(L) + "\r\n").encode()


ITEM = lambda uid, title="Item", status="NEEDS-ACTION", sug="In design": (uid, title, status, "item", [f"X-UXINBOX-ID:{uid}", f"X-UXINBOX-SUGGESTED:{sug}"])
FIND = lambda uid, status="NEEDS-ACTION": (uid, "Finding", status, "finding", ["X-UXINBOX-STUDY:ut-1", "X-UXINBOX-FINDING:3"])


def db_with(*tasks):
    return {"seq": 100, "tasks": [{"id": i + 1, "title": t, "category": "Personal", "done": False, "done_at": None, "order": i} for i, t in enumerate(tasks)]}


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        check.failed = True
check.failed = False

# ── parse ──
d, todos = uxfeed.parse(feed(ITEM("a"), FIND("f")))
check("parse: designer + both kinds", d == "Stefan Twerdochlib" and [t["kind"] for t in todos] == ["item", "finding"])
try:
    uxfeed.parse(b"<!DOCTYPE html><html>Sign in to GitHub</html>")
    check("parse: a login page is refused", False)
except ValueError:
    check("parse: a login page is refused", True)

# ── sync rules ──
db = db_with("mine")
n = uxfeed.sync(db, d, todos)
check("new UIDs are added, Design / Research", n["added"] == 2 and sorted(t["category"] for t in db["tasks"][1:]) == ["Design", "Research"])
check("your own task is untouched", db["tasks"][0] == {"id": 1, "title": "mine", "category": "Personal", "done": False, "done_at": None, "order": 0})
check("added below your own tasks", all(t["order"] > 0 for t in db["tasks"][1:]))
n = uxfeed.sync(db, d, todos)
check("re-run: no duplicates", len(db["tasks"]) == 3 and n["added"] == 0)
uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("a", "Renamed"), FIND("f")))[1])
check("changed title updates", next(t for t in db["tasks"] if t.get("external_uid") == "a")["title"] == "Renamed")
uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("a", "Renamed", "COMPLETED"), FIND("f")))[1])
a = next(t for t in db["tasks"] if t.get("external_uid") == "a")
check("feed COMPLETED ticks it (as the feed)", a["done"] and a["done_by"] == "feed")
uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("a", "Renamed", "NEEDS-ACTION"), FIND("f")))[1])
check("the feed never reopens a ticked task", a["done"])
uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("a", "Renamed")))[1])
check("UID gone + open → removed; done ones and your own stay", [t.get("external_uid") for t in db["tasks"]] == [None, "a"])
n = uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("z", status="COMPLETED")))[1])
check("a COMPLETED UID never seen is not added", n["added"] == 0 and not any(t.get("external_uid") == "z" for t in db["tasks"]))

# ── fetch: live first, then the published file; failures never touch tasks ──
inbox = TMP / "ux-inbox"; (inbox / "docs" / "feeds").mkdir(parents=True); (inbox / "data" / "edits" / "events").mkdir(parents=True)
(inbox / "docs" / "feeds" / "stefan-twerdochlib.ics").write_bytes(feed(ITEM("from-file")))
_, t2, src = uxfeed.fetch("http://127.0.0.1:9/feeds/stefan-twerdochlib.ics", str(inbox))
check("live link down → published file", src.endswith("docs/feeds/stefan-twerdochlib.ics") and t2[0]["uid"] == "from-file")
store = {"db": db_with("keep me")}
st = uxfeed.run(lambda: store["db"], lambda x: store.update(db=x), feed="http://127.0.0.1:9/feeds/nobody.ics", folder=str(inbox))
check("nothing readable → error recorded, tasks untouched", st["ok"] is False and [t["title"] for t in store["db"]["tasks"]] == ["keep me"])

# ── tick-back ──
ev_dir = inbox / "data" / "edits" / "events"
NAME = re.compile(r"^\d{8}T\d{6}\.\d{6}Z-ev_[A-Za-z0-9-]+\.json$")
db = db_with(); uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("it-1", sug="In review"), FIND("f-1")))[1])
item = next(t for t in db["tasks"] if t["kind"] == "item"); fnd = next(t for t in db["tasks"] if t["kind"] == "finding")
e = uxfeed.tick_back(item, True, folder=str(inbox))
files = sorted(p.name for p in ev_dir.iterdir())
check("tick item → one event file, named like the inbox's", len(files) == 1 and NAME.match(files[0]))
stored = json.loads((ev_dir / files[0]).read_text())
check("status.corrected to Done, with the suggestion and reason", stored["type"] == "status.corrected" and stored["payload"] == {"itemId": "it-1", "status": "Done", "suggested": "In review", "reason": uxfeed.REASON} and stored["actor"] == "Stefan Twerdochlib" and re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", stored["ts"]))
check("the task remembers the event", item["tick_event_id"] == e["id"])
u = uxfeed.tick_back(item, False, folder=str(inbox))
check("untick → status.undone naming it", u["type"] == "status.undone" and u["payload"] == {"itemId": "it-1", "undoes": e["id"]} and "tick_event_id" not in item)
fe = uxfeed.tick_back(fnd, True, folder=str(inbox))
check("tick finding → finding.resolved", fe["type"] == "finding.resolved" and fe["payload"]["studyId"] == "ut-1" and fe["payload"]["findingId"] == "3")
fu = uxfeed.tick_back(fnd, False, folder=str(inbox))
check("untick finding → finding.undone", fu["type"] == "finding.undone" and fu["payload"] == {"undoes": fe["id"]})
check("no temp files left", all(NAME.match(p.name) for p in ev_dir.iterdir()) and len(list(ev_dir.iterdir())) == 4)
before = len(list(ev_dir.iterdir()))
fed = {"source": "ux-inbox", "kind": "item", "item_id": "x", "designer": "S", "done": True, "done_by": "feed"}
check("untick a feed-ticked task → nothing written, feed won't re-tick", uxfeed.tick_back(fed, False, folder=str(inbox)) is None and fed.get("reopened") and len(list(ev_dir.iterdir())) == before)
bad = {"source": "ux-inbox", "kind": "item", "item_id": "x", "designer": "S"}
check("wrong folder → no crash, error kept on the task", uxfeed.tick_back(bad, True, folder=str(TMP / "nope")) is None and "tick_error" in bad)
check("not a feed task → ignored", uxfeed.tick_back({"title": "mine"}, True, folder=str(inbox)) is None)

# ── DoD checks as sub-tasks ──
CHK = lambda uid, parent, title="Check", status="NEEDS-ACTION", group="Validated": (uid, title, status, "check", [f"RELATED-TO;RELTYPE=PARENT:{parent}", f"X-UXINBOX-ID:{parent[5:-9]}", f"X-UXINBOX-CHECK:{uid[6:]}", f"X-UXINBOX-GROUP:{group}"])
db = db_with()
uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("item-p@ux-inbox"), CHK("check-c1", "item-p@ux-inbox"), CHK("check-c2", "item-p@ux-inbox", group="Design complete")))[1])
p = next(t for t in db["tasks"] if t.get("external_uid") == "item-p@ux-inbox")
check("checks become sub-tasks of their item, not tasks", len(db["tasks"]) == 1 and [x["uid"] for x in p["subtasks"]] == ["check-c1", "check-c2"] and p["subtasks"][1]["group"] == "Design complete")
uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("item-p@ux-inbox"), CHK("check-c1", "item-p@ux-inbox"), CHK("check-c2", "item-p@ux-inbox", group="Design complete")))[1])
check("re-run: no duplicate sub-tasks", len(p["subtasks"]) == 2)
uxfeed.sync(db, d, uxfeed.parse(feed(ITEM("item-p@ux-inbox"), CHK("check-c1", "item-p@ux-inbox", status="COMPLETED")))[1])
check("feed COMPLETED ticks a sub-task; gone + open drops it", [(x["uid"], x["done"]) for x in p["subtasks"]] == [("check-c1", True)])
p["subtasks"][0].update(done=False, done_by=None)
e = uxfeed.tick_back_check(p, p["subtasks"][0], True, folder=str(inbox))
check("tick a sub-task → check.marked with the item and criterion", e["type"] == "check.marked" and e["payload"] == {"itemId": p["item_id"], "criterionId": "c1", "reason": uxfeed.REASON} and NAME.match(next(f.name for f in ev_dir.iterdir() if e["id"] in f.name)))
u = uxfeed.tick_back_check(p, p["subtasks"][0], False, folder=str(inbox))
check("untick → check.undone naming it", u["type"] == "check.undone" and u["payload"] == {"undoes": e["id"]})

print(f"\n{TMP}")
sys.exit(1 if check.failed else 0)
