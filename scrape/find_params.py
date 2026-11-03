"""
find_params.py

1) Saytın JS kodunda seans endpoint-lərinin çağırıldığı yerləri tapıb probe_out/params_context.txt-ə yazır
   (tarix hansı adla və GET/POST ilə göndərilir, burada görünəcək).
2) Bir neçə ehtimal olunan sorğu variantını sınayıb cavabları probe_out/try_N.txt-ə yazır.

İşə salmaq: python find_params.py
"""
import re
from pathlib import Path

import httpx

BASE = "https://cinemastercard.az"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
out = Path("probe_out")
out.mkdir(exist_ok=True)

cl = httpx.Client(headers=H, timeout=30, follow_redirects=True)

# --- 1) Səhifəni və JS fayllarını yüklə
home = cl.get(BASE + "/en/")
html = home.text
sources = {"inline/page": html}
for s in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html):
    url = s if s.startswith("http") else BASE + (s if s.startswith("/") else "/" + s)
    if "cinemastercard.az" in url:
        try:
            sources[url] = cl.get(url).text
        except Exception as e:
            print("Yüklənmədi:", url, e)

KEYS = ("get_sessions_by_date", "getSessionsDates", "getSessions.php", "session_info")
lines = []
for key in KEYS:
    count = 0
    for name, text in sources.items():
        for m in re.finditer(re.escape(key), text):
            if count >= 3:
                break
            a = max(0, m.start() - 400)
            b = min(len(text), m.end() + 600)
            lines.append("=" * 90)
            lines.append(f"{key}  |  {name}")
            lines.append(text[a:b])
            count += 1
(out / "params_context.txt").write_text("\n".join(lines), encoding="utf-8")
print("JS kontekst yazıldı: probe_out/params_context.txt  (tapılan hissə sayı:", sum(1 for l in lines if l.startswith("=" * 10)), ")")

# --- 2) Ehtimal olunan sorğu variantları
xhr_headers = {"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/en/"}
tries = [
    ("GET dates", "GET", "/getSessionsDates.php", {}, None),
    ("GET date=dd.mm.yyyy", "GET", "/get_sessions_by_date.php", {"home": "yes", "lang": "en", "date": "03.11.2026"}, None),
    ("GET date=yyyy-mm-dd", "GET", "/get_sessions_by_date.php", {"home": "yes", "lang": "en", "date": "2026-11-03"}, None),
    ("POST date=dd.mm.yyyy", "POST", "/get_sessions_by_date.php?home=yes&lang=en", {}, {"date": "03.11.2026"}),
    ("POST date=yyyy-mm-dd", "POST", "/get_sessions_by_date.php?home=yes&lang=en", {}, {"date": "2026-11-03"}),
]
for i, (label, method, path, params, data) in enumerate(tries):
    try:
        r = cl.request(method, BASE + path, params=params or None, data=data, headers=xhr_headers)
        body = r.text
        (out / f"try_{i}.txt").write_text(
            f"{label}\n{method} {r.url}\nstatus={r.status_code} content-type={r.headers.get('content-type')}\n\n{body}",
            encoding="utf-8",
        )
        print(f"[{i}] {label}: status={r.status_code} uzunluq={len(body)} -> {body[:150]!r}")
    except Exception as e:
        print(f"[{i}] {label}: XƏTA {e!r}")