"""Catalogue preservation and inactive ingestion contracts."""

import csv
import hashlib
import io
import json
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path

import pytest

from fishy.catalogue import CatalogueEntry, SourceIdentity, SourceRecord, SourceValue, parse_catalogue

DATA = Path(__file__).parents[1] / "src/fishy/data"


@pytest.fixture
def documents():
    return (
        (DATA / "parameter_catalogue.json").read_text(),
        {f"parameter_sources/{p.name}": p.read_text() for p in (DATA / "parameter_sources").glob("*.json")},
        (DATA / "public_parameter_seed.csv").read_text(),
    )


def record(value: SourceValue) -> SourceRecord:
    assert isinstance(value, SourceRecord)
    return value


def records(value: SourceValue) -> tuple[SourceRecord, ...]:
    assert isinstance(value, tuple)
    return tuple(record(item) for item in value)


def thaw(value):
    if isinstance(value, SourceRecord):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value


def test_all_entries_and_separate_seeds_preserved(documents):
    catalogue = parse_catalogue(*documents)
    original = json.loads(documents[0], parse_float=Fraction)
    assert len(catalogue.entries) == 456
    assert len(catalogue.seeds) == 8
    assert thaw(catalogue.document) == original
    assert [thaw(entry.raw) for entry in catalogue.entries] == original["entries"]
    assert [thaw(seed.raw) for seed in catalogue.seeds] == list(csv.DictReader(io.StringIO(documents[2])))
    assert all(entry.raw["enabled_by_default"] is False for entry in catalogue.entries)
    assert all(seed.raw["enabled_by_default"] == "false" for seed in catalogue.seeds)
    assert record(catalogue.entries[0].raw["parsed_cell"])["value"] == Fraction(1, 10000)
    for name, text in documents[1].items():
        assert thaw(catalogue.transcriptions[name]) == json.loads(text, parse_float=Fraction)


def test_source_categories_cell_kinds_and_conditional_rows(documents):
    catalogue = parse_catalogue(*documents)
    from collections import Counter

    assert Counter(record(e.raw["parsed_cell"])["kind"] for e in catalogue.entries) == {
        "scalar_candidate": 409,
        "two_numeric_endpoints_uninterpreted": 15,
        "qualified_or_textual": 23,
        "missing_or_dash": 9,
    }
    assert Counter(e.source_id for e in catalogue.entries) == {
        "sanpin_0083_24_annex6": 141,
        "paket7272_draft_annex1": 315,
    }
    sanpin = record(catalogue.transcriptions["parameter_sources/sanpin_annex6.json"])
    assert len([r for r in records(sanpin["rows"]) if r["source_number"] == 52]) == 3
    assert sanpin["qualifications_original"]
    paket = record(catalogue.transcriptions["parameter_sources/paket_annex1.json"])
    assert paket["legal_status"] == "draft_not_binding"
    assert len(records(paket["rows"])) == 63
    assert paket["explanatory_note_blocks"]
    assert any(c["shared_across_categories"] for r in records(paket["rows"]) for c in records(r["category_cells"]))


def test_deep_immutability(documents):
    catalogue = parse_catalogue(*documents)
    entry = catalogue.entries[0]
    with pytest.raises(FrozenInstanceError):
        catalogue.entries = ()  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError):
        entry.raw["enabled_by_default"] = True  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError):
        SourceRecord((("mutable", []),))  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError):
        CatalogueEntry({})  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("mutation", ["enabled", "duplicate", "absent_source", "bad_locator", "group"])
def test_corrupted_catalogue_refused(documents, mutation):
    raw = json.loads(documents[0])
    entry = raw["entries"][0]
    if mutation == "enabled":
        entry["enabled_by_default"] = True
    elif mutation == "duplicate":
        raw["entries"].append(entry)
    elif mutation == "absent_source":
        entry["source_id"] = "absent"
    elif mutation == "bad_locator":
        entry["source_locator"] = "parameter_sources/sanpin_annex6.json#/absent"
    else:
        entry["group_membership"] = "guessed"
    with pytest.raises((ValueError, KeyError)):
        parse_catalogue(json.dumps(raw), documents[1], documents[2])


def test_disabled_seed_required(documents):
    with pytest.raises(ValueError, match="disabled"):
        parse_catalogue(documents[0], documents[1], documents[2].replace(",false,", ",true,"))


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_refused(documents, number):
    raw = documents[0].replace('"value": 0.0001', f'"value": {number}', 1)
    with pytest.raises(ValueError, match="nonfinite"):
        parse_catalogue(raw, documents[1], documents[2])


def test_duplicate_json_fields_refused(documents):
    with pytest.raises(ValueError, match="duplicate"):
        parse_catalogue('{"entries": [], "entries": []}', documents[1], documents[2])


def test_source_hash_validation():
    with pytest.raises(ValueError, match="SHA-256"):
        SourceIdentity("source", "version", "not-a-digest", None)


def test_publication_manifest_and_safe_payloads():
    manifest = json.loads((DATA / "publication_manifest.json").read_text())
    for name, digest in manifest["published_sha256"].items():
        content = (DATA / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        assert b"/Users/" not in content
        assert b"original_docx_base64" not in content
        assert b"auxiliary_ooxml_parts" not in content
    assert (
        manifest["upstream_sha256"]["parameter_catalogue.json"]
        == manifest["published_sha256"]["parameter_catalogue.json"]
    )
    assert (
        manifest["upstream_sha256"]["public_parameter_seed.csv"]
        == manifest["published_sha256"]["public_parameter_seed.csv"]
    )


def test_mismatched_transcription_identity_refused(documents):
    transcriptions = dict(documents[1])
    name = "parameter_sources/sanpin_annex6.json"
    raw = json.loads(transcriptions[name])
    raw["source"]["sha256"] = "0" * 64
    transcriptions[name] = json.dumps(raw)
    with pytest.raises(ValueError, match="identity"):
        parse_catalogue(documents[0], transcriptions, documents[2])
