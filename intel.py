"""
Free intelligence extractors for RivalRadar — everything computed from the public
pages we already fetch, with no API keys or paid data feeds:

  products_from_jsonld  prices + ratings from embedded schema.org data
  find_promos           sale / discount / coupon detection
  extract_contacts      emails, phones and social profiles
  security_grade        security-header score
  ssl_info / domain_age TLS cert + registration age (socket + free RDAP)
  discover_feeds/parse_feed   RSS/Atom new-article tracking
  seo_audit             on-page SEO issues
  keyword_focus         the terms a site pushes most

All functions are defensive: bad input returns empty/neutral results, never raises.
"""

from __future__ import annotations

import json
import re
import socket
import ssl as _ssl
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

_rdap_cache: dict[str, dict] = {}
_ssl_cache: dict[str, dict] = {}


# --------------------------------------------------------------------------- #
#  structured data (schema.org JSON-LD) -> products / prices / ratings
# --------------------------------------------------------------------------- #
def parse_jsonld(soup: BeautifulSoup) -> list:
    out = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))  # trailing commas
            except Exception:
                continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict):
                if "@graph" in it and isinstance(it["@graph"], list):
                    out.extend(x for x in it["@graph"] if isinstance(x, dict))
                else:
                    out.append(it)
    return out


def _types(node) -> set:
    t = node.get("@type", "")
    if isinstance(t, list):
        return {str(x).lower() for x in t}
    return {str(t).lower()}


def _num(v):
    if v is None:
        return None
    try:
        s = re.sub(r"[^\d.,]", "", str(v))
        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s and re.search(r",\d{2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
        return round(float(s), 2) if s else None
    except Exception:
        return None


def _offer_price(offers):
    """Return (price, currency, availability) from an offer / list / aggregate."""
    if not offers:
        return None, "", ""
    if isinstance(offers, list):
        for o in offers:
            p, c, a = _offer_price(o)
            if p is not None:
                return p, c, a
        return None, "", ""
    if isinstance(offers, dict):
        price = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
        cur = offers.get("priceCurrency") or ""
        avail = (offers.get("availability") or "").split("/")[-1]
        spec = offers.get("priceSpecification")
        if price is None and isinstance(spec, dict):
            price = spec.get("price")
            cur = cur or spec.get("priceCurrency", "")
        return _num(price), cur, avail
    return None, "", ""


def products_from_jsonld(jsonld: list, page_url: str) -> list:
    out = []
    for node in jsonld:
        if not isinstance(node, dict) or "product" not in _types(node):
            continue
        name = node.get("name") or ""
        if isinstance(name, dict):
            name = name.get("@value", "")
        price, cur, avail = _offer_price(node.get("offers"))
        rating = rc = None
        agg = node.get("aggregateRating")
        if isinstance(agg, dict):
            rating = _num(agg.get("ratingValue"))
            try:
                rc = int(float(re.sub(r"[^\d.]", "", str(agg.get("reviewCount") or agg.get("ratingCount") or 0)) or 0))
            except Exception:
                rc = None
        if name and (price is not None or rating is not None):
            out.append({"name": str(name)[:200], "price": price or 0, "currency": (cur or "")[:8],
                        "availability": (avail or "")[:40], "rating": rating or 0,
                        "review_count": rc or 0, "url": page_url})
    return out


# --------------------------------------------------------------------------- #
#  promotions / sales
# --------------------------------------------------------------------------- #
_PROMO_RE = re.compile(
    r"\b(\d{1,3}\s*%\s*off|save\s+\d{1,3}\s*%|save\s+[$£€]\s?\d+|up to\s+\d{1,3}\s*%|"
    r"free shipping|free delivery|black friday|cyber monday|clearance|"
    r"flash sale|limited time|ends (?:today|tonight|soon)|"
    r"(?:use )?(?:code|coupon|promo)\s*:?\s*[A-Z0-9]{3,12}|"
    r"buy one get one|bogo|\bsale\b|\bdeal\b|discount)\b", re.I)
_COUPON_RE = re.compile(r"(?:code|coupon|promo)\s*:?\s*([A-Z0-9]{3,14})", re.I)


def find_promos(text: str) -> dict:
    text = text or ""
    terms = sorted({m.group(0).strip().lower() for m in _PROMO_RE.finditer(text)})[:12]
    coupons = sorted({m.group(1) for m in _COUPON_RE.finditer(text)})[:8]
    return {"active": bool(terms or coupons), "terms": terms, "coupons": coupons}


# --------------------------------------------------------------------------- #
#  contacts + socials
# --------------------------------------------------------------------------- #
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:(?:\+\d{1,3}[\s.-]?)?(?:\(\d{1,4}\)[\s.-]?)?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4})")
_SOCIAL = {
    "facebook": r"facebook\.com/(?!sharer|tr\?)([^\"'/?]+)",
    "instagram": r"instagram\.com/([^\"'/?]+)",
    "twitter": r"(?:twitter|x)\.com/(?!intent|share)([^\"'/?]+)",
    "linkedin": r"linkedin\.com/(company|in)/([^\"'/?]+)",
    "youtube": r"youtube\.com/(channel/[^\"'/?]+|@[^\"'/?]+|c/[^\"'/?]+|user/[^\"'/?]+)",
    "tiktok": r"tiktok\.com/(@[^\"'/?]+)",
    "pinterest": r"pinterest\.[a-z.]+/([^\"'/?]+)",
}


