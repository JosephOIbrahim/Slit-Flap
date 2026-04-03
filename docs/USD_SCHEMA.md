# USD Schema Design — DEPARTURES

> Phase 2 document. Don't build this yet. This defines how project state
> maps to USD composition when the time comes.

## Prim Hierarchy

```
/departures                                ← root
  /departures/projects                     ← scope
    /departures/projects/brand_refresh     ← project prim (typed: DeparturesProject)
    /departures/projects/product_launch
    /departures/projects/ar_prototype
    ...
  /departures/sessions                     ← scope
    /departures/sessions/s_001             ← session prim
  /departures/notes                        ← scope
    /departures/notes/brand_refresh        ← flip-side notes prim
```

## Project Prim Schema

```usda
def DeparturesProject "brand_refresh" (
    variantSets = ["status"]
    variants = {
        string status = "ACTIVE"
    }
)
{
    string name = "Brand Refresh"
    string domain = "MIX"
    string track = "01"
    string next_action = "Finalize color palette + type system"
    string deadline = ""
    string bg_color = ""
    int mile = 3
    int mile_total = 6
    string today_time = "10:00"

    # Time-sampled for history
    string status.timeSamples = {
        1: "QUEUED",
        100: "ACTIVE",
    }

    string last_touched.timeSamples = {
        1: "2026-02-21T00:00:00Z",
        100: "2026-04-02T10:15:00Z",
    }
}
```

## Status as Variant Sets

```usda
variantSet "status" = {
    "QUEUED" { }
    "ACTIVE" { }
    "ROLLING" { }
    "BLOCKED" { }
    "REVIEW" { }
    "SHIPPED" { }
}
```

## Notes as customData

```usda
def "brand_refresh_notes" (
    customData = {
        string content = "<p>Color palette exploration notes...</p>"
        string updated_at = "2026-04-02T10:15:00Z"
    }
)
{
}
```

## Log Entries as Time-Sampled Attributes

```usda
string log_entry.timeSamples = {
    1: "Started research on type systems",
    50: "Narrowed to 3 typeface candidates",
    100: "Prototype layout with final selection",
}
```

## Composition Strategy

- **Root stage:** `departures.usda` — sublayers session stages
- **Per-session sublayers:** `session_001.usda` — strongest opinion (LIVRPS: L wins)
- **Project edits** are authored to the session sublayer, not the root
- **History** preserved by sublayer stack — old sessions are weaker but recoverable
- **Export:** flatten current state to single `.usda` for portability
- **Import:** parse `.usda`, populate SQLite tables

## Cognitive Twin Compatibility

Maps to the `AIMemoryChunk` pattern:
- Project prim → `capsule_type: "project"`
- Status variant → cognitive state mapping
- Time-sampled attributes → observation timeline
- Session sublayers → session lifecycle (register → heartbeat → close)

The `prim_path` in the capsule schema maps directly:
`/sessions/{session_id}/capsules/{capsule_id}` ↔ `/departures/sessions/s_001`
