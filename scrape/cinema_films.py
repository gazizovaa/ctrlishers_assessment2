import re, json, time
import httpx
from bs4 import BeautifulSoup

BASE = "https://cinemastercard.az"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36",
     "Accept-Language": "en-US,en;q=0.9"}
client = httpx.Client(headers=H, timeout=30, follow_redirects=True)

def card_of(h2):
    node = h2
    while node.parent is not None and len(node.parent.find_all("h2")) == 1:
        node = node.parent
    return node

def list_films():
    r = client.get(BASE + "/en/")
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    films, seen = [], set()
    for h2 in soup.find_all("h2"):
        a = h2.find("a", href=re.compile(r"/en/films/[^/]+/?$"))
        if not a or a["href"] in seen:
            continue
        seen.add(a["href"])
        text = card_of(h2).get_text(" ", strip=True)
        age = re.search(r"(\d+)\+", text)
        films.append({
            "title": a.get_text(strip=True),
            "url": a["href"] if a["href"].startswith("http") else BASE + a["href"],
            "age_rating": age.group(1) + "+" if age else None,
            "language": sorted(set(re.findall(r"Movie language:\s*(\w+)", text))),
            "format": sorted(set(re.findall(r"Movie format:\s*(\w+)", text))),
        })
    return films

def film_details(f):
    r = client.get(f["url"])
    soup = BeautifulSoup(r.text, "lxml")
    og = lambda p: (soup.find("meta", property=p) or {}).get("content")
    f["synopsis"] = og("og:description")
    f["poster"] = og("og:image")
    time.sleep(1.0)
    return f

if __name__ == "__main__":
    films = [film_details(f) for f in list_films()]
    for i, f in enumerate(films, 1):
        f["id"] = f"M{i:03d}"
    json.dump(films, open("data/films_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(films), "film")