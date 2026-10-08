"""
Local storage for RivalRadar (SQLite). Competitors, the pages we track for each,
a snapshot history per page, a change timeline, detected technologies, outbound
webhooks and the scan log. Everything stays on this machine.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

_LOCK = threading.RLock()
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rivalradar.db")

COLORS = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
          "#ec4899", "#14b8a6", "#f97316", "#64748b", "#22c55e", "#eab308"]

CHANGE_TYPES = ("new_page", "removed_page", "content", "title", "meta", "h1",
                "status", "tech_added", "tech_removed", "price", "sitemap",
                "promo", "keyword", "product", "article")

DEFAULT_SETTINGS = {
    "scan_interval_min": "720",      # default 12h auto-scan cadence
    "respect_robots": "1",
    "request_timeout": "20",
    "max_pages_per_site": "300",
    "request_delay_ms": "600",       # politeness delay between requests to one site
    "keep_snapshots": "20",          # history kept per page
    "user_agent": "RivalRadar/1.0 (+website change monitor)",
    # optional email alerts (user's own SMTP)
    "smtp_host": "", "smtp_port": "587", "smtp_security": "starttls",
    "smtp_user": "", "smtp_pass": "", "smtp_from": "", "alert_email": "",
}


def set_db_path(path: str):
    global _DB_PATH
    _DB_PATH = path


def _conn():
    c = sqlite3.connect(_DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _cols(c, table):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}


def _add_cols(c, table, cols):
    have = _cols(c, table)
    for name, decl in cols:
        if name not in have:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init():
    with _LOCK, _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS competitors(
                id INTEGER PRIMARY KEY, name TEXT, domain TEXT UNIQUE, base_url TEXT,
                notes TEXT DEFAULT '', color TEXT DEFAULT '', active INTEGER DEFAULT 1,
                interval_min INTEGER DEFAULT 0, created_at REAL,
                last_scan REAL DEFAULT 0, last_change REAL DEFAULT 0,
                status TEXT DEFAULT 'new', scan_error TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS pages(
                id INTEGER PRIMARY KEY, competitor_id INTEGER, url TEXT, kind TEXT DEFAULT 'page',
                selector TEXT DEFAULT '', label TEXT DEFAULT '',
                discovered_at REAL, last_seen REAL DEFAULT 0, last_status INTEGER DEFAULT 0,
                last_hash TEXT DEFAULT '', title TEXT DEFAULT '', meta_desc TEXT DEFAULT '',
                h1 TEXT DEFAULT '', word_count INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1, gone INTEGER DEFAULT 0,
                UNIQUE(competitor_id, url),
                FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS snapshots(
                id INTEGER PRIMARY KEY, page_id INTEGER, competitor_id INTEGER, ts REAL,
                status_code INTEGER, resp_ms INTEGER, content_hash TEXT,
                title TEXT, meta_desc TEXT, h1 TEXT, word_count INTEGER,
                text TEXT, watched TEXT DEFAULT '',
                FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS changes(
                id INTEGER PRIMARY KEY, competitor_id INTEGER, page_id INTEGER DEFAULT 0,
                ts REAL, type TEXT, summary TEXT, detail TEXT DEFAULT '', url TEXT DEFAULT '',
                seen INTEGER DEFAULT 0,
                FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS tech(
                id INTEGER PRIMARY KEY, competitor_id INTEGER, name TEXT, category TEXT,
                first_seen REAL, last_seen REAL, present INTEGER DEFAULT 1,
                UNIQUE(competitor_id, name),
                FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS webhooks(
                id INTEGER PRIMARY KEY, label TEXT DEFAULT '', url TEXT, events TEXT DEFAULT 'all',
                secret TEXT DEFAULT '', active INTEGER DEFAULT 1, created_at REAL,
                last_status TEXT DEFAULT '', last_fired REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS scans(
                id INTEGER PRIMARY KEY, competitor_id INTEGER, ts REAL, pages_checked INTEGER DEFAULT 0,
                changes_found INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ok', error TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS products(
                id INTEGER PRIMARY KEY, competitor_id INTEGER, url TEXT, name TEXT,
                price REAL DEFAULT 0, currency TEXT DEFAULT '', availability TEXT DEFAULT '',
                rating REAL DEFAULT 0, review_count INTEGER DEFAULT 0,
                first_seen REAL, last_seen REAL, present INTEGER DEFAULT 1,
                UNIQUE(competitor_id, url, name),
                FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS price_history(
                id INTEGER PRIMARY KEY, product_id INTEGER, ts REAL, price REAL, currency TEXT,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS feed_items(
                id INTEGER PRIMARY KEY, competitor_id INTEGER, guid TEXT, title TEXT, link TEXT,
                published REAL DEFAULT 0, ts REAL, UNIQUE(competitor_id, guid),
                FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS keywords(
                id INTEGER PRIMARY KEY, competitor_id INTEGER DEFAULT 0, word TEXT,
                created_at REAL, UNIQUE(competitor_id, word));
            CREATE TABLE IF NOT EXISTS intel(
                competitor_id INTEGER PRIMARY KEY, data TEXT DEFAULT '{}', ts REAL DEFAULT 0,
                FOREIGN KEY(competitor_id) REFERENCES competitors(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX IF NOT EXISTS idx_prod_comp ON products(competitor_id);
            CREATE INDEX IF NOT EXISTS idx_ph_prod ON price_history(product_id);
            CREATE INDEX IF NOT EXISTS idx_feed_comp ON feed_items(competitor_id);
            CREATE INDEX IF NOT EXISTS idx_pages_comp ON pages(competitor_id);
            CREATE INDEX IF NOT EXISTS idx_snap_page ON snapshots(page_id);
            CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(ts);
            CREATE INDEX IF NOT EXISTS idx_changes_comp ON changes(competitor_id);
            CREATE INDEX IF NOT EXISTS idx_changes_ts ON changes(ts);
            CREATE INDEX IF NOT EXISTS idx_tech_comp ON tech(competitor_id);
            CREATE INDEX IF NOT EXISTS idx_scans_comp ON scans(competitor_id);
        """)


