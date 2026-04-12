import json
from enum import Enum
from typing import Any, Type, get_args, get_origin, Union
from pydantic import BaseModel
from light_map.core.config_schema import (
    GlobalConfigSchema,
    GmPosition,
    TokenDetectionAlgorithm,
    NamingStyle,
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

    # Handle Optional/Union
    origin = get_origin(py_type)
    if origin is Union:
        args = get_args(py_type)
        ts_types = [python_type_to_ts(arg) for arg in args if arg is not type(None)]
        if type(None) in args:
            return f"{' | '.join(ts_types)} | null"
        return " | ".join(ts_types)

    # Handle Enums
    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return py_type.__name__

    return "any"


def generate_ts_interface(model_name: str, model: Type[BaseModel]) -> str:
    lines = [f"export interface {model_name} {{"]
    for field_name, field in model.model_fields.items():
        ts_type = python_type_to_ts(field.annotation)
        # Use optional marker if field can be None
        optional = (
            "?"
            if get_origin(field.annotation) is Union
            and type(None) in get_args(field.annotation)
            else ""
        )
        lines.append(f"  {field_name}{optional}: {ts_type};")
    lines.append("}\n")
    return "\n".join(lines)


def generate_ts_enum(enum_class: Type[Enum]) -> str:
    lines = [f"export enum {enum_class.__name__} {{"]
    for member in enum_class:
        # Assuming StrEnum values for simplicity in this project
        lines.append(f'  {member.name} = "{member.value}",')
    lines.append("}\n")
    return "\n".join(lines)


def generate_metadata_registry(model_name: str, model: Type[BaseModel]) -> str:
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
        if field.default is not None and str(field.default) != "PydanticUndefined":
            field_meta["default"] = field.default

        # For enums, we could add options here
        if isinstance(field.annotation, type) and issubclass(field.annotation, Enum):
            field_meta["options"] = [
                {"label": m.name.replace("_", " ").title(), "value": m.value}
                for m in field.annotation
            ]

        metadata[field_name] = field_meta

    registry_name = f"{model_name.upper()}_METADATA"
    lines = [
        f"export const {registry_name}: Record<keyof {model_name}, any> = ",
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

    # Interfaces
    sections.append(generate_ts_interface("GlobalConfig", GlobalConfigSchema))

    # Metadata
    sections.append(generate_ts_metadata_interface())
    sections.append(generate_metadata_registry("GlobalConfig", GlobalConfigSchema))

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
