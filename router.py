import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from repositories import normalize_text

REFERENCE_DATE = date(2026, 11, 2)  # Monday, reference date of the mock dataset

# ----------------------------------------------------------- date / time helpers
EN_MONTHS = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
             "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
             "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
             "december": 12, "dec": 12}
MONTH_STEMS = [("yanvar", 1), ("fevral", 2), ("mart", 3), ("aprel", 4), ("iyun", 6), ("iyul", 7),
               ("avqust", 8), ("sentyabr", 9), ("oktyabr", 10), ("noyabr", 11), ("dekabr", 12),
               ("январ", 1), ("феврал", 2), ("март", 3), ("апрел", 4), ("мая", 5), ("май", 5),
               ("июн", 6), ("июл", 7), ("август", 8), ("сентябр", 9), ("октябр", 10),
               ("ноябр", 11), ("декабр", 12)]
WEEKDAYS = [(r"monday|bazar ertesi|понедельник", 0), (r"tuesday|cersenbe axsami|вторник", 1),
            (r"wednesday|cersenbe|сред[аыу]", 2), (r"thursday|cume axsami|четверг", 3),
            (r"friday|cume|пятниц\w*", 4), (r"saturday|senbe|суббот\w*", 5),
            (r"sunday|bazar|воскресень\w*", 6)]
TODAY_RE = re.compile(r"(?<!\w)(?:today|tonight|bu gun|bu axsam|сегодня)(?!\w)")
TOMORROW_RE = re.compile(r"(?<!\w)(?:tomorrow|sabah|завтра)(?!\w)")
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")


def _month(word: str) -> Optional[int]:
    if word in EN_MONTHS:
        return EN_MONTHS[word]
    return next((m for stem, m in MONTH_STEMS if word.startswith(stem)), None)


def _build(day: int, month: int, ref: date) -> Optional[str]:
    try:
        d = date(ref.year, month, day)
        if d < ref:
            d = date(ref.year + 1, month, day)
        return d.isoformat()
    except ValueError:
        return None


def parse_date(text: str, ref: date = REFERENCE_DATE) -> Optional[str]:
    t = normalize_text(text)
    m = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", t)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return None
    for m in re.finditer(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+([^\W\d_]+)", t):
        mon = _month(m.group(2))
        if mon:
            return _build(int(m.group(1)), mon, ref)
    for m in re.finditer(r"([^\W\d_]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)", t):
        mon = _month(m.group(1))
        if mon:
            return _build(int(m.group(2)), mon, ref)
    if TODAY_RE.search(t):
        return ref.isoformat()
    if TOMORROW_RE.search(t):
        return (ref + timedelta(days=1)).isoformat()
    for pattern, wd in WEEKDAYS:
        if re.search(rf"(?<!\w)(?:{pattern})(?!\w)", t):
            return (ref + timedelta(days=(wd - ref.weekday()) % 7)).isoformat()
    return None


def extract_time(text: str) -> Optional[str]:
    m = TIME_RE.search(text)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


# ------------------------------------------------------------- keyword tables
FLIGHT_STATIC = [r"flights?", r"fly(?:ing)?", r"airlines?", r"airports?", r"baggage", r"luggage", r"layover",
                 r"non-?stop", r"one-?way", r"round[ -]?trip", r"aviasales", r"ucus\w*", r"reys\w*",
                 r"avia\w*", r"авиа\w*", r"рейс\w*", r"перелет\w*", r"полет\w*", r"самолет\w*"]
SHOP_NOUNS = [r"laptops?", r"notebooks?", r"headphones?", r"earbuds?", r"backpacks?", r"smartphones?", r"phones?",
              r"bags?", r"shoes?", r"qulaqliq\w*", r"noutbuk\w*", r"canta\w*", r"telefon\w*",
              r"наушник\w*", r"ноутбук\w*", r"рюкзак\w*", r"телефон\w*", r"сумк\w*"]
SHOP_CONTEXT = [r"products?", r"cart", r"basket", r"stock", r"brands?", r"mehsul\w*", r"sebet\w*",
                r"stokda", r"корзин\w*", r"товар\w*", r"в наличии"]
CINEMA_STATIC = [r"movies?", r"films?", r"cinemas?", r"showtimes?", r"playing", r"now showing", r"screenings?",
                 r"sci-?fi", r"science fiction", r"comed(?:y|ies)", r"horrors?", r"thrillers?", r"animat\w*",
                 r"romance", r"documentar\w*", r"kino\w*", r"film\w*", r"seans\w*", r"кино\w*", r"фильм\w*", r"сеанс\w*"]

OOS_RE = re.compile(r"(?<!\w)(?:weather|forecast|hava|president\w*|prezident\w*|trump|biden|politic\w*|recipes?|"
                    r"capital of|news|jokes?|who is|kimdir|xeber\w*|погод\w*|президент\w*|рецепт\w*)(?!\w)")
AMBIG_RE = re.compile(r"(?<!\w)(?:something good|something nice|something fun|anything good|recommend something|"
                      r"surprise me|nese yaxsi|что-нибудь|что нибудь|посоветуй\w*)")
REF_RE = re.compile(r"(?<!\w)(?:cheaper|cheapest|first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|that one|"
                    r"this one|it|them|ucuz\w*|ikinci|birinci|ucuncu|bunu|onu|второй|первый|третий|дешевле|его|ее)(?!\w)")
FOLLOW_RE = re.compile(r"(?<!\w)(?:cheaper|cheapest|first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|that one|"
                       r"this one|the one|it|them|and for|what about|how about|is it|any seats|in stock|compare|book|"
                       r"reserve|add|remove|more|another|instead|ucuz\w*|ikinci|birinci|ucuncu|bunu|onu|bu|"
                       r"второй|первый|третий|дешевле|его|ее|а на|а как)(?!\w)")
CART_RE = re.compile(r"(?<!\w)(?:cart|basket|sebet\w*|корзин\w*)(?!\w)")


def _build_re(static: List[str], terms: List[str]) -> re.Pattern:
    dyn = sorted({normalize_text(t) for t in terms if len(normalize_text(t)) >= 4}, key=len, reverse=True)
    parts = list(static) + [re.escape(t) + "s?" for t in dyn]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)")


