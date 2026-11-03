from typing import Any, Dict, List, Optional
from repositories import FlightRepository, ProductRepository, CinemaRepository
from urllib.parse import quote_plus

MAX_RESULTS = 5

def _pname(p: Dict[str, Any], lang: str = "en") -> str:
    names = p.get("name") or {}
    if isinstance(names, str):
        return names
    return names.get(lang) or names.get("en") or next(iter(names.values()), "?")

# ------------------------------------------------------------------ Flights
class FlightDomain:
    def __init__(self, repo: FlightRepository):
        self.repo = repo
        self.last_results: List[Dict[str, Any]] = []

    @staticmethod
    def _stops(f: Dict[str, Any]) -> str:
        n = f.get("stops", 0)
        if n == 0:
            return "Direct"
        via = f" via {f['via']}" if f.get("via") else ""
        return f"{n} stop(s){via}"

    @staticmethod
    def _duration(minutes: Any) -> str:
        try:
            m = int(minutes)
            return f"{m // 60}h {m % 60:02d}m"
        except (TypeError, ValueError):
            return "?"

    def _line(self, f: Dict[str, Any]) -> str:
        o, d = f.get("origin") or {}, f.get("destination") or {}
        dep = str(f.get("departure_local", "?")).replace("T", " ")
        arr = str(f.get("arrival_local", "?")).replace("T", " ")
        return (f"**{f.get('airline', '?')} {f.get('flight_number', '')}**: {o.get('code', '?')} ➔ {d.get('code', '?')} | "
                f"Dep {dep} → Arr {arr} | {self._duration(f.get('duration_min'))} | {self._stops(f)} | "
                f"Baggage {f.get('baggage_kg', '?')} kg | **{f.get('price_azn', '?')} AZN** | "
                f"Seats left: {f.get('seats_available', '?')} (ID: `{f.get('id', '?')}`)")

    def handle_search(self, params: Dict[str, Any], lang: str = "en") -> str:
        flights = self.repo.search_flights(
            origin=params.get("origin"), destination=params.get("destination"),
            date=params.get("date"), max_stops=params.get("max_stops"),
            max_price=params.get("max_price"), airline=params.get("airline"),
            sort_by=params.get("sort_by"), cabin=params.get("cabin"),
            departure_after=params.get("departure_after"),
        )
        self.last_results = flights[:MAX_RESULTS]
        if not flights:
            msg = "Sizin axtarışa uyğun uçuş tapılmadı." if lang == "az" else ("Рейсы не найдены." if lang == "ru" else "No flights found matching your criteria.")
            return msg
            
        head = "Uyğun uçuşlar:" if lang == "az" else ("Подходящие рейсы:" if lang == "ru" else "Here are the matching flights:")
        lines = [head]
        lines += [f"{i}. {self._line(f)}" for i, f in enumerate(self.last_results, 1)]
        return "\n".join(lines)

    def handle_details(self, f: Dict[str, Any]) -> str:
        return f"Flight details:\n{self._line(f)}\nCabin: {f.get('cabin', '?')}"

    def handle_compare(self, flight_ids: List[str]) -> str:
        flights = [f for f in (self.repo.get_by_id(i) for i in flight_ids) if f]
        if len(flights) < 2:
            return "Please provide at least two valid flights to compare."
        lines = ["### Flight comparison", "| Flight | Price (AZN) | Duration | Stops | Baggage | Seats |", "|---|---|---|---|---|---|"]
        for f in flights:
            lines.append(f"| {f.get('airline')} {f.get('flight_number')} (`{f.get('id')}`) | {f.get('price_azn')} | "
                         f"{self._duration(f.get('duration_min'))} | {self._stops(f)} | {f.get('baggage_kg')} kg | {f.get('seats_available')} |")
        cheapest = min(flights, key=lambda f: f.get("price_azn", float("inf")))
        fastest = min(flights, key=lambda f: f.get("duration_min", float("inf")))
        lines.append(f"Cheapest: {cheapest.get('flight_number')} · Fastest: {fastest.get('flight_number')}")
        return "\n".join(lines)

    def handle_reserve(self, flight_id: str, seats: int = 1) -> str:
        if seats < 1:
            return "The number of seats must be at least 1."
        flight = self.repo.get_by_id(flight_id)
        if not flight:
            return f"Flight {flight_id} was not found."
        if self.repo.update_seats(flight_id, seats):
            return (f"Reserved {seats} seat(s) on **{flight.get('airline')} {flight.get('flight_number')}** "
                    f"(ID: {flight_id}). Have a great trip!")
        return f"Sorry, only {flight.get('seats_available', 0)} seat(s) are left on {flight_id}."


