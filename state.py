from typing import Any, Dict, List, Optional

DOMAINS = ("Flights", "Shopping", "Cinema")


def canonical(domain: str) -> str:
    """Single casing used everywhere: 'flights' -> 'Flights'."""
    return str(domain).strip().capitalize()


class SessionState:
    def __init__(self, history_limit: int = 20):
        self.language: str = "en"
        self.preferences: Dict[str, Any] = {}
        self.last_active_domain: Optional[str] = None
        self.pending: Optional[Dict[str, Any]] = None
        self.history: List[Dict[str, str]] = []
        self.history_limit = history_limit
        self.domain_states: Dict[str, Dict[str, Any]] = {d: self._empty() for d in DOMAINS}

    @staticmethod
    def _empty() -> Dict[str, Any]:
        return {
            "last_results": [],
            "selected": None,
            "filters": {},
            "last_reply": None,
            "showtimes": [],
        }

    def get_domain_state(self, domain: str) -> Dict[str, Any]:
        return self.domain_states.setdefault(canonical(domain), self._empty())

    def update_domain_state(self, domain: str, state_data: Dict[str, Any]) -> None:
        d = canonical(domain)
        self.get_domain_state(d).update(state_data)
        self.last_active_domain = d

    def select(self, domain: str, item: Optional[Dict[str, Any]]) -> None:
        self.update_domain_state(domain, {"selected": item})

    def set_preference(self, key: str, value: Any) -> None:
        self.preferences[key] = value

    def add_turn(self, user: str, assistant: str) -> None:
        self.history.append({"user": user, "assistant": assistant})
        del self.history[:-self.history_limit]