def extract_contacts(html: str, text: str) -> dict:
    html = html or ""
    emails = sorted({e.lower() for e in _EMAIL_RE.findall(text or "")
                     if not re.search(r"\.(png|jpg|jpeg|gif|webp|svg)$", e, re.I)})[:15]
    phones = []
    for m in _PHONE_RE.findall(text or ""):
        digs = re.sub(r"\D", "", m)
        if 7 <= len(digs) <= 15:
            phones.append(m.strip())
    phones = sorted(set(phones))[:8]
    socials = {}
    for plat, rx in _SOCIAL.items():
        m = re.search(rx, html, re.I)
        if m:
            handle = m.group(0)
            socials[plat] = "https://" + handle if not handle.startswith("http") else handle
    return {"emails": emails, "phones": phones, "socials": socials}


# --------------------------------------------------------------------------- #
#  security headers
# --------------------------------------------------------------------------- #
_SEC_HEADERS = [
    ("strict-transport-security", "HSTS"), ("content-security-policy", "CSP"),
    ("x-frame-options", "X-Frame-Options"), ("x-content-type-options", "X-Content-Type-Options"),
    ("referrer-policy", "Referrer-Policy"), ("permissions-policy", "Permissions-Policy"),
]


def security_grade(headers: dict) -> dict:
    headers = headers or {}
    present = [label for key, label in _SEC_HEADERS if key in headers]
    missing = [label for key, label in _SEC_HEADERS if key not in headers]
    pct = round(len(present) / len(_SEC_HEADERS) * 100)
    grade = "A" if pct >= 85 else "B" if pct >= 65 else "C" if pct >= 45 else "D" if pct >= 20 else "F"
    return {"score": pct, "grade": grade, "present": present, "missing": missing}


