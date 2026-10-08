"""
RivalRadar monitoring engine.

Fetches a competitor's pages, extracts SEO fields + visible text, detects the
technologies they use, discovers new/removed pages from their sitemap, and diffs
each page against the last snapshot to produce a change timeline. Pure requests +
BeautifulSoup; no browser, no third-party services.

Safe by default: identifies itself with a clear User-Agent, rate-limits itself,
honours robots.txt (optional), caps pages per site, hard timeouts, and refuses to
fetch private / loopback addresses (SSRF guard).
"""

from __future__ import annotations

import difflib
import hashlib
import ipaddress
import re
import socket
import time
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

import store
import notify
import intel

_SESSION = requests.Session()
_ROBOTS_CACHE: dict[str, RobotFileParser] = {}


# --------------------------------------------------------------------------- #
#  URL helpers + SSRF guard
# --------------------------------------------------------------------------- #
def normalize_domain(raw: str) -> tuple[str, str]:
    """Return (domain, base_url) from whatever the user typed."""
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    if "://" not in raw:
        raw = "https://" + raw
    p = urlparse(raw)
    netloc = (p.netloc or p.path).split("/")[0].lower()
    host = netloc[4:] if netloc.startswith("www.") else netloc
    base = f"{p.scheme or 'https'}://{netloc}"
    return host, base


def clean_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        path = p.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        return urlunparse((p.scheme, p.netloc, path, "", p.query, ""))
    except Exception:
        return url.strip()