# --------------------------- settings --------------------------------------- #
def get_settings():
    with _LOCK, _conn() as c:
        st = {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM settings")}
    out = dict(DEFAULT_SETTINGS)
    out.update(st)
    return out


def save_settings(d):
    with _LOCK, _conn() as c:
        for k, v in d.items():
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))


def setting_int(key, default=0):
    try:
        return int(float(get_settings().get(key, default)))
    except (TypeError, ValueError):
        return int(default)


# --------------------------- competitors ------------------------------------ #
def add_competitor(name, domain, base_url, notes="", color="", interval_min=0):
    with _LOCK, _conn() as c:
        if not color:
            n = c.execute("SELECT COUNT(*) FROM competitors").fetchone()[0]
            color = COLORS[n % len(COLORS)]
        return c.execute(
            "INSERT INTO competitors(name,domain,base_url,notes,color,active,interval_min,"
            "created_at,status) VALUES(?,?,?,?,?,1,?,?,'new')",
            (name, domain, base_url, notes, color, int(interval_min or 0), time.time())).lastrowid


def update_competitor(cid, **kw):
    allowed = {"name", "domain", "base_url", "notes", "color", "active", "interval_min",
               "status", "scan_error", "last_scan", "last_change"}
    kw = {k: v for k, v in kw.items() if k in allowed}
    if not kw:
        return
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE competitors SET {','.join(k + '=?' for k in kw)} WHERE id=?",
                  list(kw.values()) + [cid])


def delete_competitor(cid):
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM competitors WHERE id=?", (cid,))


