#!/usr/bin/env python3
"""
RivalRadar — local competitor intelligence & website-change monitor.

Track competitors' websites: new/removed pages, content & SEO changes, price/stock
watches, and the technologies they use — with a change timeline, outbound webhooks
and optional email alerts. Everything runs on this machine.

    python server.py   ->   http://127.0.0.1:5160
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

from flask import Flask, Response, abort, jsonify, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import store      # noqa: E402
import monitor    # noqa: E402
import notify     # noqa: E402

try:
    import app_paths
    _STATIC = app_paths.static_dir()
    store.set_db_path(os.path.join(app_paths.data_dir(), "rivalradar.db"))
except Exception:
    app_paths = None
    _STATIC = os.path.join(HERE, "static")
if os.environ.get("RR_DB"):
    store.set_db_path(os.environ["RR_DB"])

VERSION = "1.0.0"
DEFAULT_PORT = 5160
app = Flask(__name__, static_folder=_STATIC)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
LOCAL_URL = f"http://127.0.0.1:{DEFAULT_PORT}"

# ---- scan jobs ---- #
JOBS: dict[int, dict] = {}
_JOBS_LOCK = threading.Lock()
MAX_CONCURRENT = 3
_SEM = threading.BoundedSemaphore(MAX_CONCURRENT)


# --------------------------- helpers ---------------------------------------- #
def _s(name, default=""):
    v = request.form.get(name)
    if v is None:
        v = request.args.get(name)
    if v is None and request.is_json:
        try:
            v = request.get_json(silent=True).get(name)
        except Exception:
            v = None
    return (str(v).strip() if v is not None else default)


def _int(name, default=0):
    try:
        return int(float(_s(name, str(default))))
    except (TypeError, ValueError):
        return default


def _ids(name):
    out = []
    vals = request.form.getlist(name) + request.args.getlist(name)
    for v in vals:
        for x in str(v).split(","):
            x = x.strip()
            if x.lstrip("-").isdigit():
                out.append(int(x))
    return out


# --------------------------- static ----------------------------------------- #
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/favicon.ico")
def favicon():
    base = app_paths.resource_dir() if app_paths else HERE
    p = os.path.join(base, "rivalradar.ico")
    if os.path.isfile(p):
        return send_from_directory(base, "rivalradar.ico", mimetype="image/x-icon")
    abort(404)


@app.route("/api/ping")
def api_ping():
    return jsonify({"app": "rivalradar", "version": VERSION})


@app.route("/api/state")
def api_state():
    st = store.get_settings()
    return jsonify({
        "version": VERSION,
        "competitors": store.competitors(),
        "webhooks": len(store.webhooks(active_only=True)),
        "settings": {k: st.get(k) for k in (
            "scan_interval_min", "respect_robots", "request_timeout", "max_pages_per_site",
            "request_delay_ms", "keep_snapshots", "user_agent", "smtp_host", "smtp_port",
            "smtp_security", "smtp_user", "smtp_from", "alert_email")},
        "jobs": _jobs_snapshot(),
    })


@app.route("/api/dashboard")
def api_dashboard():
    return jsonify(store.dashboard())


# --------------------------- competitors ------------------------------------ #
@app.route("/api/competitors")
def api_competitors():
    return jsonify({"competitors": store.competitors()})


@app.route("/api/competitors", methods=["POST"])
def api_add_competitor():
    domain, base = monitor.normalize_domain(_s("domain"))
    if not domain:
        return jsonify({"ok": False, "error": "Enter a website address."}), 400
    if store.find_competitor_by_domain(domain):
        return jsonify({"ok": False, "error": "You're already tracking that domain."}), 400
    name = _s("name") or domain
    cid = store.add_competitor(name, domain, base, notes=_s("notes"),
                               interval_min=_int("interval_min", 0))
    if _s("scan_now", "1") != "0":
        _start_scan(cid)
    return jsonify({"ok": True, "id": cid})


@app.route("/api/competitors/<int:cid>", methods=["POST"])
def api_update_competitor(cid):
    kw = {}
    for f in ("name", "notes"):
        if request.form.get(f) is not None or (request.is_json and f in (request.get_json(silent=True) or {})):
            kw[f] = _s(f)
    if _s("interval_min") != "":
        kw["interval_min"] = _int("interval_min")
    if _s("active") != "":
        kw["active"] = 1 if _s("active") == "1" else 0
    store.update_competitor(cid, **kw)
    return jsonify({"ok": True})


@app.route("/api/competitors/<int:cid>/delete", methods=["POST"])
def api_delete_competitor(cid):
    store.delete_competitor(cid)
    return jsonify({"ok": True})


@app.route("/api/competitors/<int:cid>")
def api_competitor_detail(cid):
    comp = store.get_competitor(cid)
    if not comp:
        return jsonify({"ok": False, "error": "Not found"}), 404
    comp["pages"] = store.pages_of(cid)
    comp["tech"] = store.tech_of(cid)
    comp["changes"] = store.changes(competitor_id=cid, per=40)["rows"]
    comp["scans"] = store.recent_scans(cid, 20)
    comp["intel"] = store.get_intel(cid)
    comp["products"] = store.products_of(cid)
    comp["feed"] = store.feed_items(cid, 40)
    comp["keywords"] = store.keywords(cid)
    with _JOBS_LOCK:
        comp["job"] = JOBS.get(cid)
    return jsonify(comp)


@app.route("/api/products/<int:pid>/history")
def api_product_history(pid):
    return jsonify({"history": store.price_history(pid)})


@app.route("/api/competitors/<int:cid>/keywords", methods=["POST"])
def api_add_keyword(cid):
    w = _s("word")
    if not w:
        return jsonify({"ok": False, "error": "Enter a keyword."}), 400
    store.add_keyword(w, competitor_id=cid)
    return jsonify({"ok": True})


@app.route("/api/keywords/<int:kid>/delete", methods=["POST"])
def api_delete_keyword(kid):
    store.delete_keyword(kid)
    return jsonify({"ok": True})


@app.route("/api/compare")
def api_compare():
    ids = _ids("ids")
    out = []
    for cid in ids:
        comp = store.get_competitor(cid)
        if not comp:
            continue
        intel_d = store.get_intel(cid)
        prods = [p for p in store.products_of(cid) if p["present"] and p["price"]]
        prices = [p["price"] for p in prods]
        out.append({
            "id": cid, "name": comp["name"], "color": comp["color"], "domain": comp["domain"],
            "pages": len([p for p in store.pages_of(cid) if not p["gone"]]),
            "tech": [t["name"] for t in store.tech_of(cid) if t["present"]],
            "products": len(prods),
            "price_min": min(prices) if prices else None, "price_max": max(prices) if prices else None,
            "price_avg": round(sum(prices) / len(prices), 2) if prices else None,
            "promo": (intel_d.get("promo") or {}).get("active", False),
            "security": (intel_d.get("security") or {}).get("grade", "—"),
            "ssl_days": (intel_d.get("ssl") or {}).get("days_left"),
            "domain_age": (intel_d.get("domain") or {}).get("age_days"),
            "socials": list((intel_d.get("contacts") or {}).get("socials", {}).keys()),
            "changes7": comp.get("last_change", 0) and store.changes(competitor_id=cid, per=1)["total"],
        })
    return jsonify({"competitors": out})


@app.route("/feed.xml")
@app.route("/api/rss")
def api_rss():
    import html as _h
    rows = store.changes(per=50)["rows"]
    base = request.host_url.rstrip("/")
    items = []
    for r in rows:
        title = _h.escape(f"[{r['comp_name']}] {r['summary']}")
        link = _h.escape(r["url"] or base)
        guid = f"rivalradar-{r['id']}"
        date = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(r["ts"]))
        items.append(f"<item><title>{title}</title><link>{link}</link>"
                     f"<guid isPermaLink=\"false\">{guid}</guid><pubDate>{date}</pubDate>"
                     f"<description>{_h.escape(r.get('detail') or r['summary'])}</description></item>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
           '<title>RivalRadar — competitor changes</title>'
           f'<link>{base}</link><description>Competitor website changes</description>'
           + "".join(items) + '</channel></rss>')
    return Response(xml, mimetype="application/rss+xml")


# --------------------------- scanning --------------------------------------- #
def _run_scan(cid, discover=True):
    with _SEM:
        with _JOBS_LOCK:
            JOBS[cid] = {"status": "running", "started": time.time(),
                         "pages_checked": 0, "changes": 0}
        res = monitor.scan_competitor(cid, discover=discover)
        with _JOBS_LOCK:
            JOBS[cid] = {"status": "done" if res.get("ok") else "error",
                         "finished": time.time(), "pages_checked": res.get("pages_checked", 0),
                         "changes": res.get("changes", 0), "error": res.get("error")}


def _start_scan(cid, discover=True):
    with _JOBS_LOCK:
        j = JOBS.get(cid)
        if j and j.get("status") == "running":
            return False
    threading.Thread(target=_run_scan, args=(cid, discover), daemon=True).start()
    return True


def _jobs_snapshot():
    with _JOBS_LOCK:
        return {str(k): v for k, v in JOBS.items() if v.get("status") == "running"}


@app.route("/api/competitors/<int:cid>/scan", methods=["POST"])
def api_scan(cid):
    if not store.get_competitor(cid):
        return jsonify({"ok": False, "error": "Not found"}), 404
    started = _start_scan(cid, discover=_s("discover", "1") != "0")
    return jsonify({"ok": True, "started": started})


@app.route("/api/scan-all", methods=["POST"])
def api_scan_all():
    n = 0
    for comp in store.competitors(active_only=True):
        if _start_scan(comp["id"]):
            n += 1
    return jsonify({"ok": True, "started": n})


@app.route("/api/jobs")
def api_jobs():
    return jsonify(_jobs_snapshot())


# --------------------------- pages ------------------------------------------ #
@app.route("/api/competitors/<int:cid>/pages", methods=["POST"])
def api_add_page(cid):
    comp = store.get_competitor(cid)
    if not comp:
        return jsonify({"ok": False, "error": "Not found"}), 404
    raw = _s("url")
    if not raw:
        return jsonify({"ok": False, "error": "Enter a page URL."}), 400
    if "://" not in raw:
        raw = comp["base_url"].rstrip("/") + "/" + raw.lstrip("/")
    url = monitor.clean_url(raw)
    if not monitor.same_site(url, comp["domain"]):
        return jsonify({"ok": False, "error": "That URL isn't on this competitor's domain."}), 400
    pid = store.add_page(cid, url, kind=_s("kind", "watch") or "watch",
                         selector=_s("selector"), label=_s("label"))
    return jsonify({"ok": True, "id": pid})


@app.route("/api/pages/<int:pid>/delete", methods=["POST"])
def api_delete_page(pid):
    store.delete_page(pid)
    return jsonify({"ok": True})


@app.route("/api/pages/<int:pid>/history")
def api_page_history(pid):
    pg = store.get_page(pid)
    if not pg:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"page": pg, "snapshots": store.snapshots_of(pid, 40)})


@app.route("/api/pages/<int:pid>/diff")
def api_page_diff(pid):
    a, b = _int("a"), _int("b")
    ta = store.snapshot_text(a) or {}
    tb = store.snapshot_text(b) or {}
    d = monitor.diff_text(ta.get("text", ""), tb.get("text", ""), max_lines=400)
    return jsonify(d)


# --------------------------- changes ---------------------------------------- #
@app.route("/api/changes")
def api_changes():
    return jsonify(store.changes(
        competitor_id=_int("competitor_id") or None, type_=_s("type") or None,
        unseen=_s("unseen") == "1", q=_s("q"), page=_int("page"), per=_int("per", 50)))


@app.route("/api/changes/<int:chid>")
def api_change_detail(chid):
    d = store.change_detail(chid)
    if not d:
        return jsonify({"ok": False}), 404
    return jsonify(d)


@app.route("/api/changes/seen", methods=["POST"])
def api_changes_seen():
    store.mark_changes_seen(competitor_id=_int("competitor_id") or None, ids=_ids("ids") or None)
    return jsonify({"ok": True})


@app.route("/api/changes/delete", methods=["POST"])
def api_changes_delete():
    n = store.delete_changes(competitor_id=_int("competitor_id") or None)
    return jsonify({"ok": True, "count": n})


@app.route("/api/export/changes.csv")
def api_export_changes():
    csv = store.export_changes_csv(competitor_id=request.args.get("competitor_id", type=int))
    return Response(csv, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=rivalradar-changes.csv"})


# --------------------------- technology ------------------------------------- #
@app.route("/api/tech")
def api_tech():
    rows = store.all_tech()
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"] or "Other", []).append(r)
    return jsonify({"by_category": by_cat, "total": len(rows)})


# --------------------------- webhooks --------------------------------------- #
@app.route("/api/webhooks")
def api_webhooks():
    return jsonify({"webhooks": store.webhooks()})


@app.route("/api/webhooks", methods=["POST"])
def api_add_webhook():
    url = _s("url")
    if not url.startswith("http"):
        return jsonify({"ok": False, "error": "Enter a valid webhook URL (https://…)."}), 400
    wid = store.add_webhook(url, label=_s("label"), events=_s("events", "all") or "all",
                            secret=_s("secret"))
    return jsonify({"ok": True, "id": wid})


@app.route("/api/webhooks/<int:wid>", methods=["POST"])
def api_update_webhook(wid):
    kw = {}
    for f in ("label", "url", "events", "secret"):
        if request.form.get(f) is not None:
            kw[f] = _s(f)
    if _s("active") != "":
        kw["active"] = 1 if _s("active") == "1" else 0
    store.update_webhook(wid, **kw)
    return jsonify({"ok": True})


@app.route("/api/webhooks/<int:wid>/delete", methods=["POST"])
def api_delete_webhook(wid):
    store.delete_webhook(wid)
    return jsonify({"ok": True})


@app.route("/api/webhooks/test", methods=["POST"])
def api_test_webhook():
    return jsonify(notify.test_webhook(_s("url"), _s("secret")))


# --------------------------- settings --------------------------------------- #
@app.route("/api/settings", methods=["POST"])
def api_settings():
    keys = ("scan_interval_min", "respect_robots", "request_timeout", "max_pages_per_site",
            "request_delay_ms", "keep_snapshots", "user_agent", "smtp_host", "smtp_port",
            "smtp_security", "smtp_user", "smtp_pass", "smtp_from", "alert_email")
    d = {}
    for k in keys:
        v = request.form.get(k)
        if v is not None:
            if k == "smtp_pass" and v == "":
                continue
            d[k] = v
    store.save_settings(d)
    return jsonify({"ok": True})


@app.route("/api/settings/test-email", methods=["POST"])
def api_test_email():
    return jsonify(notify.test_email(store.get_settings()))


@app.route("/api/data/clear", methods=["POST"])
def api_data_clear():
    if _s("confirm") != "DELETE":
        return jsonify({"ok": False, "error": "Confirmation required."}), 400
    store.clear_all()
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": "Request too large."}), 413


# --------------------------- scheduler -------------------------------------- #
def _scheduler_loop():
    while True:
        try:
            default_iv = store.setting_int("scan_interval_min", 720)
            now = time.time()
            for comp in store.competitors(active_only=True):
                iv = comp.get("interval_min") or default_iv
                if iv <= 0:
                    continue
                due = (comp.get("last_scan") or 0) + iv * 60
                with _JOBS_LOCK:
                    running = JOBS.get(comp["id"], {}).get("status") == "running"
                if now >= due and not running:
                    _start_scan(comp["id"])
                    time.sleep(2)   # stagger launches
        except Exception:
            import traceback
            traceback.print_exc()
        time.sleep(60)


# --------------------------- boot ------------------------------------------- #
_BOOTED = False


def _boot():
    global _BOOTED
    if _BOOTED:
        return
    _BOOTED = True
    store.init()
    threading.Thread(target=_scheduler_loop, daemon=True).start()


def _port_file():
    base = app_paths.data_dir() if app_paths else HERE
    return os.path.join(base, "port.txt")


def _running_copy():
    import socket
    import urllib.request
    ports = []
    try:
        with open(_port_file(), encoding="utf-8") as f:
            ports.append(int(f.read().strip()))
    except Exception:
        pass
    ports += [p for p in range(DEFAULT_PORT, DEFAULT_PORT + 20) if p not in ports]
    for p in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", p)) != 0:
                continue
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/ping", timeout=2) as r:
                if json.loads(r.read().decode()).get("app") == "rivalradar":
                    return f"http://127.0.0.1:{p}"
        except Exception:
            continue
    return None


def _pick_port(preferred):
    import socket
    for p in [preferred] + list(range(preferred + 1, preferred + 20)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return preferred


def _redirect_logs_to_file():
    try:
        base = app_paths.data_dir() if app_paths else HERE
        f = open(os.path.join(base, "rivalradar.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f
    except Exception:
        class _Null:
            def write(self, *a):
                pass

            def flush(self):
                pass
        sys.stdout = sys.stderr = _Null()


if __name__ == "__main__":
    frozen = getattr(sys, "frozen", False)
    if frozen or sys.stdout is None:
        _redirect_logs_to_file()
    open_browser = os.environ.get("RR_NO_BROWSER") != "1"
    if not os.environ.get("PORT") and not os.environ.get("RR_DB"):
        existing = _running_copy()
        if existing:
            if open_browser:
                import webbrowser
                webbrowser.open(existing)
            sys.exit(0)
    _boot()
    port = int(os.environ.get("PORT", "0")) or _pick_port(DEFAULT_PORT)
    LOCAL_URL = f"http://127.0.0.1:{port}"
    try:
        with open(_port_file(), "w", encoding="utf-8") as f:
            f.write(str(port))
    except Exception:
        pass
    print(f"\n  RivalRadar  ->  http://127.0.0.1:{port}\n")
    if open_browser:
        def _open():
            import webbrowser
            time.sleep(1.2)
            try:
                webbrowser.open(LOCAL_URL)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
else:
    _boot()
