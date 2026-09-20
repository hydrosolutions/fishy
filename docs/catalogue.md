# Inactive quality source catalogue

`fishy.catalogue.parse_catalogue` preserves source records. It does not produce
executable limits, select a national profile, assign chemistry, or activate quality.

The packaged data under `fishy/data/` contain:

- All 456 source entries: 141 physical SanPiN 0083-24 Annex 6 rows (139 numbered
  entries, including three silicon rows), and 315 draft Paket 7272 Annex 1
  parameter/category cells (60 main and three supplementary parameters).
- Eight **separate**, disabled general/Annex-5 seed rules. These are not additional
  annex catalogue entries or a complete applicable profile.
- Original names, raw cells, chemical formula typography, source-local categories,
  units, harmfulness and hazard metadata, qualifications, notes and merged-cell
  references. No spelling repair or chemical identity reconciliation occurs.

## Read supplied documents at the application boundary

```python
from importlib.resources import files
from fishy.catalogue import parse_catalogue

root = files("fishy").joinpath("data")
catalogue = parse_catalogue(
    root.joinpath("parameter_catalogue.json").read_text(encoding="utf-8"),
    {
        f"parameter_sources/{name}.json": root.joinpath(
            "parameter_sources", f"{name}.json"
        ).read_text(encoding="utf-8")
        for name in ("sanpin_annex6", "paket_annex1")
    },
    root.joinpath("public_parameter_seed.csv").read_text(encoding="utf-8"),
)
entry = catalogue.entries[0]
print(entry.entry_id, entry.raw["limit_raw"])
```

Records and nested source objects are immutable. JSON decimal tokens become exact
`Fraction` values; CSV cells remain literal strings. A parsed numeric candidate
is still source evidence, not a limit. The source contains 409 scalar candidates,
15 uninterpreted endpoint pairs, 23 qualified/textual cells and nine missing/dash
cells. A scalar does not imply an upper bound. A dash is not zero. Hazard labels
are not group membership. The API rejects enabled records, inferred membership,
duplicate identities, absent sources, unresolved row pointers and mismatched
original-source identities. It does not authenticate source contents against a
remote publisher. The supplied manifest permits independent local byte checks.

## Provenance and publication boundary

The authoritative supplied bundle is identified by the accepted implementation
vision. Its `report_snapshot/quality_support/` catalogue and seed CSV are retained
byte-for-byte. `publication_manifest.json` records upstream and published SHA-256
identities and the exact omitted/changed JSON pointers.

The source transcriptions are deliberately sanitized derivatives, **not**
byte-identical source copies. Private filesystem paths, the embedded complete
DOCX binary and auxiliary OOXML parts are omitted. The claim that the embedded
DOCX can be recovered is replaced, and its round-trip verification field is
removed. Table cells, formula runs, table layout relationships, all substantive
notes, source hashes and qualification links are retained. The catalogue's
`transcription_sha256` identifies the original supplied transcription, not the
sanitized derivative; use the publication manifest for derivative hashes.

SanPiN's original source SHA-256 is
`ef4ba7fe646bd1cfe8574f45dd13bda1f53a22cd60e919273cf8ac07c0f2b3e6`,
with public source URL <https://lex.uz/docs/7340751#7355216>.
The held draft Annex 1 DOCX SHA-256 is
`2190e94f6e5340d5cacf40766848585550c7d826b4c87b14df11ceeadc0f8b57`.
Its publisher URL is absent, not invented. No new retrieval, legal-currency check,
licence grant or official authentication is implied. No full report, restricted
methodological paper, full handover or original binary is redistributed here.

## Limits on use

Paket 7272 remains a nonbinding draft. Source А–Д categories have no inferred
strictness order and no automatic mapping to seed I/II categories. Source notes
apply even when a row has no individual ambiguity flag. Source text and parsed
candidate values do not prove chemical form, reporting basis, conservativeness,
applicability or sampling support.

A modeller must separately identify and qualify a versioned profile, including
required parameters, applicability/exclusions, forms, units, operators and
strictness, conditional meanings, sampling intervals, uncertainty and complete
authorised or explicitly hypothetical groups. SanPiN §§5/22 and draft §35 remain
separate. SanPiN §22's equality conflict remains unresolved unless a labelled
scenario interpretation is selected. The two annexes do not cover all quality
duties. Passing selected tests is not national compliance or official approval.
