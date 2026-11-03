import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from repositories import (FlightRepository, ProductRepository, CinemaRepository,
                          DataSourceError, normalize_text)
from domains import FlightDomain, ShoppingDomain, CinemaDomain
from state import SessionState
from router import SuperChatRouter, parse_date, extract_time

logger = logging.getLogger("superchat")
DATA_DIR = Path(__file__).resolve().parent

# ------------------------------------------------------------------- i18n
TEXT = {
    "en": {
        "oos": "I'm sorry, I can only help with flights, shopping products and cinema showtimes. How can I help you with those?",
        "ambiguous": "Could you tell me whether you're looking for a flight, a product or a film?",
        "missing_ctx": "Which film and showtime, or which flight, would you like to book?",
        "which_item": "Which one do you mean? Please give me its number from the list or its ID.",
        "nothing_yet": "I don't have anything to refer to yet. Please search first.",
        "how_many": "How many seats would you like?",
        "need_two": "Please name at least two items to compare (numbers from the list or IDs).",
        "pick_showtime": "Several showtimes match. Which one would you like? Please give its Showtime ID.",
        "back": "Back to where we left off:",
        "error": "Sorry, something went wrong while handling your request. Please try again.",
        "empty": "Please type a message or upload an image.",
    },
    "az": {
        "oos": "Üzr istəyirəm, mən yalnız uçuşlar, məhsullar və kino seansları ilə bağlı kömək edə bilərəm. Bu mövzularda necə kömək edim?",
        "ambiguous": "Zəhmət olmasa dəqiqləşdirin: uçuş, məhsul, yoxsa film axtarırsınız?",
        "missing_ctx": "Hansı filmi və seansı, yoxsa hansı uçuşu rezerv etmək istəyirsiniz?",
        "which_item": "Hansını nəzərdə tutursunuz? Siyahıdakı nömrəsini və ya ID-ni yazın.",
        "nothing_yet": "Hələ istinad ediləcək nəticə yoxdur. Əvvəlcə axtarış edin.",
        "how_many": "Neçə yer istəyirsiniz?",
        "need_two": "Müqayisə üçün ən azı iki seçim yazın (siyahıdakı nömrə və ya ID).",
        "pick_showtime": "Bir neçə seans uyğun gəlir. Hansını istəyirsiniz? Seans ID-sini yazın.",
        "back": "Qaldığımız yerə qayıdırıq:",
        "error": "Üzr istəyirəm, sorğunu emal edərkən xəta baş verdi. Yenidən cəhd edin.",
        "empty": "Zəhmət olmasa mesaj yazın və ya şəkil yükləyin.",
    },
    "ru": {
        "oos": "Извините, я могу помочь только с авиабилетами, товарами и киносеансами. Чем могу помочь в этих областях?",
        "ambiguous": "Уточните, пожалуйста: вы ищете авиарейс, товар или фильм?",
        "missing_ctx": "Какой фильм и сеанс или какой рейс вы хотите забронировать?",
        "which_item": "Что именно вы имеете в виду? Укажите номер из списка или ID.",
        "nothing_yet": "Пока не на что ссылаться. Сначала выполните поиск.",
        "how_many": "Сколько мест вам нужно?",
        "need_two": "Укажите минимум два варианта для сравнения (номера из списка или ID).",
        "pick_showtime": "Подходит несколько сеансов. Какой выбрать? Укажите ID сеанса.",
        "back": "Возвращаемся к тому, на чём остановились:",
        "error": "Извините, при обработке запроса произошла ошибка. Попробуйте ещё раз.",
        "empty": "Пожалуйста, введите сообщение или загрузите изображение.",
    },
}

ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5, "birinci": 1, "ikinci": 2, "ucuncu": 3,
            "первый": 1, "второй": 2, "третий": 3}
NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "bir": 1, "iki": 2, "uc": 3,
        "dord": 4, "bes": 5, "alti": 6, "один": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
        "пять": 5, "шесть": 6}
