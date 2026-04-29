import json
from enum import Enum
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from light_map.core.config_schema import (
    ArucoDefinitionSchema,
    CoverResultSchema,
    GlobalConfigSchema,
    GmPosition,
    GridType,
    MapEntrySchema,
    NamingStyle,
    SessionDataSchema,
    SizeProfileSchema,
    TokenConfigSchema,
    TokenDetectionAlgorithm,
    TokenSchema,
    ViewportStateSchema,
    WedgeSegmentSchema,
)


OUTPUT_FILE = "frontend/src/types/schema.generated.ts"


def python_type_to_ts(py_type: Any) -> str:
    """Maps Python types to TypeScript types."""
    if py_type is str:
        return "string"
    if py_type in (int, float):
        return "number"
    if py_type is bool:
        return "boolean"

    origin = get_origin(py_type)
    args = get_args(py_type)

    # Handle Optional/Union
    if origin is Union:
        ts_types = [python_type_to_ts(arg) for arg in args if arg is not type(None)]
        if type(None) in args:
            if len(ts_types) == 1:
                return f"{ts_types[0]} | null"
            return f"({' | '.join(ts_types)}) | null"
        return " | ".join(ts_types)

    # Handle Lists
    if origin is list or py_type is list:
        if args:
            return f"{python_type_to_ts(args[0])}[]"
        return "any[]"

    # Handle Tuples
    if origin is tuple or py_type is tuple:
        if args:
            return f"[{', '.join([python_type_to_ts(arg) for arg in args])}]"
        return "any[]"

    # Handle Dicts
    if origin is dict or py_type is dict:
        if len(args) == 2:
            key_type = python_type_to_ts(args[0])
            val_type = python_type_to_ts(args[1])
            return f"Record<{key_type}, {val_type}>"
        return "Record<string, any>"

    # Handle Enums
    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return py_type.__name__

    # Handle BaseModel subclasses (nested schemas)
    if isinstance(py_type, type) and issubclass(py_type, BaseModel):
        name = py_type.__name__
        if name.endswith("Schema"):
            return name[:-6]
        return name

    return "any"


def generate_ts_interface(model_name: str, model: type[BaseModel]) -> str:
    lines = [f"export interface {model_name} {{"]
    for field_name, field in model.model_fields.items():
        ts_type = python_type_to_ts(field.annotation)
        # Use optional marker only if field can be None
        origin = get_origin(field.annotation)
        args = get_args(field.annotation)
        is_optional_type = origin is Union and type(None) in args

        optional = "?" if is_optional_type else ""
        lines.append(f"  {field_name}{optional}: {ts_type};")
    lines.append("}\n")
    return "\n".join(lines)


def generate_ts_enum(enum_class: type[Enum]) -> str:
    lines = [f"export enum {enum_class.__name__} {{"]
    for member in enum_class:
        # Assuming StrEnum values for simplicity in this project
        lines.append(f'  {member.name} = "{member.value}",')
    lines.append("}\n")
    return "\n".join(lines)


def generate_metadata_registry(model_name: str, model: type[BaseModel]) -> str:
    metadata = {}
    for field_name, field in model.model_fields.items():
        field_meta = {
            "title": field.title or field_name.replace("_", " ").title(),
            "description": field.description or "",
        }

        # Extract numeric constraints from metadata list in Pydantic V2
        for meta in field.metadata:
            if hasattr(meta, "ge"):
                field_meta["min"] = meta.ge
            if hasattr(meta, "le"):
                field_meta["max"] = meta.le
            if hasattr(meta, "gt"):
                field_meta["min"] = meta.gt
            if hasattr(meta, "lt"):
                field_meta["max"] = meta.lt

        # Add default if it's not Pydantic's PydanticUndefined
        if field.default is not PydanticUndefined and field.default is not None:
            try:
                # Test if it's JSON serializable
                json.dumps(field.default)
                field_meta["default"] = field.default
            except (TypeError, OverflowError):
                pass

        # For enums, we could add options here
        annotation = field.annotation
        # Handle Optional[Enum]
        if get_origin(annotation) is Union:
            args = get_args(annotation)
            enum_types = [
                arg for arg in args if isinstance(arg, type) and issubclass(arg, Enum)
            ]
            if enum_types:
                annotation = enum_types[0]

        if isinstance(annotation, type) and issubclass(annotation, Enum):
            field_meta["options"] = [
                {"label": m.name.replace("_", " ").title(), "value": m.value}
                for m in annotation
            ]

        metadata[field_name] = field_meta

    registry_name = f"{model_name.upper()}_METADATA"
    lines = [
        f"export const {registry_name}: Record<keyof {model_name}, FieldMetadata> = ",
        json.dumps(metadata, indent=2),
        ";\n",
    ]
    return "".join(lines)


def main():
    print(f"Generating {OUTPUT_FILE}...")

    sections = [
        "/* tslint:disable */\n/* eslint-disable */\n/**\n * This file was automatically generated and should not be edited.\n * Run 'python3 scripts/generate_ts_schema.py' to update.\n */\n"
    ]

    # Enums
    sections.append(generate_ts_enum(GmPosition))
    sections.append(generate_ts_enum(TokenDetectionAlgorithm))
    sections.append(generate_ts_enum(NamingStyle))
    sections.append(generate_ts_enum(GridType))

    # All schemas to generate
    schemas = [
        ("SizeProfile", SizeProfileSchema),
        ("ArucoDefinition", ArucoDefinitionSchema),
        ("TokenConfig", TokenConfigSchema),
        ("ViewportState", ViewportStateSchema),
        ("Token", TokenSchema),
        ("SessionData", SessionDataSchema),
        ("MapEntry", MapEntrySchema),
        ("GlobalConfig", GlobalConfigSchema),
        ("WedgeSegment", WedgeSegmentSchema),
        ("CoverResult", CoverResultSchema),
    ]

    # Interfaces
    for name, model in schemas:
        sections.append(generate_ts_interface(name, model))

    # Metadata
    sections.append(generate_ts_metadata_interface())
    for name, model in schemas:
        sections.append(generate_metadata_registry(name, model))

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(sections))

    print("Done!")


def generate_ts_metadata_interface() -> str:
    return """
export interface FieldMetadata {
  title: string;
  description: string;
  min?: number;
  max?: number;
  step?: number;
  default?: any;
  options?: { label: string; value: string }[];
}
"""


if __name__ == "__main__":
    main()
