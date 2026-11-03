import json, re
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

URL = "https://cinemastercard.az/en/"
out = Path("probe_out")
out.mkdir(exist_ok=True)
reqs = []      # bütün sorğular (şəkil/şrift/css xaric)
xhrs = []      # yalnız xhr/fetch cavabları


def on_request(req):
    try:
        if req.resource_type in ("image", "font", "stylesheet", "media"):
            return
        try:
            post = req.post_data
        except Exception:
            post = "<binary>"
        reqs.append({"type": req.resource_type, "method": req.method,
                     "url": req.url, "post": post})
    except Exception as e:
        print("on_request xətası:", e)


def on_response(resp):
    try:
        req = resp.request
        if req.resource_type not in ("xhr", "fetch"):
            return
        try:
            body = resp.text()
        except Exception:
            body = ""
        i = len(xhrs)
        ctype = resp.headers.get("content-type", "")
        ext = "json" if "json" in ctype else "html"
        fname = f"xhr_{i:02d}.{ext}"
        (out / fname).write_text(body, encoding="utf-8", errors="replace")
        try:
            post = req.post_data
        except Exception:
            post = "<binary>"
        xhrs.append({"i": i, "method": req.method, "url": resp.url, "post": post,
                     "status": resp.status, "content_type": ctype, "file": fname})
        print("XHR TUTULDU:", req.method, resp.status, resp.url, post or "")
    except Exception as e:
        print("on_response xətası:", e)


try:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False)
        page = b.new_page(locale="en-US", viewport={"width": 1400, "height": 900})
        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        print("Səhifə başlığı:", page.title())
        page.screenshot(path=str(out / "after_load.png"), full_page=True)
        (out / "page.html").write_text(page.content(), encoding="utf-8")

        for label in ("Tomorrow", "Today"):
            n0 = len(reqs)
            try:
                page.get_by_text(label, exact=True).first.click(timeout=10000)
                page.wait_for_timeout(5000)
                print(f"'{label}' kliklə yaranan yeni sorğu sayı:", len(reqs) - n0)
            except Exception as e:
                print("Klik alınmadı:", label, "->", str(e)[:150])

        page.screenshot(path=str(out / "after_click.png"), full_page=True)
        (out / "page_after.html").write_text(page.content(), encoding="utf-8")
        b.close()
except Exception as e:
    print("XƏTA:", repr(e))
finally:
    (out / "requests.json").write_text(json.dumps(reqs, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "xhr_log.json").write_text(json.dumps(xhrs, indent=1, ensure_ascii=False), encoding="utf-8")

print("\n== Bütün sorğular (şəkil/şrift/css xaric) ==")
for r in reqs:
    print(r["type"], r["method"], r["url"], r["post"] or "")

print("\n== XHR/fetch sorğuları ==")
for x in xhrs:
    print(x["method"], x["status"], x["url"], x["post"] or "", "->", x["file"])

# --- Koddakı endpoint axtarışı ---
page_file = out / "page.html"
if page_file.exists():
    html = page_file.read_text(encoding="utf-8")
    pat = re.compile(r"""["'](/?[A-Za-z0-9_\-/\.]*(?:ajax|session|schedule|seans|api|getdata)[A-Za-z0-9_\-/\.\?=&{}]*)["']""", re.I)
    found = set(pat.findall(html))
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
    cl = httpx.Client(headers={"User-Agent": "Mozilla/5.0 Chrome/120"}, timeout=30, follow_redirects=True)
    for s in srcs:
        if not s.startswith("http"):
            s = "https://cinemastercard.az" + (s if s.startswith("/") else "/" + s)
        if "cinemastercard.az" not in s:
            continue
        try:
            found |= set(pat.findall(cl.get(s).text))
        except Exception:
            pass
    print("\n== Koddakı ehtimal olunan endpoint-lər ==")
    for f in sorted(found):
        print(f)