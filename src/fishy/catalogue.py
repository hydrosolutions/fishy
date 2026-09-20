"""parse_catalogue : SourceTranscription × SeedTranscription → SourceCatalogue.

Preserve inactive source evidence. This module neither selects nor activates rules.
The caller reads documents; decimal JSON tokens retain exact rational values.
"""

import csv
import io
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from fractions import Fraction

type SourceValue = str | int | Fraction | bool | None | tuple[SourceValue, ...] | SourceRecord


@dataclass(frozen=True)
class SourceRecord(Mapping[str, SourceValue]):
    """An immutable source object, retaining every supplied field."""

    fields: tuple[tuple[str, SourceValue], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.fields, tuple):
            raise TypeError("source fields must be an immutable tuple")
        keys = []
        for pair in self.fields:
            if not isinstance(pair, tuple) or len(pair) != 2 or not isinstance(pair[0], str):
                raise TypeError("source fields must be named pairs")
            keys.append(pair[0])
            _immutable(pair[1])
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate source field")

    def __getitem__(self, key: str) -> SourceValue:
        for name, value in self.fields:
            if name == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (name for name, _ in self.fields)

    def __len__(self) -> int:
        return len(self.fields)


def _immutable(value: SourceValue) -> None:
    if isinstance(value, tuple):
        for item in value:
            _immutable(item)
    elif not isinstance(value, (str, int, Fraction, bool, SourceRecord, type(None))):
        raise TypeError("source values must be immutable; numeric decimals must be exact")


def _object(pairs: list[tuple[str, SourceValue]]) -> SourceRecord:
    return SourceRecord(tuple((k, _freeze(v)) for k, v in pairs))


def _freeze(value):
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _reject_constant(value: str):
    raise ValueError(f"nonfinite source number: {value}")


def _document(text: str) -> SourceRecord:
    result = json.loads(text, object_pairs_hook=_object, parse_float=Fraction, parse_constant=_reject_constant)
    if not isinstance(result, SourceRecord):
        raise ValueError("source document must be an object")
    return result


def _text(record: SourceRecord, key: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be nonempty text")
    return value


def _records(record: SourceRecord, key: str) -> tuple[SourceRecord, ...]:
    value = record[key]
    if not isinstance(value, tuple) or not all(isinstance(v, SourceRecord) for v in value):
        raise ValueError(f"{key} must contain source records")
    return tuple(v for v in value if isinstance(v, SourceRecord))


@dataclass(frozen=True)
class SourceIdentity:
    source_id: str
    version: str
    sha256: str
    url: str | None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.version.strip():
            raise ValueError("source identity and version are required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("source SHA-256 must contain 64 lowercase hexadecimal digits")
        if self.url is not None and not self.url.startswith(("https://", "http://")):
            raise ValueError("source URL must be explicit HTTP(S) or missing")


@dataclass(frozen=True)
class CatalogueEntry:
    """Inactive source cell, not an executable numerical constraint."""

    raw: SourceRecord

    def __post_init__(self) -> None:
        if not isinstance(self.raw, SourceRecord):
            raise TypeError("entry requires an immutable source record")
        for key in ("entry_id", "source_id", "category_id", "parameter_name_raw", "source_locator"):
            _text(self.raw, key)
        if self.raw["enabled_by_default"] is not False:
            raise ValueError("catalogue entries must remain inactive")
        if self.raw["group_membership"] is not None:
            raise ValueError("source labels cannot establish group membership")

    @property
    def entry_id(self) -> str:
        return _text(self.raw, "entry_id")

    @property
    def source_id(self) -> str:
        return _text(self.raw, "source_id")


@dataclass(frozen=True)
class SeedRule:
    """A separately preserved, disabled seed; all CSV cells remain text."""

    raw: SourceRecord

    def __post_init__(self) -> None:
        if not isinstance(self.raw, SourceRecord):
            raise TypeError("seed requires an immutable source record")
        for key in ("rule_id", "source_id", "source_version", "interpretation_status"):
            _text(self.raw, key)
        if self.raw["enabled_by_default"] != "false":
            raise ValueError("seed rules must remain disabled")

    @property
    def rule_id(self) -> str:
        return _text(self.raw, "rule_id")


@dataclass(frozen=True)
class SourceCatalogue:
    document: SourceRecord
    sources: tuple[SourceIdentity, ...]
    entries: tuple[CatalogueEntry, ...]
    seeds: tuple[SeedRule, ...]
    transcriptions: SourceRecord

    def __post_init__(self) -> None:
        for values, expected in (
            (self.sources, SourceIdentity),
            (self.entries, CatalogueEntry),
            (self.seeds, SeedRule),
        ):
            if not isinstance(values, tuple) or not all(isinstance(v, expected) for v in values):
                raise TypeError("catalogue collections must be immutable domain records")
        for ids in (
            tuple(s.source_id for s in self.sources),
            tuple(e.entry_id for e in self.entries),
            tuple(s.rule_id for s in self.seeds),
        ):
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate catalogue identity")
        source_ids = {s.source_id for s in self.sources}
        if any(e.source_id not in source_ids for e in self.entries):
            raise ValueError("entry refers to an absent source")
        if not self.entries or not self.seeds:
            raise ValueError("catalogue and separate seed records are required")


def parse_catalogue(catalogue_json: str, source_transcriptions: Mapping[str, str], seed_csv: str) -> SourceCatalogue:
    """Parse supplied documents without policy inference or filesystem access.

    Transcription mapping keys are the catalogue's relative transcription names.
    Numeric source candidates are Fractions; they remain uninterpreted candidates.
    """
    document = _document(catalogue_json)
    identities = []
    transcriptions = []
    for source in _records(document, "sources"):
        url = source["source_url"]
        if url is not None and not isinstance(url, str):
            raise ValueError("source URL must be text or missing")
        identity = SourceIdentity(
            _text(source, "source_id"), _text(source, "source_version"), _text(source, "sha256"), url
        )
        name = _text(source, "transcription")
        transcription = _document(source_transcriptions[name])
        if transcription["schema"] == "source-transcription-annex6-v1":
            provenance = transcription["source"]
        elif transcription["schema"] == "lossless-draft-annex1-extraction-v1":
            provenance_sources = transcription["sources"]
            if not isinstance(provenance_sources, SourceRecord):
                raise ValueError("transcription source identity is missing")
            provenance = provenance_sources["docx"]
        else:
            raise ValueError("unsupported source transcription schema")
        if not isinstance(provenance, SourceRecord) or provenance["sha256"] != identity.sha256:
            raise ValueError("transcription source identity does not match catalogue")
        identities.append(identity)
        transcriptions.append((name, transcription))
    reader = csv.DictReader(io.StringIO(seed_csv))
    if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("missing or duplicate seed columns")
    seeds = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("seed row does not match its columns")
        seeds.append(SeedRule(SourceRecord(tuple(row.items()))))
    entries = tuple(CatalogueEntry(raw) for raw in _records(document, "entries"))
    result = SourceCatalogue(document, tuple(identities), entries, tuple(seeds), SourceRecord(tuple(transcriptions)))
    for entry in result.entries:
        locator = _text(entry.raw, "source_locator")
        filename, pointer = locator.split("#", 1)
        node = result.transcriptions[filename]
        for token in pointer.lstrip("/").split("/"):
            if isinstance(node, SourceRecord):
                node = node[token.replace("~1", "/").replace("~0", "~")]
            elif isinstance(node, tuple):
                node = node[int(token)]
            else:
                raise ValueError(f"unresolved source locator: {locator}")
    return result