_NUM = r"(\d+|" + "|".join(NUMS) + r")"
SEATS_ONLY_RE = re.compile(rf"^\W*{_NUM}\W*(?:seats?|tickets?)?\W*$")
PRONOUN_RE = re.compile(r"(?<!\w)(?:it|that one|this one|that|this|the one|bunu|onu|его|ее|этот|тот)(?!\w)")
BACK_RE = re.compile(r"(?<!\w)(?:back to|go back|return to|geri qayit\w*|geri don\w*|вернис\w*|назад к|обратно к)")
ID_RE = re.compile(r"(?<!\w)[a-z]{1,3}\d{2,4}(?!\w)")
STOP = set("""show me find do you have any is are the a an i want need looking for please under below azn what
which ok okay and in stock it of to with can get some there price cheaper one ones buy add cart and show
give list display us about my on at tonight today tomorrow""".split())
CORE_FLIGHT = ("origin", "destination", "date", "airline", "max_price")


def _to_int(s: str) -> Optional[int]:
    return int(s) if s.isdigit() else NUMS.get(s)


def extract_seats(t: str) -> Optional[int]:
    m = re.search(rf"(?<!\w){_NUM}\s+(?:seats?|tickets?|places?|yer|bilet\w*|мест\w*|билет\w*)(?!\w)", t)
    return _to_int(m.group(1)) if m else None


def extract_qty(t: str) -> Optional[int]:
    m = re.search(rf"(?<!\w){_NUM}\s*(?:x|pcs|units?|items?|pieces?|eded|шт\w*)(?!\w)", t)
    return _to_int(m.group(1)) if m else None


def extract_price(t: str) -> Optional[float]:
    m = re.search(r"(?:under|below|less than|up to|max(?:imum)?|cheaper than|within|altinda|qeder|до|менее|дешевле|не дороже)"
                  r"\s*(\d+(?:[.,]\d+)?)", t)
    if not m:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:azn|manat|man\b|₼)", t)
    return float(m.group(1).replace(",", ".")) if m else None


def detect_language(text: str, current: str = "en") -> str:
    low = text.lower()
    if re.search(r"[а-яё]", low):
        return "ru"
    if re.search(r"[əğıöüşç]", low) or re.search(
            r"(?<!\w)(?:salam|ucus\w*|axtar\w*|goster|lazimdir|bilet\w*|haradan|nece|qulaqliq\w*|noutbuk|kino|seans\w*|sebet\w*)(?!\w)",
            normalize_text(text)):
        return "az"
    if re.search(r"(?<!\w)(?:the|is|are|me|show|find|what|do|you|to|from|and|on|for|any|one|book|i|need|have)(?!\w)", low):
        return "en"
    return current