# --------------------------------------------------------------------------- #
#  TLS cert + domain age
# --------------------------------------------------------------------------- #
def ssl_info(domain: str) -> dict:
    if domain in _ssl_cache and _ssl_cache[domain].get("_t", 0) > time.time() - 86400:
        return _ssl_cache[domain]
    info = {"ok": False}
    try:
        ctx = _ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ss:
                cert = ss.getpeercert()
        exp = cert.get("notAfter")
        issuer = dict(x[0] for x in cert.get("issuer", [])).get("organizationName", "")
        days = None
        if exp:
            end = datetime.strptime(exp, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (end - datetime.now(timezone.utc)).days
        info = {"ok": True, "issuer": issuer, "expires": exp, "days_left": days}
    except Exception as e:
        info = {"ok": False, "error": str(e)[:80]}
    info["_t"] = time.time()
    _ssl_cache[domain] = info
    return info


def domain_age(domain: str) -> dict:
    if domain in _rdap_cache and _rdap_cache[domain].get("_t", 0) > time.time() - 7 * 86400:
        return _rdap_cache[domain]
    info = {"ok": False}
    try:
        r = requests.get(f"https://rdap.org/domain/{domain}",
                         headers={"User-Agent": "RivalRadar/1.0"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            created = None
            for ev in data.get("events", []):
                if ev.get("eventAction") == "registration":
                    created = ev.get("eventDate")
                    break
            age_days = None
            if created:
                try:
                    c = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - c).days
                except Exception:
                    pass
            info = {"ok": True, "created": created, "age_days": age_days,
                    "registrar": _rdap_registrar(data)}
    except Exception as e:
        info = {"ok": False, "error": str(e)[:80]}
    info["_t"] = time.time()
    _rdap_cache[domain] = info
    return info


def _rdap_registrar(data):
    for ent in data.get("entities", []):
        if "registrar" in (ent.get("roles") or []):
            for v in ent.get("vcardArray", [[], []])[1]:
                if v and v[0] == "fn":
                    return v[3]
    return ""


# --------------------------------------------------------------------------- #
#  feeds (RSS / Atom)
# --------------------------------------------------------------------------- #
def discover_feeds(base_url: str, html: str) -> list:
    feeds = []
    soup = BeautifulSoup(html or "", "html.parser")
    for link in soup.find_all("link", attrs={"rel": re.compile("alternate", re.I)}):
        t = (link.get("type") or "").lower()
        if "rss" in t or "atom" in t or "xml" in t:
            feeds.append(urljoin(base_url, link.get("href", "")))
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    for g in ("/feed", "/rss", "/feed.xml", "/rss.xml", "/blog/feed", "/atom.xml"):
        feeds.append(root + g)
    return list(dict.fromkeys(f for f in feeds if f))


def parse_feed(xml: str) -> list:
    out = []
    try:
        soup = BeautifulSoup(xml or "", "xml")
    except Exception:
        soup = BeautifulSoup(xml or "", "html.parser")
    entries = soup.find_all("item") or soup.find_all("entry")
    for e in entries[:30]:
        title = (e.find("title").get_text(strip=True) if e.find("title") else "")[:300]
        link = ""
        lk = e.find("link")
        if lk:
            link = lk.get("href") or lk.get_text(strip=True) or ""
        guid = (e.find("guid") or e.find("id"))
        guid = guid.get_text(strip=True) if guid else (link or title)
        pub = (e.find("pubDate") or e.find("published") or e.find("updated"))
        ts = 0
        if pub:
            ts = _parse_date(pub.get_text(strip=True))
        if title or link:
            out.append({"guid": guid[:300], "title": title, "link": link[:500], "published": ts})
    return out


def _parse_date(s: str) -> float:
    s = (s or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
#  SEO audit + keyword focus
# --------------------------------------------------------------------------- #
def seo_audit(info: dict) -> dict:
    issues = []
    tl = len(info.get("title") or "")
    ml = len(info.get("meta_desc") or "")
    if not info.get("title"):
        issues.append(("error", "Missing page title"))
    elif tl < 20:
        issues.append(("warn", f"Title is short ({tl} chars)"))
    elif tl > 65:
        issues.append(("warn", f"Title may be truncated in search ({tl} chars)"))
    if not info.get("meta_desc"):
        issues.append(("warn", "Missing meta description"))
    elif ml > 160:
        issues.append(("warn", f"Meta description is long ({ml} chars)"))
    if not info.get("h1"):
        issues.append(("warn", "No H1 heading"))
    if info.get("images_no_alt"):
        issues.append(("warn", f"{info['images_no_alt']} image(s) missing alt text"))
    if info.get("word_count", 0) < 100:
        issues.append(("warn", f"Thin content ({info.get('word_count', 0)} words)"))
    if not info.get("canonical"):
        issues.append(("info", "No canonical tag"))
    return {"title_len": tl, "meta_len": ml, "issues": issues,
            "score": max(0, 100 - sum(20 if s == "error" else 10 if s == "warn" else 3 for s, _ in issues))}


_STOP = set("the a an and or but of to in on for with at by from up about into over after is are "
            "was were be been being this that these those it its as your you our we they their his her "
            "will can all more most other some such no not only own same so than too very s t".split())


def keyword_focus(text: str, top: int = 20) -> list:
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", (text or "").lower())
    freq = {}
    for w in words:
        if w in _STOP or len(w) < 3:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: -x[1])[:top]
    return [{"term": w, "n": n} for w, n in ranked if n > 2]
