"""Tests for the JSON schema and schemas sub-package helpers."""

import json
from pathlib import Path

import pytest

from aetherling.schemas import load_schema


SCHEMA_PATH = Path(__file__).parent.parent / "aetherling" / "schemas" / "aetherling_schema.json"


class TestLoadSchema:
    def test_returns_dict(self):
        schema = load_schema()
        assert isinstance(schema, dict)

    def test_contains_required_fields(self):
        schema = load_schema()
        assert schema.get("title") == "AetherlingConfig"
        assert "properties" in schema

    def test_unknown_schema_raises(self):
        with pytest.raises(FileNotFoundError):
            load_schema("nonexistent_schema")


class TestSchemaStructure:
    def test_schema_file_is_valid_json(self):
        raw = SCHEMA_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_required_properties_defined(self):
        schema = load_schema()
        required = schema.get("required", [])
        assert "id" in required
        assert "name" in required
        assert "cognitive_blocks" in required
        assert "constitution" in required

    def test_cognitive_blocks_has_memory_architecture(self):
        schema = load_schema()
        cb = schema["properties"]["cognitive_blocks"]["properties"]
        assert "memory_architecture" in cb

    def test_tool_ecosystem_items_defined(self):
        schema = load_schema()
        cb = schema["properties"]["cognitive_blocks"]["properties"]
        tool_items = cb["tool_ecosystem"]["items"]["properties"]
        assert "tool_name" in tool_items
        assert "permission_level" in tool_items

    def test_example_valid(self):
        """The built-in schema example should contain all required top-level keys."""
        schema = load_schema()
        example = schema["examples"][0]
        for key in schema["required"]:
            assert key in example, f"Example missing required key: {key}"
