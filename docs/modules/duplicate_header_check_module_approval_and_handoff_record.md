# DuplicateHeaderCheck — Module Approval and Handoff Record

## 1. Module

- DuplicateHeaderCheck

## 2. Status

- Approved

## 3. Approved Responsibilities

- Consume parsed DataRow objects from RowParser
- Consume HeaderInfo from HeaderResolver
- Perform exact tuple equality comparison:
  row.fields == header_info.resolved_columns
- Detect and count all verbatim header-duplicating rows
- Produce exactly one Finding

## 4. Approved Dependencies

- phenopred.domain.entities.DataRow
- phenopred.domain.value_objects.HeaderInfo
- phenopred.domain.value_objects.Finding
- Python standard library only

QualityCheck remains a provisional Protocol definition in phenopred.domain.interfaces. DuplicateHeaderCheck structurally satisfies the QualityCheck Protocol because it provides the required check() method. No explicit import, inheritance relationship, or runtime dependency exists between DuplicateHeaderCheck and QualityCheck.

## 5. Verified Behaviour

- exact equality only
- no trimming
- no normalization
- no case conversion
- full scan
- count all matches
- examples bounded to 10
- affected_row_refs bounded to 10
- DataRow.line_index used
- empty input returns zero-count Finding
- missing header returns zero-count Finding
- no exceptions for quality findings
- no mutation
- deterministic output
- stateless construction

## 6. Test Evidence

- 23/23 DuplicateHeaderCheck tests passing
- 31/31 RowParser tests passing
- 13/13 DataRow/entity tests passing
- regression validation completed

## 7. Known Limitations

- QualityCheck Protocol remains provisional
- Finding example/reference bound is fixed at 10
- Future CI pytest execution remains a standing validation item if applicable

## 8. Deferred Future Decisions

- MalformedRowCheck relationship with ColumnCountDistribution and Finding
- Column-name-resolution mechanism for MissingValueScanner, DuplicateRsidCheck, DuplicateChrPosCheck
- Final QualityCheck generic Protocol signature
- report_builder.py aggregation contract

## 9. Final Approval Statement

"DuplicateHeaderCheck module is approved and frozen."
