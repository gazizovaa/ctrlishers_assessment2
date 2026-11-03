import re
from pathlib import Path

from bs4 import BeautifulSoup

from cinema_films import client, BASE

ENDPOINT = BASE + "/get_sessions_by_date.php"
LANG = "en"
DATE_FORMATS = ["%d.%m.%Y", "%Y-%m-%d"]      # tarix formatı sınaq qaydası ilə seçilir
_working_format = None                        # işləyən format tapılanda yadda saxlanır

PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def _fetch(date_obj):
    """Tarix üçün xam HTML qaytarır. Format seçimini avtomatik edir."""
    global _working_format
    formats = [_working_format] if _working_format else DATE_FORMATS
    last = ""
    for fmt in formats:
        r = client.get(
            ENDPOINT,
            params={"home": "yes", "lang": LANG, "datex": date_obj.strftime(fmt)},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/en/"},
        )
        if r.status_code != 200:
            last = r.text
            continue
        _working_format = fmt
        return r.text
    print("Server xəta qaytardı, sonuncu cavab:", last[:200])
    return ""


def parse_rows(html):
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        cells = [td.get_text(" ", strip=True) for td in tds]
        movie, sessions, cinema_name, hall, fmt, price = cells[:6]
        pm = PRICE_RE.search(price)

        # data-* atributları (seans id, kinoteatr id və s.) varsa saxla
        attrs = {}
        for el in [tr] + tr.find_all(True):
            for k, v in el.attrs.items():
                if str(k).startswith("data-"):
                    attrs.setdefault(k, []).append(v if isinstance(v, str) else " ".join(v))

        rows.append({
            "movie": movie,
            "time": sessions,
            "cinema": cinema_name,
            "hall": hall,
            "format": fmt,
            "price_azn": float(pm.group(1).replace(",", ".")) if pm else None,
            "attrs": attrs,
        })
    return rows


def get_sessions(date_ddmmyyyy, cinema=None):
    """build üçün interfeys: 'dd.mm.yyyy' qəbul edir, sətir siyahısı qaytarır."""
    from datetime import datetime
    d = datetime.strptime(date_ddmmyyyy, "%d.%m.%Y")
    html = _fetch(d)
    rows = parse_rows(html)
    if cinema:
        rows = [r for r in rows if cinema.lower() in r["cinema"].lower()]
    return rows


if __name__ == "__main__":
    from datetime import date

    today = date.today()
    html = _fetch(today)
    Path("probe_out").mkdir(exist_ok=True)
    Path("probe_out/sessions_raw.html").write_text(html, encoding="utf-8")
    print("Seçilən tarix formatı:", _working_format)
    print("Cavab uzunluğu:", len(html), "simvol")
    rows = parse_rows(html)
    print("Sətir sayı:", len(rows))
    for r in rows[:8]:
        print({k: v for k, v in r.items() if k != "attrs"})
    if not rows:
        print("Sətir tapılmadı. Ya həmin gün seans yoxdur, ya da HTML strukturu fərqlidir.")
        print("probe_out/sessions_raw.html faylının ilk hissəsini mənə göndərin.")