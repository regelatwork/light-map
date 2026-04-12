import dataclasses
from typing import Any, Dict, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


def sync_pydantic_to_dataclass(pydantic_obj: BaseModel, dataclass_obj: Any) -> None:
    """
    Synchronizes values from a Pydantic model to a dataclass instance recursively.
    Only fields that are set in the Pydantic model and exist in the dataclass are updated.
    """
    if not pydantic_obj or not dataclass_obj:
        return

    # Use model_dump to get values that were actually provided (exclude_unset=True)
    # but for initial load we might want all fields.
    # For API updates, exclude_unset=True is critical.
    data = pydantic_obj.model_dump(exclude_unset=True)
    _sync_dict_to_dataclass(data, dataclass_obj)


def _sync_dict_to_dataclass(data: Dict[str, Any], dataclass_obj: Any) -> None:
    for key, value in data.items():
        if not hasattr(dataclass_obj, key):
            continue

        current_val = getattr(dataclass_obj, key)

        if isinstance(value, dict) and dataclasses.is_dataclass(current_val):
            # Recursive sync for nested dataclasses
            _sync_dict_to_dataclass(value, current_val)
        elif isinstance(value, list) and isinstance(current_val, list):
            # For lists, we currently overwrite.
            # In the future, we might want smarter merging for complex list items.
            setattr(dataclass_obj, key, value)
        else:
            # Direct assignment (handles primitives, Enums, etc.)
            setattr(dataclass_obj, key, value)


def sync_pydantic_to_dict(pydantic_obj: BaseModel, target_dict: Dict[str, Any]) -> None:
    """
    Synchronizes values from a Pydantic model to a plain dictionary.
    """
    data = pydantic_obj.model_dump(exclude_unset=True)
    target_dict.update(data)
