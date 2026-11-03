import os, json, time, itertools, requests
from datetime import date, timedelta

TOKEN = os.environ["TRAVELPAYOUTS_TOKEN"]          # export TRAVELPAYOUTS_TOKEN=...
URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
ORIGINS = ["GYD"]                                   # extend as needed
DESTINATIONS = ["IST", "DXB", "MOW", "TBS", "LON", "FRA"]
CITY = {"GYD": "Baku", "IST": "Istanbul", "DXB": "Dubai", "MOW": "Moscow",
        "TBS": "Tbilisi", "LON": "London", "FRA": "Frankfurt"}
DAYS_AHEAD = 30
START = date(2026, 11, 2)                           # reference date from the brief


def fetch(origin, dest, day):
    params = {"origin": origin, "destination": dest, "departure_at": day.isoformat(),
              "one_way": "true", "currency": "azn", "limit": 30,
              "sorting": "price", "token": TOKEN}
    for attempt in range(3):
        try:
            r = requests.get(URL, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(2 ** attempt); continue
            r.raise_for_status()
            return r.json().get("data", [])
        except requests.RequestException as e:
            print(f"[warn] {origin}-{dest} {day}: {e}")
            time.sleep(2 ** attempt)
    return []


def to_schema(o, i):
    dep = o["departure_at"][:16]
    dur = o.get("duration_to") or o.get("duration") or 0
    return {
        "id": f"F{i:04d}",
        "airline": o.get("airline"),
        "flight_number": f'{o.get("airline", "")}{o.get("flight_number", "")}',
        "origin": {"code": o["origin"], "city": CITY.get(o["origin"], o["origin"])},
        "destination": {"code": o["destination"], "city": CITY.get(o["destination"], o["destination"])},
        "departure_local": dep,
        "arrival_local": None,                      # not provided by this endpoint
        "duration_min": dur,
        "stops": o.get("transfers", 0),
        "via": None,
        "price_azn": float(o["price"]),
        "cabin": "economy",
        "baggage_kg": None,                         # not provided
        "seats_available": None,                    # not provided
        "link": "https://www.aviasales.com" + o.get("link", ""),
    }


def main():
    seen, flights, i = set(), [], 1
    for (org, dst), d in itertools.product(itertools.product(ORIGINS, DESTINATIONS),
                                           range(DAYS_AHEAD)):
        day = START + timedelta(days=d)
        for o in fetch(org, dst, day):
            key = (o["origin"], o["destination"], o["departure_at"], o.get("flight_number"))
            if key in seen: continue
            seen.add(key); flights.append(to_schema(o, i)); i += 1
        time.sleep(0.3)                             # be polite
    with open("data/aviasales.json", "w", encoding="utf-8") as f:
        json.dump(flights, f, ensure_ascii=False, indent=1)
    print(f"Saved {len(flights)} flights")


if __name__ == "__main__":
    main()