class SuperChatRouter:
    def __init__(self, vocab: Optional[Dict[str, List[str]]] = None):
        vocab = vocab or {}
        self.shop_noun_re = _build_re(SHOP_NOUNS, vocab.get("Shopping", []))
        self.patterns = {
            "Flights": _build_re(FLIGHT_STATIC, vocab.get("Flights", [])),
            "Shopping": re.compile(self.shop_noun_re.pattern + "|" + _build_re(SHOP_CONTEXT, []).pattern),
            "Cinema": _build_re(CINEMA_STATIC, vocab.get("Cinema", [])),
        }

    def find_terms(self, domain: str, text: str) -> List[str]:
        if domain != "Shopping":
            return []
        seen: List[str] = []
        for m in self.shop_noun_re.finditer(normalize_text(text)):
            if m.group(0) not in seen:
                seen.append(m.group(0))
        return seen

    @staticmethod
    def _action(t: str) -> str:
        if re.search(r"(?<!\w)(?:compare|versus|vs|muqayise\w*|сравн\w*)(?!\w)", t):
            return "compare"
        if CART_RE.search(t):
            if re.search(r"(?<!\w)(?:remove|delete|sil|удал\w*)(?!\w)", t):
                return "cart_remove"
            if re.search(r"(?<!\w)(?:add|put|elave\w*|добав\w*)(?!\w)", t):
                return "cart_add"
            return "cart_view"
        if re.search(r"(?<!\w)(?:buy|purchase|satin\w*|купить|куплю)(?!\w)", t):
            return "cart_add"
        if re.search(r"(?<!\w)(?:book|booking|reserve|rezerv\w*|бронир\w*|забронир\w*)(?!\w)", t):
            return "reserve"
        if (re.search(r"(?<!\w)(?:cinemas|kinoteatr\w*|кинотеатр\w*)(?!\w)", t)
                and not re.search(r"playing|showing|tonight|today|tomorrow", t)):
            return "cinemas"
        return "search"

    def classify_intent(self, message: str, last_domain: Optional[str], image_path: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        # VISUAL SEARCH
        if image_path:
            meta: Dict[str, Any] = {
                "raw": message, 
                "action": "visual_search", 
                "domains": ["Shopping"],
                "has_reference": False,
                "image_path": image_path 
            }
            return "Shopping", meta

        t = normalize_text(message)
        domains = [d for d, rx in self.patterns.items() if rx.search(t)]
        action = self._action(t)
        meta: Dict[str, Any] = {"raw": message, "action": action, "domains": domains,
                                "has_reference": bool(REF_RE.search(t))}

        if len(domains) >= 2:
            return "Mixed", meta
        if len(domains) == 1:
            meta["domain"] = domains[0]
            return domains[0], meta
        if OOS_RE.search(t):
            return "Out of scope", meta
        if AMBIG_RE.search(t):
            return "Ambiguous", meta
        cue = FOLLOW_RE.search(t) or parse_date(t) or TIME_RE.search(t) or action != "search"
        if last_domain and cue:
            meta["domain"] = meta["target_domain"] = last_domain
            return "Follow-up", meta
        if action in ("reserve", "cart_add"):
            meta["reason"] = "missing_context"
        return "Ambiguous", meta