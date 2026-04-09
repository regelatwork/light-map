import time
from typing import TypeVar, Generic, Optional, Callable

T = TypeVar("T")


class VersionedAtom(Generic[T]):
    def __init__(
        self,
        initial_value: T,
        name: str,
        equality_fn: Optional[Callable[[T, T], bool]] = None,
    ):
        self._value = initial_value
        self._name = name
        self._timestamp = time.monotonic_ns()
        self._equality_fn = equality_fn or (lambda a, b: a == b)

    @property
    def value(self) -> T:
        return self._value

    @property
    def timestamp(self) -> int:
        return self._timestamp

    def would_change(self, new_value: T) -> bool:
        """Checks if the new value is different from the current value."""
        return not self._equality_fn(self._value, new_value)

    def update(self, new_value: T, force_timestamp: Optional[int] = None) -> bool:
        if force_timestamp is not None or not self._equality_fn(self._value, new_value):
            self._value = new_value
            self._timestamp = force_timestamp or time.monotonic_ns()
            return True
        return False