def get_competitor(cid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM competitors WHERE id=?", (cid,)).fetchone()
    return dict(r) if r else None


def find_competitor_by_domain(domain):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM competitors WHERE domain=?", (domain,)).fetchone()
    return dict(r) if r else None


def competitors(active_only=False):
    q = "SELECT * FROM competitors"
    if active_only:
        q += " WHERE active=1"
    with _LOCK, _conn() as c:
        rows = [dict(r) for r in c.execute(q + " ORDER BY name COLLATE NOCASE")]
        for r in rows:
            r["pages"] = c.execute("SELECT COUNT(*) FROM pages WHERE competitor_id=? AND gone=0",
                                   (r["id"],)).fetchone()[0]
            r["unseen"] = c.execute("SELECT COUNT(*) FROM changes WHERE competitor_id=? AND seen=0",
                                    (r["id"],)).fetchone()[0]
            r["changes7"] = c.execute("SELECT COUNT(*) FROM changes WHERE competitor_id=? AND ts>?",
                                      (r["id"], time.time() - 7 * 86400)).fetchone()[0]
            r["tech_count"] = c.execute("SELECT COUNT(*) FROM tech WHERE competitor_id=? AND present=1",
                                        (r["id"],)).fetchone()[0]
    return rows


# --------------------------- pages ------------------------------------------ #
def add_page(competitor_id, url, kind="page", selector="", label=""):
    with _LOCK, _conn() as c:
        ex = c.execute("SELECT id FROM pages WHERE competitor_id=? AND url=?",
                       (competitor_id, url)).fetchone()
        if ex:
            if kind == "watch":
                c.execute("UPDATE pages SET kind='watch', selector=?, label=?, active=1, gone=0 "
                          "WHERE id=?", (selector, label, ex["id"]))
            return ex["id"]
        return c.execute(
            "INSERT INTO pages(competitor_id,url,kind,selector,label,discovered_at,active) "
            "VALUES(?,?,?,?,?,?,1)",
            (competitor_id, url, kind, selector, label, time.time())).lastrowid


def pages_of(competitor_id, include_gone=True):
    q = "SELECT * FROM pages WHERE competitor_id=?"
    if not include_gone:
        q += " AND gone=0"
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY kind DESC, url", (competitor_id,))]


def active_pages(competitor_id):
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM pages WHERE competitor_id=? AND active=1 AND gone=0 ORDER BY id",
            (competitor_id,))]


def get_page(pid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM pages WHERE id=?", (pid,)).fetchone()
    return dict(r) if r else None


def delete_page(pid):
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM pages WHERE id=?", (pid,))


def update_page(pid, **kw):
    allowed = {"kind", "selector", "label", "active", "gone", "last_seen", "last_status",
               "last_hash", "title", "meta_desc", "h1", "word_count"}
    kw = {k: v for k, v in kw.items() if k in allowed}
    if not kw:
        return
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE pages SET {','.join(k + '=?' for k in kw)} WHERE id=?",
                  list(kw.values()) + [pid])


def known_urls(competitor_id):
    with _LOCK, _conn() as c:
        return {r[0] for r in c.execute("SELECT url FROM pages WHERE competitor_id=?",
                                        (competitor_id,))}


# --------------------------- snapshots -------------------------------------- #
def last_snapshot(page_id):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM snapshots WHERE page_id=? ORDER BY ts DESC LIMIT 1",
                      (page_id,)).fetchone()
    return dict(r) if r else None


def add_snapshot(page_id, competitor_id, data, keep=20):
    with _LOCK, _conn() as c:
        sid = c.execute(
            "INSERT INTO snapshots(page_id,competitor_id,ts,status_code,resp_ms,content_hash,"
            "title,meta_desc,h1,word_count,text,watched) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (page_id, competitor_id, time.time(), data.get("status_code", 0),
             data.get("resp_ms", 0), data.get("content_hash", ""), data.get("title", ""),
             data.get("meta_desc", ""), data.get("h1", ""), data.get("word_count", 0),
             (data.get("text", "") or "")[:300000], (data.get("watched", "") or "")[:100000])).lastrowid
        # prune old history
        old = [r[0] for r in c.execute(
            "SELECT id FROM snapshots WHERE page_id=? ORDER BY ts DESC LIMIT -1 OFFSET ?",
            (page_id, max(2, keep)))]
        if old:
            c.execute(f"DELETE FROM snapshots WHERE id IN ({','.join('?' * len(old))})", old)
    return sid


def snapshots_of(page_id, limit=30):
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,ts,status_code,resp_ms,content_hash,title,meta_desc,h1,word_count "
            "FROM snapshots WHERE page_id=? ORDER BY ts DESC LIMIT ?", (page_id, limit))]


