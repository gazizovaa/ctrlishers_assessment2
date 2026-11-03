import json
import re
from datetime import date, timedelta
from pathlib import Path

from cinema_films import list_films, film_details
from cinema_sessions import get_sessions

DAYS = 1                      # neçə gün irəli seans çəkilsin (ilk test üçün 1 yazın)
OUT = Path("data/cinemaplus.json")

LANG_NAMES = {"Aze": "Azerbaijani", "Rus": "Russian", "Eng": "English", "Tur": "Turkish"}
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")


def norm(s):
    return re.sub(r"\W+", "", (s or "").lower())


def build_movies():
    movies, by_title = [], {}
    for i, f in enumerate(list_films(), 1):
        f = film_details(f)
        codes = f.get("language") or []
        m = {
            "id": f"M{i:03d}",
            "title": f["title"],
            "genre": [],                      # film səhifəsindən sonra doldurulacaq
            "language": LANG_NAMES.get(codes[0], codes[0]) if codes else "",
            "languages": [LANG_NAMES.get(c, c) for c in codes],
            "format": f.get("format", []),
            "duration_min": None,
            "age_rating": f.get("age_rating"),
            "rating": None,
            "synopsis": f.get("synopsis"),
            "poster": f.get("poster"),
            "url": f["url"],
        }
        movies.append(m)
        by_title[norm(f["title"])] = m
    return movies, by_title


def build_showtimes(by_title):
    cinemas, showtimes, unmatched = {}, [], set()
    for offset in range(DAYS):
        day = date.today() + timedelta(days=offset)
        rows = get_sessions(day.strftime("%d.%m.%Y"))
        if not isinstance(rows, list):
            print("Gözlənilməyən cavab formatı, cinema_sessions.py-ni yoxlayın:", type(rows))
            break
        for r in rows:
            movie = by_title.get(norm(r.get("movie")))
            if not movie:
                unmatched.add(r.get("movie"))
                continue
            cname = r.get("cinema") or "Unknown"
            c = cinemas.setdefault(cname, {"id": f"C{len(cinemas) + 1:02d}", "name": cname,
                                           "district": None, "address": None})
            for h, mnt in TIME_RE.findall(str(r.get("time", ""))):
                showtimes.append({
                    "id": f"S{len(showtimes) + 1:05d}",
                    "movie_id": movie["id"],
                    "cinema_id": c["id"],
                    "date": day.isoformat(),
                    "time": f"{int(h):02d}:{mnt}",
                    "hall": r.get("hall"),
                    "format": r.get("format"),
                    "price_azn": r.get("price_azn"),
                    "seats_total": None,
                    "seats_available": None,
                })
        print(day.isoformat(), "->", len(rows), "sətir")
    if unmatched:
        print("Filmlə uyğunlaşmayan adlar:", sorted(x for x in unmatched if x))
    return list(cinemas.values()), showtimes


def main():
    movies, by_title = build_movies()
    cinemas, showtimes = build_showtimes(by_title)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps({"movies": movies, "cinemas": cinemas, "showtimes": showtimes},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"Saxlandı: {len(movies)} film, {len(cinemas)} kinoteatr, {len(showtimes)} seans -> {OUT}")


if __name__ == "__main__":
    main()