def same_site(url: str, domain: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host == domain or host.endswith("." + domain)
    except Exception:
        return False


def is_safe_url(url: str) -> bool:
    """Block loopback / private / reserved addresses (SSRF protection)."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.hostname
        if not host:
            return False
        infos = socket.getaddrinfo(host, None)
        for fam, _, _, _, sockaddr in infos:
            ip = ipaddress.ip_address(sockaddr[0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                    or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
#  fetching
# --------------------------------------------------------------------------- #
def _robots(base_url: str, ua: str, timeout: int):
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    if root in _ROBOTS_CACHE:
        return _ROBOTS_CACHE[root]
    rp = RobotFileParser()
    rp.set_url(root + "/robots.txt")
    try:
        r = _SESSION.get(root + "/robots.txt", headers={"User-Agent": ua}, timeout=timeout)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        rp._rr_sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text) if r.status_code == 200 else []
    except Exception:
        rp.parse([])
        rp._rr_sitemaps = []
    _ROBOTS_CACHE[root] = rp
    return rp


def fetch(url: str, ua: str, timeout: int) -> dict:
    """Return {ok, status, html, headers, resp_ms, final_url, error}."""
    out = {"ok": False, "status": 0, "html": "", "headers": {}, "resp_ms": 0,
           "final_url": url, "error": ""}
    if not is_safe_url(url):
        out["error"] = "blocked (unsafe/private address)"
        return out
    t0 = time.time()
    try:
        r = _SESSION.get(url, headers={"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,"
                                       "application/xml;q=0.9,*/*;q=0.8"},
                         timeout=timeout, allow_redirects=True)
    except requests.exceptions.SSLError:
        try:
            r = _SESSION.get(url, headers={"User-Agent": ua}, timeout=timeout,
                             allow_redirects=True, verify=False)
        except Exception as e:
            out["error"] = f"SSL error ({e})"[:200]
            return out
    except requests.exceptions.RequestException as e:
        out["error"] = str(e)[:200]
        return out
    out["resp_ms"] = int((time.time() - t0) * 1000)
    out["status"] = r.status_code
    out["final_url"] = str(r.url)
    out["headers"] = {k.lower(): v for k, v in r.headers.items()}
    ctype = out["headers"].get("content-type", "")
    if r.status_code == 200 and ("html" in ctype or "xml" in ctype or not ctype):
        out["html"] = r.text[:2_000_000]
    out["ok"] = r.status_code < 400
    return out


# --------------------------------------------------------------------------- #
#  SEO + text extraction
# --------------------------------------------------------------------------- #
def extract(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if md and md.get("content"):
        meta_desc = md["content"].strip()
    h1 = ""
    h1t = soup.find("h1")
    if h1t:
        h1 = h1t.get_text(" ", strip=True)
    canonical = ""
    cl = soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
    if cl and cl.get("href"):
        canonical = cl["href"].strip()
    robots_meta = ""
    rm = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    if rm and rm.get("content"):
        robots_meta = rm["content"].strip()
    structured = bool(soup.find("script", attrs={"type": "application/ld+json"}))
    imgs = soup.find_all("img")
    images_no_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
    body = soup.find("body") or soup
    text = body.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    links = []
    for a in soup.find_all("a", href=True):
        links.append(a["href"])
    return {"title": title[:400], "meta_desc": meta_desc[:600], "h1": h1[:400],
            "canonical": canonical[:400], "robots_meta": robots_meta[:200],
            "structured": structured, "text": text, "word_count": len(text.split()),
            "images": len(imgs), "images_no_alt": images_no_alt, "links": links}


def extract_selector(html: str, selector: str) -> str:
    """Visible text of a CSS selector region (for watched price/stock blocks)."""
    try:
        soup = BeautifulSoup(html or "", "html.parser")
        for t in soup(["script", "style"]):
            t.decompose()
        nodes = soup.select(selector)
        return re.sub(r"\s+", " ", " ".join(n.get_text(" ", strip=True) for n in nodes)).strip()
    except Exception:
        return ""


def _norm_text(text: str) -> str:
    return "\n".join(s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text or "") if s.strip())


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()[:32]


# --------------------------------------------------------------------------- #
#  technology detection
# --------------------------------------------------------------------------- #
_TECH = [
    # (name, category, html-regex or None, header-check(dict)->bool or None)
    ("WordPress", "CMS", r"wp-content|wp-includes|/wp-json", None),
    ("Shopify", "Ecommerce", r"cdn\.shopify\.com|Shopify\.theme|myshopify\.com", None),
    ("WooCommerce", "Ecommerce", r"woocommerce", None),
    ("Magento", "Ecommerce", r"Magento|mage/|/static/version\d", None),
    ("BigCommerce", "Ecommerce", r"bigcommerce\.com", None),
    ("Wix", "Website builder", r"wix\.com|wixstatic\.com|X-Wix", None),
    ("Squarespace", "Website builder", r"squarespace\.com|static1\.squarespace", None),
    ("Webflow", "Website builder", r"webflow\.com|wf-", None),
    ("Drupal", "CMS", r"Drupal|sites/default/files", None),
    ("Joomla", "CMS", r"Joomla|/media/jui/", None),
    ("Ghost", "CMS", r"ghost\.io|content=\"Ghost", None),
    ("HubSpot", "Marketing", r"hs-scripts\.com|hubspot\.com|hsforms", None),
    ("Google Analytics", "Analytics", r"google-analytics\.com|gtag\(['\"]config|googletagmanager\.com/gtag", None),
    ("Google Tag Manager", "Analytics", r"googletagmanager\.com/gtm", None),
    ("Meta Pixel", "Advertising", r"connect\.facebook\.net|fbq\(['\"]init", None),
    ("TikTok Pixel", "Advertising", r"analytics\.tiktok\.com", None),
    ("Hotjar", "Analytics", r"static\.hotjar\.com|hjid", None),
    ("Klaviyo", "Email", r"klaviyo\.com|klaviyo\.js", None),
    ("Mailchimp", "Email", r"mailchimp\.com|mc\.us\d", None),
    ("Intercom", "Support", r"intercom\.io|widget\.intercom", None),
    ("Zendesk", "Support", r"zendesk\.com|zdassets", None),
    ("Drift", "Support", r"drift\.com|js\.driftt", None),
    ("React", "JS framework", r"__NEXT_DATA__|react|data-reactroot", None),
    ("Next.js", "JS framework", r"__NEXT_DATA__|/_next/static", None),
    ("Vue.js", "JS framework", r"vue(?:\.min)?\.js|data-v-|__VUE__", None),
    ("Angular", "JS framework", r"ng-version|angular(?:\.min)?\.js", None),
    ("jQuery", "JS library", r"jquery(?:-\d|\.min)?\.js", None),
    ("Bootstrap", "UI framework", r"bootstrap(?:\.min)?\.(?:css|js)", None),
    ("Tailwind CSS", "UI framework", r"tailwind", None),
    ("Stripe", "Payments", r"js\.stripe\.com", None),
    ("PayPal", "Payments", r"paypal\.com/sdk|paypalobjects", None),
    ("Cloudflare", "CDN / Server", None, lambda h: "cloudflare" in h.get("server", "").lower()
     or "cf-ray" in h),
    ("nginx", "CDN / Server", None, lambda h: "nginx" in h.get("server", "").lower()),
    ("Apache", "CDN / Server", None, lambda h: "apache" in h.get("server", "").lower()),
    ("Vercel", "Hosting", None, lambda h: "vercel" in h.get("server", "").lower()
     or "x-vercel-id" in h),
    ("Netlify", "Hosting", None, lambda h: "netlify" in h.get("server", "").lower()),
    ("Varnish", "CDN / Server", None, lambda h: "varnish" in h.get("via", "").lower()
     or "x-varnish" in h),
]


def detect_tech(html: str, headers: dict) -> list:
    found = {}
    low = (html or "")
    for name, cat, rx, hcheck in _TECH:
        hit = False
        if rx and re.search(rx, low, re.I):
            hit = True
        elif hcheck:
            try:
                hit = bool(hcheck(headers or {}))
            except Exception:
                hit = False
        if hit:
            found[name] = {"name": name, "category": cat}
    # generator meta tag
    m = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', low, re.I)
    if m:
        gen = m.group(1).split()[0]
        if gen and gen not in found:
            found[gen] = {"name": gen[:40], "category": "CMS"}
    return list(found.values())


# --------------------------------------------------------------------------- #
#  sitemap discovery
# --------------------------------------------------------------------------- #
def discover_sitemap_urls(base_url: str, domain: str, ua: str, timeout: int, cap: int) -> list:
    rp = _robots(base_url, ua, timeout)
    roots = list(getattr(rp, "_rr_sitemaps", []))
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    for guess in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        if root + guess not in roots:
            roots.append(root + guess)
    seen_maps, urls = set(), []
    queue = list(roots)
    while queue and len(urls) < cap:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        if not is_safe_url(sm):
            continue
        try:
            r = _SESSION.get(sm, headers={"User-Agent": ua}, timeout=timeout)
            if r.status_code != 200:
                continue
            xml = r.text
        except Exception:
            continue
        # nested sitemap index?
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml, re.I)
        is_index = "<sitemapindex" in xml.lower()
        if is_index:
            for loc in locs:
                if loc not in seen_maps and len(seen_maps) < 50:
                    queue.append(loc.strip())
        else:
            for loc in locs:
                u = clean_url(loc.strip())
                if same_site(u, domain):
                    urls.append(u)
                    if len(urls) >= cap:
                        break
    return list(dict.fromkeys(urls))


def discover_homepage_links(base_url: str, html: str, domain: str, cap: int) -> list:
    urls = []
    for href in extract(html)["links"]:
        u = clean_url(urljoin(base_url, href))
        if same_site(u, domain) and u not in urls:
            urls.append(u)
            if len(urls) >= cap:
                break
    return urls


# --------------------------------------------------------------------------- #
#  diffing
# --------------------------------------------------------------------------- #
def diff_text(old: str, new: str, max_lines: int = 60) -> dict:
    a, b = _norm_text(old).splitlines(), _norm_text(new).splitlines()
    added = removed = 0
    sample = []
    for line in difflib.unified_diff(a, b, lineterm="", n=0):
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added += 1
            if len(sample) < max_lines:
                sample.append(line[:300])
        elif line.startswith("-"):
            removed += 1
            if len(sample) < max_lines:
                sample.append(line[:300])
    return {"added": added, "removed": removed, "sample": "\n".join(sample)}


# --------------------------------------------------------------------------- #
#  scan orchestration
# --------------------------------------------------------------------------- #
def _record(comp, type_, summary, detail="", url="", page_id=0):
    store.add_change(comp["id"], type_, summary, detail, url, page_id)
    try:
        notify.dispatch(type_, comp, summary, url, detail)
    except Exception:
        pass


def scan_competitor(cid: int, discover: bool = True) -> dict:
    comp = store.get_competitor(cid)
    if not comp:
        return {"ok": False, "error": "not found"}
    st = store.get_settings()
    ua = st.get("user_agent") or "RivalRadar/1.0"
    timeout = store.setting_int("request_timeout", 20)
    delay = store.setting_int("request_delay_ms", 600) / 1000.0
    cap = store.setting_int("max_pages_per_site", 300)
    keep = store.setting_int("keep_snapshots", 20)
    respect_robots = st.get("respect_robots", "1") == "1"
    baseline = not comp.get("last_scan")
    t0 = time.time()
    changes_found = 0
    pages_checked = 0
    # intel accumulators (free-pack)
    acc_text, acc_len = [], 0
    promo_terms, promo_coupons = set(), set()
    seen_products, broken = set(), []
    prev_intel = store.get_intel(cid)
    store.update_competitor(cid, status="scanning", scan_error="")

    rp = _robots(comp["base_url"], ua, timeout) if respect_robots else None

    def allowed(u):
        if not rp:
            return True
        try:
            return rp.can_fetch(ua, u)
        except Exception:
            return True

    try:
        # 1) homepage -> tech + (optionally) link discovery
        home = fetch(comp["base_url"], ua, timeout)
        if home["ok"] and home["html"]:
            tech = detect_tech(home["html"], home["headers"])
            added, removed = store.sync_tech(cid, tech)
            if not baseline:
                for t in added:
                    _record(comp, "tech_added", f"Started using {t}", url=comp["base_url"])
                    changes_found += 1
                for t in removed:
                    _record(comp, "tech_removed", f"Stopped using {t}", url=comp["base_url"])
                    changes_found += 1
        elif home["error"]:
            store.update_competitor(cid, scan_error=home["error"])

        # 1b) homepage-derived intel saved early, so it shows before a big crawl finishes
        try:
            e0 = extract(home["html"]) if home.get("html") else {"text": "", "title": "",
                 "meta_desc": "", "h1": "", "word_count": 0, "canonical": "", "images_no_alt": 0}
            early = dict(prev_intel) if prev_intel else {}
            early.pop("_ts", None)
            early["contacts"] = intel.extract_contacts(home.get("html", ""), e0.get("text", ""))
            early["security"] = intel.security_grade(home.get("headers", {}))
            early["ssl"] = intel.ssl_info(comp["domain"])
            early["domain"] = intel.domain_age(comp["domain"])
            early["seo"] = intel.seo_audit(e0)
            store.save_intel(cid, early)
        except Exception:
            pass

        # 2) discover pages (sitemap first, homepage links as fallback)
        if discover:
            known = store.known_urls(cid)
            budget = max(0, cap - len(known))
            found = discover_sitemap_urls(comp["base_url"], comp["domain"], ua, timeout, cap) if budget else []
            if not found and home.get("html"):
                found = discover_homepage_links(comp["base_url"], home["html"], comp["domain"], min(cap, 80))
            # always track the homepage itself
            found = [clean_url(comp["base_url"])] + found
            new_urls = [u for u in dict.fromkeys(found) if u not in known][:budget + 1]
            for u in new_urls:
                store.add_page(cid, u, kind="page")
                if not baseline:
                    _record(comp, "new_page", "New page published", url=u)
                    changes_found += 1

        # 3) scan each active page
        pages = store.active_pages(cid)[:cap + 50]
        for pg in pages:
            if pg["kind"] != "watch" and not allowed(pg["url"]):
                continue
            res = fetch(pg["url"], ua, timeout)
            pages_checked += 1
            prev = store.last_snapshot(pg["id"])

            # page gone?
            if res["status"] in (404, 410) or (not res["ok"] and not res["html"]):
                if not pg["gone"]:
                    store.update_page(pg["id"], gone=1, last_status=res["status"] or 0)
                    if not baseline:
                        _record(comp, "removed_page",
                                f"Page removed or unreachable ({res['status'] or res['error']})",
                                url=pg["url"], page_id=pg["id"])
                        changes_found += 1
                time.sleep(delay)
                continue

            info = extract(res["html"]) if res["html"] else {
                "title": "", "meta_desc": "", "h1": "", "text": "", "word_count": 0}
            watched = extract_selector(res["html"], pg["selector"]) if pg.get("selector") else ""
            basis = watched if (pg["kind"] == "watch" and pg["selector"]) else info["text"]
            h = content_hash(basis)
            snap = {"status_code": res["status"], "resp_ms": res["resp_ms"], "content_hash": h,
                    "title": info["title"], "meta_desc": info["meta_desc"], "h1": info["h1"],
                    "word_count": info["word_count"], "text": info["text"], "watched": watched}

            if prev and not baseline:
                # status change
                if prev["status_code"] != res["status"] and res["status"]:
                    _record(comp, "status", f"HTTP status changed {prev['status_code']} → {res['status']}",
                            url=pg["url"], page_id=pg["id"])
                    changes_found += 1
                # title / meta / h1
                for field, label, ctype in (("title", "Title", "title"),
                                             ("meta_desc", "Meta description", "meta"),
                                             ("h1", "Headline (H1)", "h1")):
                    if (prev.get(field) or "") != (info.get(field) or ""):
                        _record(comp, ctype, f"{label} changed",
                                detail=f"Before: {prev.get(field) or '—'}\nAfter:  {info.get(field) or '—'}",
                                url=pg["url"], page_id=pg["id"])
                        changes_found += 1
                # watched region (price/stock)
                if pg["kind"] == "watch" and pg["selector"]:
                    if (prev.get("watched") or "") != watched:
                        _record(comp, "price", f"Watched content changed{': ' + (pg['label'] or '')}",
                                detail=f"Before: {prev.get('watched') or '—'}\nAfter:  {watched or '—'}",
                                url=pg["url"], page_id=pg["id"])
                        changes_found += 1
                # body content
                elif prev["content_hash"] != h:
                    d = diff_text(prev.get("text") or "", info["text"])
                    if d["added"] or d["removed"]:
                        _record(comp, "content",
                                f"Content changed (+{d['added']} / −{d['removed']} lines)",
                                detail=d["sample"], url=pg["url"], page_id=pg["id"])
                        changes_found += 1

            store.add_snapshot(pg["id"], cid, snap, keep=keep)
            store.update_page(pg["id"], last_seen=time.time(), last_status=res["status"],
                              last_hash=h, title=info["title"], meta_desc=info["meta_desc"],
                              h1=info["h1"], word_count=info["word_count"], gone=0)

            # ---- free intel from this page ----
            if res.get("html"):
                if acc_len < 250000:
                    acc_text.append(info.get("text", "")[:20000]); acc_len += 20000
                pr = intel.find_promos(info.get("text", ""))
                promo_terms.update(pr["terms"]); promo_coupons.update(pr["coupons"])
                if res["status"] and res["status"] >= 400:
                    broken.append({"url": pg["url"], "status": res["status"]})
                try:
                    jl = intel.parse_jsonld(BeautifulSoup(res["html"], "html.parser"))
                    for prod in intel.products_from_jsonld(jl, pg["url"]):
                        seen_products.add((prod["url"], prod["name"]))
                        pid, old, new = store.upsert_product(cid, prod)
                        if not baseline:
                            if old is None:
                                _record(comp, "product", f"New product: {prod['name']}"
                                         + (f" ({prod['currency']}{new})" if new else ""),
                                         url=pg["url"], page_id=pg["id"]); changes_found += 1
                            elif new and abs(new - (old or 0)) > 0.001:
                                _record(comp, "price",
                                         f"Price changed on “{prod['name']}”: {prod['currency']}{old} → {prod['currency']}{new}",
                                         detail=f"Before: {old}\nAfter:  {new}", url=pg["url"], page_id=pg["id"])
                                changes_found += 1
                except Exception:
                    pass
            time.sleep(delay)

        # ---- site-level intel (free pack) ----
        home_html = home.get("html", "") if "html" in home else ""
        e_home = extract(home_html) if home_html else {"text": "", "title": "", "meta_desc": "",
                                                       "h1": "", "word_count": 0, "canonical": "",
                                                       "images_no_alt": 0}
        big_text = " ".join(acc_text) or e_home.get("text", "")
        new_intel = dict(prev_intel) if prev_intel else {}
        new_intel.pop("_ts", None)
        try:
            new_intel["contacts"] = intel.extract_contacts(home_html, e_home.get("text", ""))
            new_intel["security"] = intel.security_grade(home.get("headers", {}))
            new_intel["ssl"] = intel.ssl_info(comp["domain"])
            new_intel["domain"] = intel.domain_age(comp["domain"])
            new_intel["seo"] = intel.seo_audit(e_home)
            new_intel["keyword_focus"] = intel.keyword_focus(big_text)
            new_intel["broken"] = broken[:50]
            new_intel["page_count"] = len(store.active_pages(cid))
        except Exception:
            import traceback
            traceback.print_exc()

        # feeds / new articles
        try:
            feeds = intel.discover_feeds(comp["base_url"], home_html)[:4]
            found_feed = []
            for fu in feeds:
                fr = fetch(fu, ua, timeout)
                if fr["ok"] and fr["html"] and ("<rss" in fr["html"].lower() or "<feed" in fr["html"].lower()
                                                or "<item" in fr["html"].lower()):
                    found_feed.append(fu)
                    for item in intel.parse_feed(fr["html"]):
                        is_new = store.add_feed_item(cid, item)
                        if is_new and not baseline:
                            _record(comp, "article", f"New post: {item.get('title') or item.get('link')}",
                                    url=item.get("link", ""))
                            changes_found += 1
                    break   # one working feed is enough
            new_intel["feeds"] = found_feed
        except Exception:
            pass

        # promotions
        promo = {"active": bool(promo_terms or promo_coupons),
                 "terms": sorted(promo_terms)[:12], "coupons": sorted(promo_coupons)[:8]}
        if not baseline:
            prev_terms = set((prev_intel.get("promo") or {}).get("terms", []))
            new_terms = [t for t in promo["terms"] if t not in prev_terms]
            if new_terms:
                _record(comp, "promo", "Promotion detected: " + ", ".join(new_terms[:4]),
                        detail="Terms: " + ", ".join(promo["terms"]) + (
                            "\nCoupons: " + ", ".join(promo["coupons"]) if promo["coupons"] else ""),
                        url=comp["base_url"])
                changes_found += 1
        new_intel["promo"] = promo

        # keyword alerts
        try:
            words = store.keywords(cid)
            low = big_text.lower()
            hits = sorted({w["word"] for w in words if w["word"].lower() in low})
            prev_hits = set(prev_intel.get("keyword_hits", []))
            for w in hits:
                if w not in prev_hits and not baseline:
                    _record(comp, "keyword", f"Keyword appeared: “{w}”", url=comp["base_url"])
                    changes_found += 1
            new_intel["keyword_hits"] = hits
        except Exception:
            pass

        if not baseline and seen_products:
            store.mark_products_seen(cid, seen_products)
        store.save_intel(cid, new_intel)

        if baseline:
            _record(comp, "new_page", f"Tracking started — baseline of {pages_checked} page(s) captured",
                    url=comp["base_url"])

        dur = int((time.time() - t0) * 1000)
        store.log_scan(cid, pages_checked, changes_found, dur, "ok")
        store.update_competitor(cid, status="ok", last_scan=time.time(), scan_error="")
        return {"ok": True, "pages_checked": pages_checked, "changes": changes_found,
                "duration_ms": dur}
    except Exception as e:
        import traceback
        traceback.print_exc()
        dur = int((time.time() - t0) * 1000)
        store.log_scan(cid, pages_checked, changes_found, dur, "error", str(e))
        store.update_competitor(cid, status="error", last_scan=time.time(), scan_error=str(e)[:300])
        return {"ok": False, "error": str(e), "pages_checked": pages_checked,
                "changes": changes_found}