def snapshot_text(sid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT text,watched FROM snapshots WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


# --------------------------- changes ---------------------------------------- #
def add_change(competitor_id, type_, summary, detail="", url="", page_id=0):
    with _LOCK, _conn() as c:
        cid = c.execute(
            "INSERT INTO changes(competitor_id,page_id,ts,type,summary,detail,url,seen) "
            "VALUES(?,?,?,?,?,?,?,0)",
            (competitor_id, page_id, time.time(), type_, summary,
             detail if isinstance(detail, str) else json.dumps(detail), url)).lastrowid
        c.execute("UPDATE competitors SET last_change=? WHERE id=?", (time.time(), competitor_id))
    return cid


def changes(competitor_id=None, type_=None, unseen=None, q="", page=0, per=50):
    where, args = ["1=1"], []
    if competitor_id:
        where.append("ch.competitor_id=?")
        args.append(competitor_id)
    if type_:
        where.append("ch.type=?")
        args.append(type_)
    if unseen:
        where.append("ch.seen=0")
    if q:
        where.append("(ch.summary LIKE ? OR ch.url LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    w = " AND ".join(where)
    with _LOCK, _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM changes ch WHERE {w}", args).fetchone()[0]
        rows = [dict(r) for r in c.execute(
            f"SELECT ch.*, co.name comp_name, co.color comp_color FROM changes ch "
            f"JOIN competitors co ON co.id=ch.competitor_id WHERE {w} "
            f"ORDER BY ch.ts DESC LIMIT ? OFFSET ?", args + [per, page * per])]
    return {"total": total, "rows": rows, "page": page, "per": per}


def change_detail(chid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT ch.*, co.name comp_name, co.color comp_color FROM changes ch "
                      "JOIN competitors co ON co.id=ch.competitor_id WHERE ch.id=?",
                      (chid,)).fetchone()
    return dict(r) if r else None


def mark_changes_seen(competitor_id=None, ids=None):
    with _LOCK, _conn() as c:
        if ids:
            ids = [int(i) for i in ids]
            c.execute(f"UPDATE changes SET seen=1 WHERE id IN ({','.join('?' * len(ids))})", ids)
        elif competitor_id:
            c.execute("UPDATE changes SET seen=1 WHERE competitor_id=?", (competitor_id,))
        else:
            c.execute("UPDATE changes SET seen=1")


def delete_changes(competitor_id=None):
    with _LOCK, _conn() as c:
        if competitor_id:
            return c.execute("DELETE FROM changes WHERE competitor_id=?", (competitor_id,)).rowcount
        return c.execute("DELETE FROM changes").rowcount


# --------------------------- technology ------------------------------------- #
def sync_tech(competitor_id, detected):
    """detected: list of {name, category}. Records additions/removals as changes."""
    now = time.time()
    added, removed = [], []
    names = {d["name"] for d in detected}
    with _LOCK, _conn() as c:
        prev = {r["name"]: dict(r) for r in c.execute(
            "SELECT * FROM tech WHERE competitor_id=?", (competitor_id,))}
        for d in detected:
            if d["name"] in prev:
                was_present = prev[d["name"]]["present"]
                c.execute("UPDATE tech SET last_seen=?, present=1, category=? WHERE id=?",
                          (now, d.get("category", ""), prev[d["name"]]["id"]))
                if not was_present:
                    added.append(d["name"])
            else:
                c.execute("INSERT INTO tech(competitor_id,name,category,first_seen,last_seen,present)"
                          " VALUES(?,?,?,?,?,1)",
                          (competitor_id, d["name"], d.get("category", ""), now, now))
                added.append(d["name"])
        for name, row in prev.items():
            if row["present"] and name not in names:
                c.execute("UPDATE tech SET present=0 WHERE id=?", (row["id"],))
                removed.append(name)
    return added, removed


def tech_of(competitor_id):
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM tech WHERE competitor_id=? ORDER BY present DESC, category, name",
            (competitor_id,))]


def all_tech():
    """Technology across all competitors, for the Technology page."""
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT t.*, co.name comp_name, co.color comp_color FROM tech t "
            "JOIN competitors co ON co.id=t.competitor_id WHERE t.present=1 "
            "ORDER BY t.category, t.name")]


# --------------------------- scans ------------------------------------------ #
def log_scan(competitor_id, pages_checked, changes_found, duration_ms, status="ok", error=""):
    with _LOCK, _conn() as c:
        c.execute("INSERT INTO scans(competitor_id,ts,pages_checked,changes_found,duration_ms,"
                  "status,error) VALUES(?,?,?,?,?,?,?)",
                  (competitor_id, time.time(), pages_checked, changes_found, duration_ms,
                   status, (error or "")[:500]))
        # keep the last 200 scans per competitor
        old = [r[0] for r in c.execute(
            "SELECT id FROM scans WHERE competitor_id=? ORDER BY ts DESC LIMIT -1 OFFSET 200",
            (competitor_id,))]
        if old:
            c.execute(f"DELETE FROM scans WHERE id IN ({','.join('?' * len(old))})", old)


