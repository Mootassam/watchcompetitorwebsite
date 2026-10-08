# RivalRadar — competitor intelligence & website-change monitor

Track your competitors' websites and get told the moment anything changes — new
pages, removed pages, content and SEO edits, price/stock moves, and the tools
they add or drop. Everything runs on your own PC. Nothing leaves this machine
except the requests RivalRadar makes to the public pages you ask it to watch.

```
python server.py   ->   http://127.0.0.1:5160
```

Data lives in `data\` (from source) or `%LOCALAPPDATA%\RivalRadar` (installed).

## What it watches

| Signal | What you get |
|---|---|
| **New / removed pages** | Discovered from the competitor's `sitemap.xml` (and sitemap index), with homepage links as a fallback. |
| **Content changes** | A real line-by-line diff of each page's visible text — see exactly what they added or removed. |
| **SEO changes** | Page title, meta description and H1 tracked over time. |
| **Price / stock watches** | Add a specific URL + a CSS selector (e.g. `.price`) to watch just one part of a page. |
| **Technology** | Detects CMS, ecommerce, analytics, ad pixels, JS frameworks, email tools, payments and CDN/server — and tells you when a competitor adds or drops one. |
| **HTTP status** | Catches pages going down or redirecting. |

## Alerts

- **In-app feed** — the Changes page, with filters, search and an unseen badge.
- **Webhooks** — a JSON `POST` to any URL (Zapier, Make, Slack, Discord, your own
  server) on every change, optionally signed with `X-RivalRadar-Signature`
  (HMAC-SHA256). Filter by event type per webhook.
- **Email** — optional, via your own SMTP account (Settings).

## How it behaves (safe & polite by default)

- Identifies itself with a clear User-Agent.
- Honours `robots.txt` (toggle in Settings).
- Rate-limits itself with a configurable delay between requests.
- Caps pages per site, hard timeouts on every request, and refuses to fetch
  private/loopback addresses.
- Automatic background scans on a schedule you choose (per competitor or global).

## Setup from source

```
pip install -r requirements.txt
python server.py
```

Requires Python 3.10+. Dependencies: Flask, requests, BeautifulSoup4.

## Notes on fair use

RivalRadar reads **public** pages, the same ones anyone can open in a browser. It
is for competitive research and monitoring your own market — not for copying a
competitor's content, branding or site wholesale. Watch the strategy; build your
own thing.
