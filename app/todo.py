#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
todo-cat data core — tasks, Obsidian Daily Log / Monthly / Dashboard, AI retro.
Usage: todo.py <done|undone|delete|add|dashboard|retro|eod> …
Data:  <vault>/Tracker/tasks.json   (vault path from config.json)
Retro: <vault>/Tracker/Retros/*.md
"""
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
CONFIG_FILE = ROOT / "config.json"
DEFAULTS = {"vault_path": "~/Documents/todo-cat", "vault_name": "", "lang": "en",
            "import_hour": 8, "eod_hour": 18, "claude_bin": "", "loaf_after": 300}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text()))
    except Exception:
        pass
    return cfg


CFG = load_config()
VAULT = Path(CFG["vault_path"]).expanduser()
DIR = VAULT / "Tracker"
DATA = DIR / "tasks.json"
RETRO_DIR = DIR / "Retros"
CLAUDE_BIN = (CFG["claude_bin"] or shutil.which("claude")
              or str(Path.home() / ".local" / "bin" / "claude"))
OBSIDIAN_VAULT = CFG["vault_name"]   # empty → open files directly instead of obsidian://

CATS = {
    "Meeting":           ("#56789A", "회의"),
    "Design":            ("#B65C7E", "디자인"),
    "Strategic":         ("#8A6FB8", "전략"),
    "Research":          ("#3F8F7A", "리서치"),
    "Personal Growth":   ("#C99039", "성장"),
    "Personal Interest": ("#7A8450", "관심사"),
    "Personal":          ("#C05B4D", "개인"),
}


def now():
    return datetime.now().astimezone()


def load():
    if not DATA.exists():
        return {"seq": 0, "tasks": []}
    try:
        return json.loads(DATA.read_text())
    except Exception:
        return {"seq": 0, "tasks": []}


def save(db):
    DIR.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=1))


def add(title, cat, minutes=None):
    db = load()
    db["seq"] += 1
    task = {"id": db["seq"], "title": title.strip(),
            "category": cat, "created_at": now().isoformat(),
            "done": False, "done_at": None}
    if minutes:
        task["minutes"] = int(minutes)
    db["tasks"].append(task)
    save(db)


def find(db, tid):
    for t in db["tasks"]:
        if t["id"] == int(tid):
            return t
    return None


def set_done(tid, flag):
    db = load()
    t = find(db, tid)
    if t:
        t["done"] = flag
        t["done_at"] = now().isoformat() if flag else None
        save(db)


def delete(tid):
    db = load()
    db["tasks"] = [t for t in db["tasks"] if t["id"] != int(tid)]
    save(db)


def set_title(tid, title):
    db = load()
    t = find(db, tid)
    if t and title.strip():
        t["title"] = title.strip()
        save(db)


def set_category(tid, cat):
    db = load()
    x = find(db, tid)
    if x and cat in CATS:
        x["category"] = cat
        save(db)


def d_of(iso):
    return datetime.fromisoformat(iso).astimezone().date()


def done_on(t, day):
    return t["done"] and t["done_at"] and d_of(t["done_at"]) == day


def done_between(tasks, a, b):
    return [t for t in tasks
            if t["done"] and t["done_at"] and a <= d_of(t["done_at"]) <= b]


def today_stats(db):
    today = date.today()
    open_t = [t for t in db["tasks"] if not t["done"]]
    done_t = [t for t in db["tasks"] if done_on(t, today)]
    return open_t, done_t, len(open_t) + len(done_t)


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def osa(script):
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True)
    return r.stdout.strip()


def notify(msg, title="Claude Todo"):
    osa(f'display notification "{esc(msg)}" with title "{esc(title)}"')


WD_KO = ["월", "화", "수", "목", "금", "토", "일"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def dashboard():
    """Refresh Daily Log + Dashboard, then open the Dashboard in Obsidian."""
    write_daily_log()
    open_note(DIR / "Dashboard.md", "Tracker/Dashboard")


def open_note(path, vault_rel):
    """Open a note in Obsidian when a vault name is configured, otherwise with the default app."""
    if OBSIDIAN_VAULT:
        fp = urllib.parse.quote(vault_rel)
        subprocess.run(["open", f"obsidian://open?vault={OBSIDIAN_VAULT}&file={fp}"])
    else:
        subprocess.run(["open", str(path)])


def md_esc(x):
    return x.replace("|", "\\|")


def retro_summary(day):
    f = RETRO_DIR / f"{day.isoformat()}-Daily.md"
    if not f.exists():
        return None, False
    txt = f.read_text()
    m = re.search(r"##\s*(?:요약|Summary)\s*\n+(.+?)(?:\n\n|\n#)", txt, re.S)
    line = " ".join(m.group(1).split()) if m else ""
    return line[:200], True


def write_monthly_page(day):
    ym = day.strftime("%Y-%m")
    logdir = DIR / "Log"
    out = DIR / "Monthly"
    out.mkdir(parents=True, exist_ok=True)
    days = sorted(x.stem for x in logdir.glob(f"{ym}-??.md"))
    retros = {x.stem for x in RETRO_DIR.glob(f"{ym}-*.md")} \
        if RETRO_DIR.exists() else set()
    L = ["---", "type: monthly-log", f"month: {ym}", "---", "",
         f"# {ym} Monthly Review", "",
         "![[Tracker/assets/heatmap.svg]]", ""]
    for d in days:
        dt = datetime.fromisoformat(d).date()
        L += [f"## {dt.month}/{dt.day} ({WD_KO[dt.weekday()]})", "",
              f"![[Tracker/Log/{d}]]", ""]
    others = sorted(x for x in retros if not x.endswith("-Daily"))
    if others:
        L += ["## Period retros (Weekly · Monthly · Quarterly)", ""]
        for o in others:
            L.append(f"![[Tracker/Retros/{o}]]")
        L.append("")
    (out / f"{ym}.md").write_text("\n".join(L))


def fmt_min(m):
    m = int(m or 0)
    if m <= 0:
        return ""
    h, r = divmod(m, 60)
    if h and r:
        return f"~{h}h {r}m"
    return f"~{h}h" if h else f"~{r}m"


def pomo_day(day):
    try:
        pl = json.loads((STATE / "pomo_log.json").read_text()).get(day.isoformat(), {})
        if isinstance(pl, int):
            pl = {"count": pl, "min": pl * 25}
        return int(pl.get("count", 0)), int(pl.get("min", 0))
    except Exception:
        return 0, 0


def retro_section(day, names):
    """Extract one section body from a retro file (several heading candidates)."""
    f = RETRO_DIR / f"{day.isoformat()}-Daily.md"
    if not f.exists():
        return None
    txt = f.read_text()
    pat = r"##\s*(?:" + "|".join(names) + r")[^\n]*\n+(.+?)(?=\n##|\Z)"
    m = re.search(pat, txt, re.S)
    return m.group(1).strip() if m else None


def write_heatmap_svg(weeks=16):
    """GitHub-style heatmap of completions → Tracker/assets/heatmap.svg"""
    db = load()
    counts = {}
    for x in db["tasks"]:
        if x["done"] and x["done_at"]:
            d = d_of(x["done_at"]).isoformat()
            counts[d] = counts.get(d, 0) + 1
    today = date.today()
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))  # weeks start on Monday
    cell, gap, left, top = 13, 3, 30, 22
    W = left + weeks * (cell + gap) + 6
    H = top + 7 * (cell + gap) + 6
    cols = ["#ECEEE7", "#BFD9CF", "#84B5A4", "#4F907B", "#2E6E5E"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="Inter,Pretendard,-apple-system,sans-serif" '
           f'font-size="10" fill="#767C70">']
    for i, lab in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
        out.append(f'<text x="0" y="{top + i*(cell+gap) + 10}">{lab}</text>')
    last_month = None
    for w in range(weeks):
        wk = start + timedelta(weeks=w)
        if wk.month != last_month:
            out.append(f'<text x="{left + w*(cell+gap)}" y="12">{MONTHS[wk.month - 1]}</text>')
            last_month = wk.month
        for r in range(7):
            d = wk + timedelta(days=r)
            if d > today:
                continue
            n = counts.get(d.isoformat(), 0)
            c = cols[min(n, 4)]
            x, y = left + w * (cell + gap), top + r * (cell + gap)
            stroke = ' stroke="#2E6E5E" stroke-width="1.5"' if d == today else ""
            out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" '
                       f'fill="{c}"{stroke}><title>{d.isoformat()} · {n} done</title></rect>')
    out.append("</svg>")
    a = DIR / "assets"
    a.mkdir(parents=True, exist_ok=True)
    (a / "heatmap.svg").write_text("\n".join(out))


def bar(v, mx, width=12):
    n = 0 if mx <= 0 else round(v / mx * width)
    return "▰" * n + "▱" * (width - n)


def write_dashboard():
    """Tracker/Dashboard.md — 30-day activity · categories · heatmap · timeline"""
    write_heatmap_svg()
    db = load()
    today = date.today()
    since = today - timedelta(days=29)
    done30 = done_between(db["tasks"], since, today)
    meet_min = sum(int(x.get("minutes") or 0) for x in done30)
    pomo_cnt = pomo_min = 0
    for i in range(30):
        c, m = pomo_day(since + timedelta(days=i))
        pomo_cnt += c; pomo_min += m
    hours = (meet_min + pomo_min) / 60
    active_days = len({d_of(x["done_at"]) for x in done30})
    cat_cnt = {}
    for x in done30:
        cat_cnt[x["category"]] = cat_cnt.get(x["category"], 0) + 1
    mx = max(cat_cnt.values()) if cat_cnt else 0
    L = ["---", "type: dashboard", f"updated: {now().isoformat()}", "---", "",
         "# Dashboard", "",
         f"> Last 30 days · 최근 30일 · {since.month}/{since.day} – {today.month}/{today.day}", "",
         "## ACTIVITY · 활동", "",
         "| | | | |", "|:--|:--|:--|:--|",
         f"| **{len(done30)}**<br>Actions · 완료 | **{hours:.0f}h**<br>Hours worked · 근무 "
         f"| **{active_days}**<br>Active days · 활동일 | **{pomo_cnt}** 🍅<br>{pomo_min} min focus · 집중 |", "",
         "## CATEGORIES · 카테고리", "",
         "| # | Category · 카테고리 | | Done |", "|:--|:--|:--|--:|"]
    for i, (cat, n) in enumerate(sorted(cat_cnt.items(), key=lambda kv: -kv[1]), 1):
        lab = CATS.get(cat, ("", cat))[1]
        L.append(f"| {i} | {lab} ({cat}) | `{bar(n, mx)}` | {n} |")
    if not cat_cnt:
        L.append("| – | No completions yet | | |")
    L += ["", "## HEATMAP · 히트맵", "", "![[Tracker/assets/heatmap.svg]]", "",
          "## TIMELINE · 타임라인", ""]
    labels = {0: "Today", 1: "Yesterday"}
    for i in range(7):
        d = today - timedelta(days=i)
        f = DIR / "Log" / f"{d.isoformat()}.md"
        name = labels.get(i, ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][d.weekday()])
        sub = f"{d.day} {MONTHS[d.month-1]}"
        if f.exists():
            L.append(f"- [[Tracker/Log/{d.isoformat()}|{name}]] · {sub}")
        else:
            L.append(f"- {name} · {sub} _(no log)_")
    L += ["", f"[[Tracker/Monthly/{today.strftime('%Y-%m')}|→ Full month]]", ""]
    (DIR / "Dashboard.md").write_text("\n".join(L))


def write_daily_log(day=None):
    """Daily Log — WORK SESSIONS / FOCUS / UNFINISHED / NEXT STEPS"""
    day = day or date.today()
    db = load()
    done = [x for x in db["tasks"] if done_on(x, day)]
    open_t = ([x for x in db["tasks"] if not x["done"]]
              if day == date.today() else [])
    total = len(done) + len(open_t)
    pct = round(len(done) / total * 100) if total else 0
    pc, pm = pomo_day(day)
    meet_min = sum(int(x.get("minutes") or 0) for x in done)

    def hm(iso):
        return datetime.fromisoformat(iso).astimezone().strftime("%H:%M")

    L = ["---", "type: daily-log", f"date: {day.isoformat()}",
         f"done: {len(done)}", f"total: {total}",
         f"pomodoros: {pc}", f"focus_min: {pm}", f"meeting_min: {meet_min}",
         "---", "",
         f"# {day.isoformat()} ({WD_KO[day.weekday()]}) Daily Log", "",
         "## WORK SESSIONS · 작업 세션", ""]
    if not done:
        L.append("_완료된 항목 없음 / Nothing completed_")
    for x in sorted(done, key=lambda t: t["done_at"]):
        lab = CATS.get(x["category"], ("", x["category"]))[1]
        title = x["title"]
        m = re.match(r"^(\d{1,2}:\d{2}|종일|All day)\s+(.*)$", title)
        if m:
            title = m.group(2)
        dur = fmt_min(x.get("minutes"))
        meta = f" ({dur})" if dur else ""
        L.append(f"- **{md_esc(title)}**{meta}: {lab} ({x['category']}) · done {hm(x['done_at'])}")
    L += ["", "## FOCUS · 집중", ""]
    summ = retro_section(day, ["요약"])
    summ_en = retro_section(day, ["Summary"])
    if summ or summ_en:
        if summ:
            L.append(summ)
        if summ_en:
            L += ["", summ_en]
    else:
        ko = [f"완료 {len(done)}/{total} ({pct}%)"]
        en = [f"Completed {len(done)}/{total} ({pct}%)"]
        if meet_min:
            ko.append(f"회의 {fmt_min(meet_min).lstrip('~')}")
            en.append(f"meetings {fmt_min(meet_min).lstrip('~')}")
        if pc:
            ko.append(f"포모도로 {pc}회 · {pm}분 집중")
            en.append(f"{pc} pomodoros · {pm} min focus")
        L.append(" · ".join(ko) + ".")
        L.append("")
        L.append(" · ".join(en) + ".")
    L += ["", "## UNFINISHED · 미완료", ""]
    if open_t:
        for x in open_t:
            lab = CATS.get(x["category"], ("", x["category"]))[1]
            L.append(f"- {md_esc(x['title'])} · {lab} ({x['category']})")
    else:
        L.append("_열린 항목 없음 / Nothing open_")
    L += ["", "## NEXT STEPS · 다음 단계", ""]
    nxt = retro_section(day, ["다음 기간 제안"])
    nxt_en = retro_section(day, ["Suggestions for next period"])
    if nxt or nxt_en:
        if nxt:
            L.append(nxt)
        if nxt_en:
            L += ["", nxt_en]
    else:
        for i, x in enumerate(open_t[:3], 1):
            L.append(f"{i}. {md_esc(x['title'])}")
        if not open_t:
            L.append("_Generate a retro to fill in suggestions_")
    rf = RETRO_DIR / f"{day.isoformat()}-Daily.md"
    if rf.exists():
        L += ["", "## RETRO · 회고", "", f"![[Tracker/Retros/{day.isoformat()}-Daily]]"]
    out = DIR / "Log"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{day.isoformat()}.md").write_text("\n".join(L) + "\n")
    write_monthly_page(day)
    try:
        write_dashboard()
    except Exception:
        pass


def period_range(kind):
    t = date.today()
    if kind == "daily":
        return t, t, "Daily"
    if kind == "weekly":
        return t - timedelta(days=t.weekday()), t, "Weekly"
    if kind == "monthly":
        return t.replace(day=1), t, "Monthly"
    return date(t.year, 3 * ((t.month - 1) // 3) + 1, 1), t, "Quarterly"


def retro(kind):
    a, b, label = period_range(kind)
    db = load()
    done = done_between(db["tasks"], a, b)
    if not done:
        notify("이 기간에 완료된 항목이 없습니다. / Nothing completed in this period.",
               f"{label} retro")
        return
    lines = []
    for x in sorted(done, key=lambda t: t["done_at"]):
        dur = fmt_min(x.get("minutes"))
        lines.append(f'- [{x["category"]}] {x["title"]}'
                     f'{" (" + dur + ")" if dur else ""} ({d_of(x["done_at"])})')
    pc = pm = 0
    d = a
    while d <= b:
        c, m = pomo_day(d); pc += c; pm += m; d += timedelta(days=1)
    prompt = (
        f"Below is the list of tasks I completed between {a} and {b}"
        f"{f', plus {pc} pomodoro sessions ({pm} min of focus)' if pc else ''}. "
        "Write a personal retrospective DRAFT twice: first in Korean, then in English, "
        "separated by a line containing only '---'.\n"
        "Each version uses exactly these sections (keep the headings in that language):\n"
        "Korean: ## 요약 (2~3문장) / ## Wins (핵심 성과 3~5개) / ## 패턴 (1~2개) / "
        "## Highlight 후보 (팀 공유용 1개) / ## 다음 기간 제안 (1~2개)\n"
        "English: ## Summary (2-3 sentences) / ## Wins (3-5 items) / ## Patterns (1-2) / "
        "## Highlight candidate (1 item) / ## Suggestions for next period (1-2)\n"
        "Each version under 250 words, plain tone, no emoji, no hype. Task list:\n"
        + "\n".join(lines))
    notify("Claude is drafting the retro… (10–60 s)", f"{label} retro")
    try:
        r = subprocess.run([CLAUDE_BIN, "-p", prompt],
                           capture_output=True, text=True, timeout=240)
        draft = r.stdout.strip() or ("_Draft generation failed_\n\n```\n"
                                     + r.stderr.strip()[-400:] + "\n```")
    except Exception as e:
        draft = f"_Draft generation failed: {e}_"
    RETRO_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{b.isoformat()}-{label}"
    path = RETRO_DIR / f"{name}.md"
    # preserve the user's notes section from an existing file
    notes = "- \n"
    if path.exists():
        m = re.search(r"## ✍️ 내 노트[^\n]*\n(.*?)(?=\n## |\Z)", path.read_text(), re.S)
        if m and m.group(1).strip() and m.group(1).strip() != "-":
            notes = m.group(1).strip() + "\n"
    md = (f"---\ntype: {label.lower()}-retro\nperiod: {a} ~ {b}\n"
          f"generated: {now().isoformat()}\ndone_count: {len(done)}\n"
          f"pomodoros: {pc}\nfocus_min: {pm}\nlang: ko, en\n---\n\n"
          f"# {label} Retro · {b.isoformat()}\n\n{draft}\n\n"
          f"## ✍️ 내 노트 / My notes\n\n{notes}\n## 완료 목록 / Completed\n\n"
          + "\n".join(lines) + "\n")
    path.write_text(md)
    notify("Retro saved / 회고 저장 완료", f"{label} retro")
    return path


def run_eod():
    """18:00 end-of-day: generate retro → refresh Daily Log/Dashboard (does not open Obsidian)."""
    try:
        retro("daily")
    except Exception:
        pass
    write_daily_log()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd in ("", "-h", "--help"):
        print(__doc__.strip()); return
    if cmd == "eod": run_eod(); return
    if cmd == "done": set_done(sys.argv[2], True)
    elif cmd == "undone": set_done(sys.argv[2], False)
    elif cmd == "delete": delete(sys.argv[2])
    elif cmd == "add": add(" ".join(sys.argv[3:]), sys.argv[2])
    elif cmd == "dashboard": dashboard()
    elif cmd == "retro": retro(sys.argv[2])


if __name__ == "__main__":
    main()
