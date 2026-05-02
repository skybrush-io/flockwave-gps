from collections import OrderedDict
from collections.abc import MutableMapping
from typing import TypeVar

__all__ = ("CaseInsensitiveMapping",)

V = TypeVar("V")


class CaseInsensitiveMapping(MutableMapping[str, V]):
    """A case-insensitive mapping for HTTP headers."""

    _items: OrderedDict[str, V]
    """The underlying dictionary storing the header keys and values. The keys are
    stored verbatim and another dictionary will be used to map case-insensitivized keys
    to their original keys in this dictionary.
    """

    _key_map: dict[str, str]
    """Mapping from case-insensitivized keys to their original keys in the items
    dictionary. This is used to allow us to preserve the original capitalization
    submitted by the user while still allowing us to do case-insensitive lookups for
    headers.
    """

    def __init__(self):
        self._items = OrderedDict()
        self._key_map = {}

    def _get_stored_key(self, key: str) -> str:
        normalized_key = key.lower()
        stored_key = self._key_map.get(normalized_key)
        if stored_key is not None:
            return stored_key
        else:
            raise KeyError(key)

    def __getitem__(self, key: str) -> V:
        return self._items[self._get_stored_key(key)]

    def __setitem__(self, key: str, value: V) -> None:
        try:
            old_stored_key = self._get_stored_key(key)
        except KeyError:
            pass
        else:
            del self._items[old_stored_key]

        normalized_key = key.lower()
        self._items[key] = value
        self._key_map[normalized_key] = key

    def __delitem__(self, key: str) -> None:
        stored_key = self._get_stored_key(key)
        del self._items[stored_key]
        del self._key_map[key.lower()]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)
