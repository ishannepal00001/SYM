from typing import Any, Dict


class APIManager:
    def __init__(self, api_keys: list[Dict[str, Any]]):
        self._index = 0
        self._API = api_keys
        self._blacklist: Dict[str, Any] = dict()

    def blacklist(self):
        None

    def whitelist(self):
        None

    def get_api():
        None
