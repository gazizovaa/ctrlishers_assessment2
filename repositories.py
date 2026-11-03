import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

_FOLD = str.maketrans({"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ş": "s", "ç": "c", "ğ": "g", "ё": "е"})


def normalize_text(text: Any) -> str:
    """Lower-case and fold Azerbaijani letters so 'QULAQLIQ', 'qulaqlıq' and
    'Qulaqliq' compare equal (handles the İ/I problem)."""
    return str(text or "").replace("İ", "i").lower().translate(_FOLD)


def _tokens(text: str) -> List[str]:
    toks = re.findall(r"\w+", normalize_text(text))
    return [t[:-1] if len(t) > 3 and t.endswith("s") else t for t in toks]  # crude plural strip


class DataSourceError(Exception):
    """Raised when a data source is missing or corrupt."""


class BaseRepository:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.data: List[Dict[str, Any]] = self._load_data()

    def _load_data(self) -> List[Dict[str, Any]]:
        if not self.filepath.exists():
            raise DataSourceError(f"Data file not found: {self.filepath}")
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise DataSourceError(f"Invalid JSON in {self.filepath}: {e}") from e
        if not isinstance(data, list):
            raise DataSourceError(f"{self.filepath} must contain a JSON list")
        return data

    def get_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        if not item_id:
            return None
        return next((i for i in self.data if str(i.get("id", "")).upper() == str(item_id).upper()), None)