class SuperChatApp:
    def __init__(self, data_dir: Optional[Path] = None):
        base = Path(data_dir) if data_dir else DATA_DIR
        data_folder = base / "data"
        mock_folder = base / "mock"

        # 1. Əvvəlcə mock dataları ilə repozitoriyaları yaradırıq
        self.flight_repo = FlightRepository(mock_folder / "flights.json")
        self.product_repo = ProductRepository(mock_folder / "products.json")
        self.cinema_repo = CinemaRepository(
            mock_folder / "movies.json", 
            mock_folder / "cinemas.json", 
            mock_folder / "showtimes.json"
        )

        # 2. Üstəlik real dataları da (data/ daxilindəki JSON-lar) üzərinə əlavə edirik
        self._load_real_data(data_folder)

        self.flights = FlightDomain(self.flight_repo)
        self.shopping = ShoppingDomain(self.product_repo)
        self.cinema = CinemaDomain(self.cinema_repo)

        self.state = SessionState()
        self.router = SuperChatRouter({
            "Flights": self.flight_repo.vocabulary(),
            "Shopping": self.product_repo.vocabulary(),
            "Cinema": self.cinema_repo.vocabulary(),
        })

    def _load_real_data(self, data_folder: Path):
        """Real dataları mock dataların üzərinə təhlükəsiz şəkildə əlavə edir."""
        aviasales_path = data_folder / "aviasales.json"
        if aviasales_path.exists():
            try:
                with open(aviasales_path, "r", encoding="utf-8") as f:
                    real_flights = json.load(f)
                    if isinstance(real_flights, list):
                        self.flight_repo.data.extend(real_flights)
            except Exception as e:
                logger.error(f"Error loading aviasales.json: {e}")

        birmarket_path = data_folder / "birmarket.json"
        if birmarket_path.exists():
            try:
                with open(birmarket_path, "r", encoding="utf-8") as f:
                    real_products = json.load(f)
                    if isinstance(real_products, list):
                        self.product_repo.data.extend(real_products)
            except Exception as e:
                logger.error(f"Error loading birmarket.json: {e}")

        cinemaplus_path = data_folder / "cinemaplus.json"
        if cinemaplus_path.exists():
            try:
                with open(cinemaplus_path, "r", encoding="utf-8") as f:
                    real_movies = json.load(f)
                    if isinstance(real_movies, list):
                        self.cinema_repo.movies.extend(real_movies)
            except Exception as e:
                logger.error(f"Error loading cinemaplus.json: {e}")

    def process_message(self, user_message: str, image_path: Optional[str] = None) -> str:
        """Köhnə interfeys: yalnız mətn qaytarır."""
        return self.process_message_rich(user_message, image_path)["text"]
    
    def process_message_rich(self, user_message: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """Mətn + card datası qaytarır."""
        self.shopping.last_cards = []   # əvvəlki sorğunun card-ları qalmasın
        try:
            reply = self._process(user_message or "", image_path)
        except Exception:
            logger.exception("Error while processing message")
            reply = self._t("error")

        display_message = user_message if user_message else "[Şəkil yükləndi]"
        self.state.add_turn(display_message, reply)

        domain = self.state.last_active_domain
        cards = list(self.shopping.last_cards) if domain == "Shopping" else []
        return {"text": reply, "domain": domain, "cards": cards}


    def _t(self, key: str) -> str:
        return TEXT.get(self.state.language, TEXT["en"])[key]

    def _process(self, message: str, image_path: Optional[str] = None) -> str:
        message = message.strip()
        if not message and not image_path:
            return self._t("empty")
            
        t = normalize_text(message)
        if message:
            self.state.language = detect_language(message, self.state.language)
            self.state.set_preference("language", self.state.language)

        if self.state.pending:
            pending, self.state.pending = self.state.pending, None
            m = SEATS_ONLY_RE.match(t)
            if m and pending.get("type") == "cinema_seats":
                return self.cinema.handle_reserve(pending["showtime_id"], _to_int(m.group(1)) or 1)

        intent, meta = self.router.classify_intent(message, self.state.last_active_domain, image_path=image_path)
        intent, meta = self.router.classify_intent(message, self.state.last_active_domain, image_path=image_path)

        self.last_debug = {
            "message": message or "[image]",
            "intent": intent,
            "domains": meta.get("domains", []),
            "action": meta.get("action"),
            "language": self.state.language,
        }

        if intent == "Out of scope":
            return self._t("oos")
        if intent == "Ambiguous":
            return self._t("missing_ctx" if meta.get("reason") == "missing_context" else "ambiguous")
        if intent == "Mixed":
            parts = []
            for d in meta["domains"]:
                parts.append(self._dispatch(d, t, "Mixed", {**meta, "domain": d, "action": "search", "has_reference": False}))
            return "\n\n".join(parts)
        return self._dispatch(meta["domain"], t, intent, meta)

    def _dispatch(self, domain: str, t: str, intent: str, meta: Dict[str, Any]) -> str:
        self.state.last_active_domain = domain
        if intent != "Mixed" and BACK_RE.search(t):
            saved = self.state.get_domain_state(domain)["last_reply"]
            if saved:  
                return f"{self._t('back')}\n{saved}"
        handler = {"Flights": self._flights, "Shopping": self._shopping, "Cinema": self._cinema}[domain]
        return handler(t, intent, meta)

    def _remember(self, domain: str, reply: str, results: List[Dict[str, Any]],
                  filters: Optional[Dict[str, Any]] = None, **extra) -> None:
        self.state.update_domain_state(domain, {"last_results": list(results), "last_reply": reply,
                                                "filters": filters or {}, "selected": None, **extra})

    def _resolve_item(self, domain: str, t: str, lookup: Callable[[str], Optional[Dict[str, Any]]],
                      allow_default: bool = False) -> Optional[Dict[str, Any]]:
        for tok in ID_RE.findall(t):
            item = lookup(tok)
            if item:
                return item
        st = self.state.get_domain_state(domain)
        results = st["last_results"]
        for word, n in ORDINALS.items():
            if re.search(rf"(?<!\w){word}(?!\w)", t) and n <= len(results):
                return results[n - 1]
        m = re.search(r"(?:number|option|no\.?|#)\s*(\d+)", t)
        if m and 0 < int(m.group(1)) <= len(results):
            return results[int(m.group(1)) - 1]
        priced = [r for r in results if isinstance(r.get("price_azn"), (int, float))]
        if priced and re.search(r"cheaper|cheapest|ucuz|дешев", t):
            return min(priced, key=lambda r: r["price_azn"])
        if PRONOUN_RE.search(t) or allow_default:
            if st["selected"]:
                return st["selected"]
            if allow_default and len(results) == 1:
                return results[0]
        return None

    def _many_ids(self, domain: str, t: str, lookup) -> List[str]:
        ids: List[str] = []
        for tok in ID_RE.findall(t):
            item = lookup(tok)
            if item and item["id"] not in ids:
                ids.append(item["id"])
        if len(ids) >= 2:
            return ids
        results = self.state.get_domain_state(domain)["last_results"]
        nums = sorted({n for w, n in ORDINALS.items() if re.search(rf"(?<!\w){w}(?!\w)", t)})
        picked = [results[n - 1]["id"] for n in nums if n <= len(results)]
        if len(picked) >= 2:
            return picked
        return [r["id"] for r in results[:2]] if len(results) >= 2 else ids

    def _extract_route(self, t: str):
        found = []
        for key, city in self.flight_repo.cities().items():
            for m in re.finditer(rf"(?<!\w){re.escape(key)}(\w*)", t):
                found.append((m.start(), city, m.group(1)))
        for code, city in self.flight_repo.codes().items():
            for m in re.finditer(rf"(?<!\w){re.escape(code)}(?!\w)", t):
                found.append((m.start(), city, ""))
        found.sort()
        origin = dest = None
        loose: List[str] = []
        for pos, city, suffix in found:
            words = t[:pos].split()
            prev = words[-1] if words else ""
            if prev in ("from", "из") or suffix.startswith(("dan", "den", "tan", "ten")):
                origin = origin or city
            elif prev in ("to", "в", "на", "into") or suffix in ("a", "e", "ya", "ye"):
                dest = dest or city
            else:
                loose.append(city)
        if loose:
            if dest is None and origin is None and len(loose) >= 2:
                origin, dest = loose[0], loose[-1]
            elif dest is None:
                dest = loose[-1]
            elif origin is None:
                origin = loose[0]
        return origin, dest

    def _flight_params(self, t: str) -> Dict[str, Any]:
        p: Dict[str, Any] = {}
        origin, dest = self._extract_route(t)
        if origin:
            p["origin"] = origin
        if dest:
            p["destination"] = dest
        d = parse_date(t)
        if d:
            p["date"] = d
        price = extract_price(t)
        if price is not None:
            p["max_price"] = price
        for a in self.flight_repo.airlines():
            if normalize_text(a) in t:
                p["airline"] = a
        if re.search(r"(?<!\w)(?:direct|nonstop|non-stop|birbasa|прямой|прямые|прямого)(?!\w)", t):
            p["max_stops"] = 0
        if re.search(r"cheap|ucuz|дешев", t):
            p["sort_by"] = "price"
        elif re.search(r"fastest|shortest|quickest", t):
            p["sort_by"] = "duration"
        elif re.search(r"earliest", t):
            p["sort_by"] = "departure"
        return p

    def _flights(self, t: str, intent: str, meta: Dict[str, Any]) -> str:
        f, st, action, lang = self.flights, self.state.get_domain_state("Flights"), meta["action"], self.state.language
        lookup = self.flight_repo.get_by_id

        if action == "compare":
            ids = self._many_ids("Flights", t, lookup)
            return f.handle_compare(ids) if len(ids) >= 2 else self._t("need_two")
        if action in ("reserve", "cart_add"):
            item = self._resolve_item("Flights", t, lookup, allow_default=True)
            if not item:
                return self._t("which_item" if st["last_results"] else "missing_ctx")
            self.state.select("Flights", item)
            return f.handle_reserve(item["id"], extract_seats(t) or 1)

        params = self._flight_params(t)
        core = {k: v for k, v in params.items() if k in CORE_FLIGHT}
        ref = self._resolve_item("Flights", t, lookup)
        if ref and not core:                       
            self.state.select("Flights", ref)
            return f.handle_details(ref)
        if meta.get("has_reference") and not core:
            return self._t("which_item" if st["last_results"] else "nothing_yet")
        if intent == "Follow-up":                  
            params = {**st["filters"], **params}
            
        reply = f.handle_search(params, lang)
        self._remember("Flights", reply, f.last_results, params)
        return reply

    def _shopping(self, t: str, intent: str, meta: Dict[str, Any]) -> str:
        s, st, action, lang = self.shopping, self.state.get_domain_state("Shopping"), meta["action"], self.state.language
        lookup = self.product_repo.get_by_id

        if action == "visual_search":
            reply = s.handle_visual_search(meta["image_path"], lang)
            self._remember("Shopping", reply, s.last_results, {})
            return reply

        if action == "cart_view":
            return s.handle_view_cart(lang)
        if action in ("cart_add", "cart_remove"):
            item = self._resolve_item("Shopping", t, lookup, allow_default=True)
            if not item:
                return self._t("which_item" if st["last_results"] else "nothing_yet")
            if action == "cart_add":
                return s.handle_add_to_cart(item["id"], extract_qty(t) or 1, lang)
            return s.handle_remove_from_cart(item["id"], extract_qty(t), lang)
        if action == "compare":
            ids = self._many_ids("Shopping", t, lookup)
            return s.handle_compare(ids, lang) if len(ids) >= 2 else self._t("need_two")

        terms = self.router.find_terms("Shopping", t)
        words = set(re.findall(r"\w+", t))
        brand = next((b for b in self.product_repo.brands() if normalize_text(b) in t), None)
        color = next((c for c in self.product_repo.colors() if normalize_text(c) in words), None)
        query = " ".join(terms)
        if not (terms or brand or color or meta.get("has_reference")):
            query = " ".join(w for w in re.findall(r"\w+", t) if w not in STOP and not w.isdigit() and len(w) > 2)
        price = extract_price(t)
        core = bool(query or brand or color or price is not None)

        ref = self._resolve_item("Shopping", t, lookup)
        if ref and not core:                       
            self.state.select("Shopping", ref)
            return s.handle_details(ref, lang)
        if meta.get("has_reference") and not core:
            return self._t("which_item" if st["last_results"] else "nothing_yet")

        filters = {"query": query or None, "brand": brand, "color": color, "max_price": price}
        if intent == "Follow-up" and not query:
            filters = {**st["filters"], **{k: v for k, v in filters.items() if v is not None}}
            
        reply = s.handle_search(filters, lang)
        self._remember("Shopping", reply, s.last_results, filters)
        return reply

    def _find_genre(self, t: str) -> Optional[str]:
        t2 = t.replace("science fiction", "scifi")
        toks = set(re.findall(r"\w+", t2.replace("-", "")))
        for g in self.cinema_repo.genres():
            gn = normalize_text(g).replace("-", "").replace(" ", "")
            if gn in toks or gn + "s" in toks:
                return g
        return None

    def _find_language(self, t: str) -> Optional[str]:
        toks = set(re.findall(r"\w+", t))
        return next((l for l in self.cinema_repo.languages() if normalize_text(l) in toks), None)

    def _find_movie(self, t: str, allow_default: bool = False) -> Optional[Dict[str, Any]]:
        m = self.cinema_repo.find_movie_in_text(t)
        if m:
            return m
        return self._resolve_item("Cinema", t, lambda tok: self.cinema_repo.get_movie_by_id(tok, fuzzy=False),
                                  allow_default=allow_default)

    def _cinema(self, t: str, intent: str, meta: Dict[str, Any]) -> str:
        c, st, action, lang = self.cinema, self.state.get_domain_state("Cinema"), meta["action"], self.state.language
        if action == "cinemas":
            return c.handle_cinemas()
        if action in ("reserve", "cart_add"):
            return self._cinema_reserve(t)

        date, time = parse_date(t), extract_time(t)
        after = "17:00" if re.search(r"tonight|evening|axsam|вечер", t) else None
        genre, language = self._find_genre(t), self._find_language(t)

        movie = self._find_movie(t)
        if movie and not (genre and not c.repo.find_movie_in_text(t) and not ID_RE.search(t)):
            self.state.select("Cinema", movie)
            reply = c.handle_showtimes(movie["id"], date, time, after)
            self._remember("Cinema", reply, c.last_results, {}, showtimes=c.last_showtimes, selected=movie)
            return reply

        params = {"genre": genre, "language": language, "date": date, "time": time, "after": after}
        if intent == "Follow-up":                  
            params = {**st["filters"], **{k: v for k, v in params.items() if v}}
            
        reply = c.handle_search_movies(params, lang)
        self._remember("Cinema", reply, c.last_results, params, showtimes=c.last_showtimes)
        return reply

    def _cinema_reserve(self, t: str) -> str:
        c, st = self.cinema, self.state.get_domain_state("Cinema")
        seats = extract_seats(t)
        showtime = None
        for tok in ID_RE.findall(t):
            showtime = c.repo.get_showtime_by_id(tok)
            if showtime:
                break
        if not showtime:
            movie = self._find_movie(t, allow_default=True)
            cands = [s for s in st["showtimes"] if movie is None or s.get("movie_id") == movie["id"]]
            d, tm = parse_date(t), extract_time(t)
            if d:
                cands = [s for s in cands if s.get("date") == d]
            if tm:
                cands = [s for s in cands if str(s.get("time", "")).startswith(tm)]
            if len(cands) == 1:
                showtime = cands[0]
            elif len(cands) > 1:
                return self._t("pick_showtime") + "\n" + "\n".join(f"- {c.showtime_line(s)}" for s in cands[:6])
            elif movie:
                return c.handle_showtimes(movie["id"], d) + "\n\n" + self._t("pick_showtime")
            else:
                return self._t("missing_ctx")
        self.state.select("Cinema", showtime)
        if not seats:
            self.state.pending = {"type": "cinema_seats", "showtime_id": showtime["id"]}
            return self._t("how_many")
        return c.handle_reserve(showtime["id"], seats)
    


SAMPLES = [
    ["Find me a flight from Baku to Istanbul on Friday.", "What is playing tonight?", "Do you have wireless headphones under 100 AZN?"],
    ["What is playing tonight?", "Show me laptops.", "Okay, and the sci-fi one, any seats on Saturday?"],
    ["Show me laptops.", "The second one, is it in stock?"],
    ["Flights to Istanbul on 6 November.", "The cheaper one, is it direct?"],
    ["I need a flight to Istanbul on 6 November and a backpack for the trip."],
    ["Show me something good."],
    ["What is the weather in Ganja?"],
    ["Book two seats."],
]


def run_demo() -> None:
    for i, convo in enumerate(SAMPLES, 1):
        print(f"\n===== Conversation {i} =====")
        app = SuperChatApp()
        for q in convo:
            print(f"\nUser: {q}\nSuperChat: {app.process_message(q)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, filename="superchat.log")
    try:
        if "--demo" in sys.argv:
            run_demo()
        else:
            chat = SuperChatApp()
            print("SuperChat ready. Type 'exit' to quit.")
            while True:
                msg = input("\nYou: ").strip()
                if msg.lower() in ("exit", "quit"):
                    break
                print(f"SuperChat: {chat.process_message(msg)}")
    except DataSourceError as e:
        print(f"Startup error: {e}")
        
        