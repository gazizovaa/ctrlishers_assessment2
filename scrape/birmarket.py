import argparse, json, os, re, time
import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://birmarket.az"
HEADERS = {"User-Agent": "Mozilla/5.0 (research project; visual search demo)"}

# Small, visually distinct categories work best for a visual-search demo.
CATEGORIES = {
    "Qol saatları": "2998-qol-saatlari",
    "Zinət əşyaları": "2324-zinyet-eshyalari",
    "Bəzəklər və bijuteriya": "2299-bezekler-ve-bijuteriya",
    "Geyim və ayaqqabı": "3003-geyim-ve-ayaqqabi",
    "Ev əşyaları": "937-ev-ve-bag-uchun-mehsullar",
    "Məişət texnikası": "106-meishet-texnikasi",
    "Telefonlar": "2-telefonlar-ve-aksessuarlar",
    "Uşaqlar üçün": "779-analar-ve-balalar-uchun",
}

session = requests.Session()
session.headers.update(HEADERS)


def get(url, **kw):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=25, **kw)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} {url}")
        except requests.RequestException as e:
            print(f"  retry {attempt+1}: {e}")
        time.sleep(2 * (attempt + 1))
    return None


def parse_price(text):
    # "12.90 ₼ 25.00 ₼" -> first number is the current price; "1 207.79 ₼" uses a space as thousands separator
    nums = re.findall(r"(\d[\d\s ]*\.\d{2})\s*₼", text)
    vals = [float(n.replace(" ", "").replace(" ", "")) for n in nums]
    return (vals[0] if vals else None), (vals[1] if len(vals) > 1 else None)


def listing(category_slug, page):
    url = f"{BASE}/categories/{category_slug}" + (f"?page={page}" if page > 1 else "")
    r = get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    items, seen = [], set()
    for a in soup.select('a[href*="/product/"]'):
        href = a["href"].split("?")[0]
        if not href.startswith("http"):
            href = BASE + href
        m = re.search(r"/product/(\d+)-", href)
        if not m or href in seen:
            continue
        seen.add(href)
        price, old_price = parse_price(a.get_text(" ", strip=True))
        items.append({"id": int(m.group(1)), "url": href, "price_azn": price, "old_price_azn": old_price})
    return items


def product_page(url):
    r = get(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    def meta(prop):
        t = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return t["content"].strip() if t and t.get("content") else None

    title = meta("og:title") or (soup.title.string if soup.title else "")
    image = meta("og:image")
    crumbs = [a.get_text(strip=True) for a in soup.select('a[href*="/categories/"]')]
    crumbs = [c for c in dict.fromkeys(crumbs) if c and c.lower() not in ("kateqoriyalar", "bütün kateqoriyalar")]
    # use the larger 840px variant when the og:image points at the 280px one
    if image:
        image = image.replace("/img/product/280/", "/img/product/840/")
    return {"name": title, "image_url": image, "subcategory": crumbs[-1] if crumbs else None}


def download(url, path):
    r = get(url)
    if not r or not r.headers.get("content-type", "").startswith("image"):
        return False
    with open(path, "wb") as f:
        f.write(r.content)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=40)
    ap.add_argument("--out", default="data")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    os.makedirs(f"{args.out}/images", exist_ok=True)
    rows = []
    for cat_name, slug in CATEGORIES.items():
        print(f"== {cat_name}")
        collected, page = [], 1
        while len(collected) < args.per_category and page <= 10:
            found = listing(slug, page)
            if not found:
                break
            collected += found
            page += 1
            time.sleep(args.delay)
        for it in collected[: args.per_category]:
            info = product_page(it["url"])
            time.sleep(args.delay)
            if not info or not info["image_url"]:
                continue
            img_path = f"{args.out}/images/{it['id']}.jpg"
            if not os.path.exists(img_path) and not download(info["image_url"], img_path):
                continue
            rows.append({**it, **info, "category": cat_name, "image_file": img_path})
            print(f"  ok {it['id']} {info['name'][:60]}")
            time.sleep(args.delay)

    df = pd.DataFrame(rows).drop_duplicates("id")
    df.to_json(f"{args.out}/birmarket.json", orient="records", force_ascii=False, indent=2)
    print(f"Saved {len(df)} products")


if __name__ == "__main__":
    main()