def recent_scans(competitor_id=None, limit=50):
    with _LOCK, _conn() as c:
        if competitor_id:
            rows = c.execute("SELECT * FROM scans WHERE competitor_id=? ORDER BY ts DESC LIMIT ?",
                             (competitor_id, limit)).fetchall()
        else:
            rows = c.execute("SELECT s.*, co.name comp_name FROM scans s "
                             "JOIN competitors co ON co.id=s.competitor_id "
                             "ORDER BY s.ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------- webhooks --------------------------------------- #
def add_webhook(url, label="", events="all", secret=""):
    with _LOCK, _conn() as c:
        return c.execute("INSERT INTO webhooks(label,url,events,secret,active,created_at) "
                         "VALUES(?,?,?,?,1,?)",
                         (label, url, events, secret, time.time())).lastrowid


def update_webhook(wid, **kw):
    allowed = {"label", "url", "events", "secret", "active", "last_status", "last_fired"}
    kw = {k: v for k, v in kw.items() if k in allowed}
    if not kw:
        return
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE webhooks SET {','.join(k + '=?' for k in kw)} WHERE id=?",
                  list(kw.values()) + [wid])


def delete_webhook(wid):
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM webhooks WHERE id=?", (wid,))


def webhooks(active_only=False):
    q = "SELECT * FROM webhooks"
    if active_only:
        q += " WHERE active=1"
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY created_at")]


# --------------------------- products / prices ------------------------------ #
def upsert_product(competitor_id, p):
    """Insert/update a product from structured data. Returns (product_id, old_price, new_price)."""
    now = time.time()
    name = (p.get("name") or "").strip()
    url = p.get("url") or ""
    price = float(p.get("price") or 0)
    with _LOCK, _conn() as c:
        ex = c.execute("SELECT id,price FROM products WHERE competitor_id=? AND url=? AND name=?",
                       (competitor_id, url, name)).fetchone()
        if ex:
            old = ex["price"]
            c.execute("UPDATE products SET price=?,currency=?,availability=?,rating=?,review_count=?,"
                      "last_seen=?,present=1 WHERE id=?",
                      (price, p.get("currency", ""), p.get("availability", ""), float(p.get("rating") or 0),
                       int(p.get("review_count") or 0), now, ex["id"]))
            pid = ex["id"]
            if price and abs(price - (old or 0)) > 0.001:
                c.execute("INSERT INTO price_history(product_id,ts,price,currency) VALUES(?,?,?,?)",
                          (pid, now, price, p.get("currency", "")))
            return pid, old, price
        pid = c.execute("INSERT INTO products(competitor_id,url,name,price,currency,availability,"
                        "rating,review_count,first_seen,last_seen,present) VALUES(?,?,?,?,?,?,?,?,?,?,1)",
                        (competitor_id, url, name, price, p.get("currency", ""), p.get("availability", ""),
                         float(p.get("rating") or 0), int(p.get("review_count") or 0), now, now)).lastrowid
        if price:
            c.execute("INSERT INTO price_history(product_id,ts,price,currency) VALUES(?,?,?,?)",
                      (pid, now, price, p.get("currency", "")))
        return pid, None, price


def mark_products_seen(competitor_id, seen_keys):
    """Flag products not seen this scan as gone (seen_keys = set of (url,name))."""
    with _LOCK, _conn() as c:
        for r in c.execute("SELECT id,url,name FROM products WHERE competitor_id=? AND present=1",
                           (competitor_id,)).fetchall():
            if (r["url"], r["name"]) not in seen_keys:
                c.execute("UPDATE products SET present=0 WHERE id=?", (r["id"],))


def products_of(competitor_id):
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM products WHERE competitor_id=? ORDER BY present DESC, name", (competitor_id,))]


def price_history(product_id, limit=200):
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT ts,price,currency FROM price_history WHERE product_id=? ORDER BY ts", (product_id,))][-limit:]


# --------------------------- feeds ------------------------------------------ #
def add_feed_item(competitor_id, item):
    """Returns True if this item is new."""
    with _LOCK, _conn() as c:
        cur = c.execute("INSERT OR IGNORE INTO feed_items(competitor_id,guid,title,link,published,ts) "
                        "VALUES(?,?,?,?,?,?)",
                        (competitor_id, item.get("guid", ""), item.get("title", ""), item.get("link", ""),
                         item.get("published", 0) or 0, time.time()))
        return cur.rowcount > 0


def feed_items(competitor_id, limit=40):
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM feed_items WHERE competitor_id=? ORDER BY COALESCE(NULLIF(published,0),ts) DESC "
            "LIMIT ?", (competitor_id, limit))]


