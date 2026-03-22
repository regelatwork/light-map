import time
from light_map.core.versioned_atom import VersionedAtom


def test_versioned_atom_updates_timestamp_on_change():
    atom = VersionedAtom(10, "test_atom")
    initial_ts = atom.timestamp

    time.sleep(0.001)  # Ensure monotonic clock can advance
    changed = atom.update(20)

    assert changed is True
    assert atom.value == 20
    assert atom.timestamp > initial_ts


def test_versioned_atom_does_not_update_on_same_value():
    atom = VersionedAtom(10, "test_atom")
    initial_ts = atom.timestamp

    changed = atom.update(10)

    assert changed is False
    assert atom.timestamp == initial_ts
