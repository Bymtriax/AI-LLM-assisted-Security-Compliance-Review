"""Shared data models for corpus construction and storage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, TypeAlias


MetadataValue: TypeAlias = str | int | float | bool
_RESERVED_METADATA_KEYS = frozenset({"id", "text"})
_REQUIRED_METADATA_TYPES: Final = {
    "document": str,
    "version": str,
    "language": str,
    "section": str,
    "parent_titles": str,
    "source_file": str,
    "pdf_page_start": int,
    "printed_page_start": str,
}
_NON_EMPTY_REQUIRED_METADATA_KEYS = frozenset(_REQUIRED_METADATA_TYPES) - {"printed_page_start"}

 
@dataclass(frozen=True)
class CorpusRecord:
    """One retrieval-sized corpus passage with immutable core data."""

    id: str
    text: str
    metadata: Mapping[str, MetadataValue]

    def __post_init__(self) -> None:
        for field_name, value in (("id", self.id), ("text", self.text)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Record {field_name} must be a non-empty string.")

        try:
            raw_metadata = dict(self.metadata)
        except (TypeError, ValueError) as error:
            raise ValueError("Record metadata must be a key-value mapping.") from error
        if any(not isinstance(key, str) or not key.strip() for key in raw_metadata):
            raise ValueError("Record metadata keys must be non-empty strings.")
        if any(not isinstance(value, (str, int, float, bool)) for value in raw_metadata.values()):
            raise ValueError("Record metadata values must be strings, numbers or booleans.")
        duplicated = _RESERVED_METADATA_KEYS.intersection(raw_metadata)
        if duplicated:
            raise ValueError(f"Record metadata cannot duplicate reserved fields: {sorted(duplicated)}")
        missing = [key for key in _REQUIRED_METADATA_TYPES if key not in raw_metadata]
        if missing:
            raise ValueError(f"Record metadata is missing required fields: {missing}")
        for key, expected_type in _REQUIRED_METADATA_TYPES.items():
            value = raw_metadata[key]
            if type(value) is not expected_type:
                raise ValueError(
                    f"Record metadata field {key!r} must be {expected_type.__name__}, "
                    f"not {type(value).__name__}."
                )
            if key in _NON_EMPTY_REQUIRED_METADATA_KEYS and isinstance(value, str) and not value.strip():
                raise ValueError(f"Record metadata field {key!r} cannot be empty.")
        if raw_metadata["pdf_page_start"] < 1:
            raise ValueError("Record metadata field 'pdf_page_start' must be positive.")

        object.__setattr__(self, "metadata", MappingProxyType(raw_metadata))