class FlightRepository(BaseRepository):
    def __init__(self, filepath="flights.json"):
        super().__init__(filepath)

    @staticmethod
    def _place_match(query: str, place: Optional[Dict[str, Any]]) -> bool:
        place = place or {}
        q = normalize_text(query).strip()
        return q == str(place.get("code", "")).lower() or q in normalize_text(place.get("city", ""))

    def search_flights(
        self,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        date: Optional[str] = None,
        max_stops: Optional[int] = None,
        max_price: Optional[float] = None,
        airline: Optional[str] = None,
        sort_by: Optional[str] = None,
        cabin: Optional[str] = None,
        departure_after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for f in self.data:
            if origin and not self._place_match(origin, f.get("origin")):
                continue
            if destination and not self._place_match(destination, f.get("destination")):
                continue
            dep = str(f.get("departure_local", ""))
            if date and not dep.startswith(date):
                continue
            if max_stops is not None and f.get("stops", 0) > max_stops:
                continue
            if max_price is not None and f.get("price_azn", float("inf")) > max_price:
                continue
            if airline and normalize_text(airline) not in normalize_text(f.get("airline", "")):
                continue
            if cabin and cabin.lower() != str(f.get("cabin", "")).lower():
                continue
            if departure_after and dep[11:16] < departure_after:
                continue
            results.append(f)

        if sort_by == "price":
            results.sort(key=lambda x: x.get("price_azn", float("inf")))
        elif sort_by == "duration":
            results.sort(key=lambda x: x.get("duration_min", float("inf")))
        elif sort_by == "departure":
            results.sort(key=lambda x: str(x.get("departure_local", "")))
        return results

    def update_seats(self, flight_id: str, count: int) -> bool:
        flight = self.get_by_id(flight_id)
        if count > 0 and flight and flight.get("seats_available", 0) >= count:
            flight["seats_available"] -= count
            return True
        return False

    def cities(self) -> Dict[str, str]:
        out = {}
        for f in self.data:
            for side in ("origin", "destination"):
                city = (f.get(side) or {}).get("city")
                if city:
                    out[normalize_text(city)] = city
        return out

    def codes(self) -> Dict[str, str]:
        out = {}
        for f in self.data:
            for side in ("origin", "destination"):
                p = f.get(side) or {}
                if p.get("code") and p.get("city"):
                    out[p["code"].lower()] = p["city"]
        return out

    def airlines(self) -> List[str]:
        return sorted({f["airline"] for f in self.data if f.get("airline")})

    def vocabulary(self) -> List[str]:
        return self.airlines()


class ProductRepository(BaseRepository):
    def __init__(self, filepath="products.json"):
        super().__init__(filepath)
        
        # --- VISUAL SEARCH SETUP ---
        self.embeddings_path = self.filepath.parent.parent / "data" / "product_embeddings.json"
        self.has_visual_search = False
        
        if self.embeddings_path.exists() and os.environ.get("NVIDIA_API_KEY"):
            try:
                with open(self.embeddings_path, "r", encoding="utf-8") as f:
                    db = json.load(f)
                self.embed_model = db["model"]
                self.embed_products = db["products"]
                self.embed_matrix = np.array([p["embedding"] for p in self.embed_products], dtype=np.float32)
                self.nvidia_client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=os.environ["NVIDIA_API_KEY"])
                self.has_visual_search = True
            except Exception as e:
                logger.warning(f"Failed to load visual search resources: {e}")

    @staticmethod
    def _haystack(p: Dict[str, Any]) -> str:
        names = p.get("name") or {}
        names = " ".join(names.values()) if isinstance(names, dict) else str(names)
        parts = [names, p.get("description", ""), p.get("category", ""), p.get("brand", ""), p.get("color", "")]
        return normalize_text(" ".join(str(x) for x in parts))

    def search_by_image(self, image_path: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Find products similar to the uploaded image using Nvidia embeddings."""
        if not self.has_visual_search:
            return []
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            r = self.nvidia_client.embeddings.create(
                model=self.embed_model, encoding_format="float",
                input=[f"data:image/jpeg;base64,{b64}"],
                extra_body={"input_type": "passage", "modality": "image"}
            )
            v = np.array(r.data[0].embedding, dtype=np.float32)
            q = v / np.linalg.norm(v)
            
            sims = self.embed_matrix @ q
            order = np.argsort(-sims)
            
            results = []
            for i in order[:top_k]:
                pid = str(self.embed_products[i]["id"])
                if not pid.startswith("P"):
                    pid = f"P{int(pid):03d}"
                prod = self.get_by_id(pid)
                if prod:
                    results.append(prod)
            return results
        except Exception as e:
            logger.error(f"Visual search failed: {e}")
            return []

    def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        max_price: Optional[float] = None,
        color: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        qtoks = _tokens(query) if query else []
        results = []
        for p in self.data:
            if category and normalize_text(p.get("category")) != normalize_text(category):
                continue
            if brand and normalize_text(p.get("brand")) != normalize_text(brand):
                continue
            if max_price is not None and p.get("price_azn", float("inf")) > max_price:
                continue
            if color and normalize_text(p.get("color")) != normalize_text(color):
                continue
            if qtoks:
                hay = self._haystack(p)
                if not all(t in hay for t in qtoks):  # every word must match, order-independent
                    continue
            results.append(p)
        return results

    def update_stock(self, prod_id: str, count: int) -> bool:
        prod = self.get_by_id(prod_id)
        if count > 0 and prod and prod.get("stock", 0) >= count:
            prod["stock"] -= count
            return True
        return False

    def brands(self) -> List[str]:
        return sorted({p["brand"] for p in self.data if p.get("brand")})

    def colors(self) -> List[str]:
        return sorted({p["color"] for p in self.data if p.get("color")})

    def vocabulary(self) -> List[str]:
        words = set()
        for p in self.data:
            names = p.get("name") or {}
            for n in (names.values() if isinstance(names, dict) else [str(names)]):
                words.update(w for w in re.findall(r"\w+", normalize_text(n)) if len(w) >= 4)
            for key in ("category", "brand"):
                if p.get(key):
                    words.add(normalize_text(p[key]))
        return sorted(words)


class CinemaRepository:
    def __init__(self, movies_path="movies.json", cinemas_path="cinemas.json", showtimes_path="showtimes.json"):
        self.movies = BaseRepository(movies_path).data
        self.cinemas = BaseRepository(cinemas_path).data
        self.showtimes = BaseRepository(showtimes_path).data

    @staticmethod
    def _genres_of(m: Dict[str, Any]) -> List[str]:
        g = m.get("genre", [])
        return [g] if isinstance(g, str) else list(g)

    @staticmethod
    def _gnorm(s: str) -> str:
        return normalize_text(s).replace("-", "").replace(" ", "")

    def _cinema(self, cinema_id) -> Dict[str, Any]:
        return next((c for c in self.cinemas if c.get("id") == cinema_id), {})

    def search_movies(self, genre=None, language=None, date=None, min_rating=None) -> List[Dict[str, Any]]:
        on_date = {st["movie_id"] for st in self.showtimes if st.get("date") == date} if date else None
        results = []
        for m in self.movies:
            if genre and not any(self._gnorm(genre) in self._gnorm(g) for g in self._genres_of(m)):
                continue
            if language and normalize_text(language) not in normalize_text(m.get("language", "")):
                continue
            if min_rating is not None and m.get("rating", 0) < min_rating:
                continue
            if on_date is not None and m.get("id") not in on_date:
                continue
            results.append(m)
        return results

    def get_movie_by_id(self, movie_identifier: str, fuzzy: bool = True) -> Optional[Dict[str, Any]]:
        exact = next((m for m in self.movies if str(m.get("id", "")).upper() == movie_identifier.upper()), None)
        if exact or not fuzzy or len(movie_identifier) < 3:
            return exact
        return next((m for m in self.movies if movie_identifier.lower() in str(m.get("title", "")).lower()), None)

    def find_movie_in_text(self, text: str) -> Optional[Dict[str, Any]]:
        t = normalize_text(text)
        hits = [m for m in self.movies if len(str(m.get("title", ""))) >= 3 and normalize_text(m["title"]) in t]
        return max(hits, key=lambda m: len(m["title"])) if hits else None

    def get_showtimes_for_movie(self, movie_id, date=None, time=None, after=None) -> List[Dict[str, Any]]:
        results = []
        for st in self.showtimes:
            if str(st.get("movie_id", "")).upper() != movie_id.upper():
                continue
            if date and st.get("date") != date:
                continue
            if time and not str(st.get("time", "")).startswith(time):
                continue
            if after and str(st.get("time", "")) < after:
                continue
            results.append({**st, "cinema": self._cinema(st.get("cinema_id"))})
        results.sort(key=lambda s: (s.get("date", ""), s.get("time", "")))
        return results

    def get_showtime_by_id(self, st_id: str) -> Optional[Dict[str, Any]]:
        for st in self.showtimes:
            if str(st.get("id", "")).upper() == st_id.upper():
                return {**st, "cinema": self._cinema(st.get("cinema_id")),
                        "movie": self.get_movie_by_id(st.get("movie_id", ""), fuzzy=False)}
        return None

    def reserve_showtime(self, st_id: str, seats: int) -> bool:
        for st in self.showtimes:
            if str(st.get("id", "")).upper() == st_id.upper():
                if seats > 0 and st.get("seats_available", 0) >= seats:
                    st["seats_available"] -= seats
                    return True
        return False

    def genres(self) -> List[str]:
        return sorted({g for m in self.movies for g in self._genres_of(m)})

    def languages(self) -> List[str]:
        return sorted({m["language"] for m in self.movies if m.get("language")})

    def vocabulary(self) -> List[str]:
        return [m["title"] for m in self.movies if m.get("title")] + \
               [c["name"] for c in self.cinemas if c.get("name")] + self.genres()