# ----------------------------------------------------------------- Shopping
class ShoppingDomain:
    def __init__(self, repo: ProductRepository):
        self.repo = repo
        self.cart: List[Dict[str, Any]] = []
        self.last_results: List[Dict[str, Any]] = []
        self.last_cards: List[Dict[str, Any]] = []

    @staticmethod
    def _stock(p: Dict[str, Any]) -> str:
        s = p.get("stock", 0)
        return f"In stock ({s})" if s > 0 else "Out of stock"

    def _line(self, p: Dict[str, Any], lang: str) -> str:
        return (f"**{_pname(p, lang)}** by {p.get('brand', '?')} - **{p.get('price_azn', '?')} AZN** | "
                f"⭐{p.get('rating', '?')} | {self._stock(p)} (ID: `{p.get('id', '?')}`)")

    def handle_visual_search(self, image_path: str, lang: str = "en") -> str:
        products = self.repo.search_by_image(image_path)
        self.last_results = products[:MAX_RESULTS]
        self._set_cards(self.last_results, lang)
        
        if not products:
            if lang == "az":
                return "Şəkildəki məhsulu dəqiq müəyyən edə bilmədim. Nə axtardığınızı sözlərlə yaza bilərsiniz?"
            elif lang == "ru":
                return "Не удалось определить товар на фото. Можете описать его словами?"
            return "I couldn't confidently identify that product. Could you tell me what it is in words?"
            
        head = "Şəklinizə ən uyğun məhsullar:" if lang == "az" else ("Наиболее похожие товары:" if lang == "ru" else "Here are the closest matches to your image:")
        lines = [head]
        lines += [f"{i}. {self._line(p, lang)}" for i, p in enumerate(self.last_results, 1)]
        return "\n".join(lines)

    def handle_search(self, params: Dict[str, Any], lang: str = "en") -> str:
        products = self.repo.search_products(
            query=params.get("query"), category=params.get("category"), brand=params.get("brand"),
            max_price=params.get("max_price"), color=params.get("color"))
        self.last_results = products[:MAX_RESULTS]
        self._set_cards(self.last_results, lang)
        if not products:
            if lang == "az": return "Axtarışa uyğun məhsul tapılmadı."
            if lang == "ru": return "Товары по вашему запросу не найдены."
            return "No products found matching your search."
            
        head = "Tapılan məhsullar:" if lang == "az" else ("Найденные товары:" if lang == "ru" else "Here are the products found:")
        lines = [head]
        lines += [f"{i}. {self._line(p, lang)}" for i, p in enumerate(self.last_results, 1)]
        return "\n".join(lines)

    def handle_details(self, p: Dict[str, Any], lang: str = "en") -> str:
        extra = f"\nColour: {p.get('color', '?')} | Category: {p.get('category', '?')}\n{p.get('description', '')}"
        self._set_cards(self.last_results, lang)
        return f"{self._line(p, lang)}{extra}".strip()


    def handle_compare(self, ids: List[str], lang: str = "en") -> str:
        prods = [p for p in (self.repo.get_by_id(i) for i in ids) if p]
        if len(prods) < 2:
            return "Please provide at least two valid products to compare."
        lines = ["### Product comparison", "| Product | Brand | Price (AZN) | Rating | Stock | Colour |", "|---|---|---|---|---|---|"]
        for p in prods:
            lines.append(f"| {_pname(p, lang)} (`{p.get('id')}`) | {p.get('brand')} | {p.get('price_azn')} | "
                         f"{p.get('rating')} | {p.get('stock')} | {p.get('color')} |")
        return "\n".join(lines)

    def _in_cart(self, pid: str) -> Optional[Dict[str, Any]]:
        return next((i for i in self.cart if i["product"]["id"].upper() == pid.upper()), None)

    def handle_add_to_cart(self, product_id: str, qty: int = 1, lang: str = "en") -> str:
        if qty < 1:
            return "Quantity must be at least 1."
        prod = self.repo.get_by_id(product_id)
        if not prod:
            return f"Product with ID {product_id} not found."
        line = self._in_cart(product_id)
        already = line["qty"] if line else 0
        if prod.get("stock", 0) < already + qty:
            return f"Sorry, only {prod.get('stock', 0)} unit(s) of {_pname(prod, lang)} are in stock."
        if line:
            line["qty"] += qty
        else:
            self.cart.append({"product": prod, "qty": qty})
        
        if lang == "az": return f"{qty} ədəd **{_pname(prod, lang)}** səbətə əlavə edildi."
        if lang == "ru": return f"{qty}x **{_pname(prod, lang)}** добавлено в корзину."
        return f"Added {qty}x **{_pname(prod, lang)}** to your cart."

    def handle_remove_from_cart(self, product_id: str, qty: Optional[int] = None, lang: str = "en") -> str:
        line = self._in_cart(product_id)
        if not line:
            return "That product is not in your cart."
        name = _pname(line["product"], lang)
        if qty is None or qty >= line["qty"]:
            self.cart.remove(line)
            return f"Removed **{name}** from your cart."
        line["qty"] -= qty
        return f"Removed {qty}x **{name}**; {line['qty']} left in your cart."

    def handle_view_cart(self, lang: str = "en") -> str:
        if not self.cart:
            return "Səbətiniz boşdur." if lang == "az" else ("Ваша корзина пуста." if lang == "ru" else "Your shopping cart is empty.")
        total, lines = 0.0, ["### Shopping cart"]
        for item in self.cart:
            p = item["product"]
            sub = p.get("price_azn", 0) * item["qty"]
            total += sub
            lines.append(f"- {item['qty']}x {_pname(p, lang)} - {p.get('price_azn')} AZN each (subtotal {sub:.2f} AZN)")
        lines.append(f"\n**Cart total: {total:.2f} AZN**")
        return "\n".join(lines)
    
    def to_card(self, p: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
        name = _pname(p, lang)
        stock = p.get("stock", 0)
        # data-da real link varsa onu götür, yoxdursa birmarket axtarış linkinə düş
        url = p.get("url") or f"https://birmarket.az/search?q={quote_plus(name)}"
        return {
            "id": p.get("id"),
            "name": name,
            "brand": p.get("brand"),
            "category": p.get("category"),
            "description": p.get("description", ""),
            "price_azn": p.get("price_azn"),
            "rating": p.get("rating"),
            "stock": stock,
            "in_stock": stock > 0,
            "image_url": p.get("image") or p.get("image_url"),
            "url": url,
            "url_is_exact": bool(p.get("url")),
        }
        
    def _set_cards(self, products, lang):
        self.last_cards = [self.to_card(p, lang) for p in products[:MAX_RESULTS]]


# ------------------------------------------------------------------- Cinema
class CinemaDomain:
    def __init__(self, repo: CinemaRepository):
        self.repo = repo
        self.last_results: List[Dict[str, Any]] = []     
        self.last_showtimes: List[Dict[str, Any]] = []   

    @staticmethod
    def showtime_line(s: Dict[str, Any]) -> str:
        c = s.get("cinema") or {}
        return (f"{c.get('name', 'Cinema')} | Hall {s.get('hall', '?')} | {s.get('date', '?')} {s.get('time', '?')} | "
                f"**{s.get('price_azn', '?')} AZN** | Seats: {s.get('seats_available', '?')}/{s.get('seats_total', '?')} "
                f"(Showtime ID: `{s.get('id', '?')}`)")

    @staticmethod
    def _movie_head(m: Dict[str, Any]) -> str:
        g = m.get("genre", [])
        genres = g if isinstance(g, str) else ", ".join(g)
        return (f"**{m.get('title', '?')}** ({genres}, {m.get('language', '?')}) ⭐{m.get('rating', '?')} | "
                f"{m.get('duration_min', '?')} min | Age {m.get('age_rating', '?')}")

    def handle_search_movies(self, params: Dict[str, Any], lang: str = "en") -> str:
        date, time, after = params.get("date"), params.get("time"), params.get("after")
        movies = self.repo.search_movies(genre=params.get("genre"), language=params.get("language"))
        self.last_showtimes = []

        if not (date or time or after):  
            self.last_results = movies[:MAX_RESULTS]
            if not movies:
                return "Axtarışa uyğun film tapılmadı." if lang == "az" else "No films found."
            head = "Filmlər:" if lang == "az" else "Here are the films:"
            lines = [head]
            lines += [f"{i}. {self._movie_head(m)} (ID: `{m.get('id')}`)" for i, m in enumerate(self.last_results, 1)]
            return "\n".join(lines)

        entries = []
        for m in movies:
            sts = self.repo.get_showtimes_for_movie(m["id"], date=date, time=time, after=after)
            if sts:
                entries.append((m, sts))
        entries = entries[:MAX_RESULTS]
        if not entries:
            when = f" on {date}" if date else ""
            return f"No films found{when} matching your criteria."
            
        self.last_results = [m for m, _ in entries]
        self.last_showtimes = [s for _, sts in entries for s in sts[:4]]
        lines = ["Seanslar:" if lang == "az" else "Here is what's showing:"]
        for i, (m, sts) in enumerate(entries, 1):
            lines.append(f"{i}. {self._movie_head(m)}")
            lines += [f"   - {self.showtime_line(s)}" for s in sts[:4]]
        return "\n".join(lines)

    def handle_showtimes(self, movie_identifier: str, date: Optional[str] = None,
                         time: Optional[str] = None, after: Optional[str] = None) -> str:
        movie = self.repo.get_movie_by_id(movie_identifier)
        if not movie:
            return f"Movie '{movie_identifier}' not found."
        sts = self.repo.get_showtimes_for_movie(movie["id"], date, time, after)
        self.last_results, self.last_showtimes = [movie], sts
        head = f"### {self._movie_head(movie)}\n{movie.get('synopsis', '')}".strip()
        if not sts:
            return f"{head}\n\nNo showtimes found for this film" + (f" on {date}." if date else ".")
        return head + "\n\n" + "\n".join(f"- {self.showtime_line(s)}" for s in sts)

    def handle_cinemas(self) -> str:
        if not self.repo.cinemas:
            return "No cinemas found."
        return "Cinemas:\n" + "\n".join(
            f"- **{c.get('name')}** ({c.get('district', '?')}) - {c.get('address', '')}" for c in self.repo.cinemas)

    def handle_reserve(self, showtime_id: str, seats: int) -> str:
        if seats < 1:
            return "The number of seats must be at least 1."
        st = self.repo.get_showtime_by_id(showtime_id)
        if not st:
            return f"Showtime {showtime_id} was not found."
        if st.get("seats_available", 0) < seats:
            return f"Sorry, only {st.get('seats_available', 0)} seat(s) are left for showtime {showtime_id}."
        if not self.repo.reserve_showtime(showtime_id, seats):
            return f"Sorry, could not reserve {seats} seat(s) for showtime {showtime_id}."
        for s in self.last_showtimes: 
            if s.get("id") == st.get("id"):
                s["seats_available"] = s.get("seats_available", 0) - seats
        title = (st.get("movie") or {}).get("title", "the film")
        cinema = (st.get("cinema") or {}).get("name", "the cinema")
        total = st.get("price_azn", 0) * seats
        return (f"Reserved {seats} ticket(s) for **{title}** at **{cinema}** on {st.get('date')} {st.get('time')} "
                f"(total {total:.2f} AZN).")