def feed_count(competitor_id):
    with _LOCK, _conn() as c:
        return c.execute("SELECT COUNT(*) FROM feed_items WHERE competitor_id=?", (competitor_id,)).fetchone()[0]


# --------------------------- keyword alerts --------------------------------- #
def add_keyword(word, competitor_id=0):
    word = (word or "").strip()
    if not word:
        return None
    with _LOCK, _conn() as c:
        try:
            return c.execute("INSERT INTO keywords(competitor_id,word,created_at) VALUES(?,?,?)",
                             (competitor_id, word, time.time())).lastrowid
        except sqlite3.IntegrityError:
            return None


def delete_keyword(kid):
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM keywords WHERE id=?", (kid,))


def keywords(competitor_id=None):
    with _LOCK, _conn() as c:
        if competitor_id is None:
            return [dict(r) for r in c.execute("SELECT * FROM keywords ORDER BY word")]
        return [dict(r) for r in c.execute(
            "SELECT * FROM keywords WHERE competitor_id IN (0,?) ORDER BY word", (competitor_id,))]


# --------------------------- intel blob ------------------------------------- #
def get_intel(competitor_id):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT data,ts FROM intel WHERE competitor_id=?", (competitor_id,)).fetchone()
    if not r:
        return {}
    try:
        d = json.loads(r["data"] or "{}")
        d["_ts"] = r["ts"]
        return d
    except Exception:
        return {}


def save_intel(competitor_id, data):
    with _LOCK, _conn() as c:
        c.execute("INSERT INTO intel(competitor_id,data,ts) VALUES(?,?,?) "
                  "ON CONFLICT(competitor_id) DO UPDATE SET data=excluded.data,ts=excluded.ts",
                  (competitor_id, json.dumps(data), time.time()))


# --------------------------- dashboard -------------------------------------- #
def dashboard():
    now = time.time()
    with _LOCK, _conn() as c:
        comps = c.execute("SELECT COUNT(*) FROM competitors").fetchone()[0]
        active = c.execute("SELECT COUNT(*) FROM competitors WHERE active=1").fetchone()[0]
        pages = c.execute("SELECT COUNT(*) FROM pages WHERE gone=0").fetchone()[0]
        unseen = c.execute("SELECT COUNT(*) FROM changes WHERE seen=0").fetchone()[0]
        ch24 = c.execute("SELECT COUNT(*) FROM changes WHERE ts>?", (now - 86400,)).fetchone()[0]
        ch7 = c.execute("SELECT COUNT(*) FROM changes WHERE ts>?", (now - 7 * 86400,)).fetchone()[0]
        by_type = {r[0]: r[1] for r in c.execute(
            "SELECT type,COUNT(*) FROM changes WHERE ts>? GROUP BY type", (now - 30 * 86400,))}
        recent = [dict(r) for r in c.execute(
            "SELECT ch.*, co.name comp_name, co.color comp_color FROM changes ch "
            "JOIN competitors co ON co.id=ch.competitor_id ORDER BY ch.ts DESC LIMIT 12")]
        # 14-day activity series
        series = {}
        for r in c.execute("SELECT date(ts,'unixepoch','localtime') d, COUNT(*) n FROM changes "
                           "WHERE ts>? GROUP BY d", (now - 14 * 86400,)):
            series[r["d"]] = r["n"]
    import datetime as _dt
    days = []
    for i in range(13, -1, -1):
        d = (_dt.date.today() - _dt.timedelta(days=i)).isoformat()
        days.append({"d": d, "n": series.get(d, 0)})
    return {"competitors": comps, "active": active, "pages": pages, "unseen": unseen,
            "changes_24h": ch24, "changes_7d": ch7, "by_type": by_type, "recent": recent,
            "series": days}


# --------------------------- export / danger zone --------------------------- #
def export_changes_csv(competitor_id=None):
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["when", "competitor", "type", "summary", "url"])
    data = changes(competitor_id=competitor_id, per=100000)
    for r in data["rows"]:
        w.writerow([time.strftime("%Y-%m-%d %H:%M", time.localtime(r["ts"])),
                    r["comp_name"], r["type"], r["summary"], r["url"]])
    return out.getvalue()


def clear_all():
    with _LOCK, _conn() as c:
        for t in ("snapshots", "changes", "tech", "scans", "pages", "competitors"):
            c.execute(f"DELETE FROM {t}")
