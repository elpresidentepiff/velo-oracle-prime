# Horse Identity Bridge V1

## Purpose

The Racing Post archive only becomes measurable when horses can be connected to VÉLØ, Racing API, RPDC, and Sigma truth. This bridge is the conservative identity layer between archive context and outcome evidence.

## Inputs

- Racing Post horse dossiers.
- Racing Post racecard archive.
- VÉLØ runner snapshots.
- Local VÉLØ verdict artifacts.
- RPDC historical memory.
- Sigma result artifacts where available.

## Matching Hierarchy

1. Exact RP horse id where a downstream source carries it.
2. Exact normalized horse name plus race date.
3. Exact normalized horse name plus race date/course.
4. Exact normalized horse name against RPDC/Sigma memory.
5. Fuzzy match only when confidence is explicit and ambiguity is reported.

No ambiguous match is silently merged.

## Classifications

- `IDENTITY_CONFIRMED`: RP horse matched to VÉLØ runner snapshot or VÉLØ verdict identity.
- `NAME_MATCH_ONLY`: RP horse matched only by name to RPDC/Sigma memory.
- `MULTI_MATCH_AMBIGUOUS`: multiple plausible matches; manual review required.
- `RP_ONLY`: RP context exists, but no local VÉLØ/Racing API/RPDC/Sigma match exists.
- `VELO_ONLY`: reserved for future reverse-bridge rows where VÉLØ has a horse not present in RP.
- `NEEDS_MANUAL_REVIEW`: insufficient or conflicting evidence.

## Confidence

- `0.92`: normalized name + date + course.
- `0.86`: normalized name + date.
- `0.72`: normalized name only.
- `0.00`: no match or ambiguous match.

## Governance

The bridge is read-only and has no scoring impact. It does not promote RP fields. It only lets us measure which archive context fields become useful after outcomes exist.

RPR remains `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`.

## Why It Matters

Without identity, RP is a library. With identity, RP becomes testable intelligence:

`Identity -> Outcome -> Signal Value`
