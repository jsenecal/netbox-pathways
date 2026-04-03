# Cable Routing Redesign

**Date:** 2026-04-03
**Status:** Approved

## Problem

CableSegment carried fields that didn't belong (`enter_point`, `exit_point`) and a user-editable `sequence` that should be system-managed. Slack storage was modeled as fields on CableSegment, but slack loops are physically located at structures along a cable's route — they're a separate concern. There was no route validation, no cable-specific map view, and cable routing items were scattered across menu groups.

## Design

### 1. CableSegment (simplified)

Through-table linking a cable to a pathway in its route.

| Field | Type | Notes |
|-------|------|-------|
| `cable` | FK → `dcim.Cable` | `on_delete=CASCADE`, `related_name='pathway_segments'` |
| `pathway` | FK → `Pathway` | `on_delete=SET_NULL`, null/blank, `related_name='cable_segments'` |
| `sequence` | `PositiveIntegerField` | Auto-managed, not exposed in forms. `null=True, blank=True` — `None` triggers auto-assignment on save. |
| `comments` | `TextField` | blank=True |
| + standard NetBox fields | | `tags`, `created`, `last_updated` |

- **Ordering:** `['cable', 'sequence']`
- **No unique constraint** on `(cable, pathway)` — a cable can traverse the same pathway more than once (slack loops, conduit junction return paths).
- **UniqueConstraint** on `(cable, sequence)` — sequence must be unique per cable.
- **`sequence` is not in forms** — it's set programmatically when building routes (via route finder or future route-building UI). For manual CableSegment creation, auto-assign `max(existing sequences for cable) + 1`.
- Remove `slack_loop_location` and `slack_length` fields (moved to SlackLoop).
- **Sequence gaps are acceptable** — deleting a segment leaves a gap (e.g., [1, 3]). Ordering always uses `ORDER BY sequence`, so gaps don't affect functionality. No automatic compaction.

### 2. SlackLoop (new model)

Represents stored slack at a point along a cable's route.

| Field | Type | Notes |
|-------|------|-------|
| `cable` | FK → `dcim.Cable` | `on_delete=CASCADE`, `related_name='slack_loops'` |
| `structure` | FK → `Structure` | Required. Slack is always at a structure (manhole, handhole, etc.) |
| `pathway` | FK → `Pathway` | Optional. For aerial slack stored on a span near the structure. |
| `length` | `FloatField` | Required, no default. Meters of slack stored. |
| `comments` | `TextField` | blank=True |
| + standard NetBox fields | | `tags`, `created`, `last_updated` |

- **Ordering:** `['cable', 'structure']`
- **Cardinality:** Multiple slack loops per cable per structure are valid (e.g., underground slack in the vault and aerial slack on the span leaving the vault). No `(cable, structure)` unique constraint.
- Underground slack: structure only. Aerial slack: structure + pathway (the span it's on).

Full CRUD: model, form, table, filter, serializer, API viewset, views, search index, UI panel, URLs.

**UI panels:** SlackLoop tables appear on both Cable detail pages (via template extension — all slack for this cable) and Structure detail pages (via template extension — all slack at this structure).

### 3. Route Validation

A shared utility function that checks whether a cable's route is physically connected.

**Location:** `netbox_pathways/routing.py` (new file — separate from `graph.py` which handles traversal algorithms)

**Signature:**
```python
def validate_cable_route(cable_id) -> dict:
    """
    Returns {
        'valid': bool,
        'segment_count': int,
        'gaps': [
            {
                'after_segment_id': int,
                'before_segment_id': int,
                'after_pathway': str,
                'before_pathway': str,
                'detail': str,  # human-readable gap description
            },
            ...
        ],
    }
    """
```

**Validation logic:** For each consecutive pair of segments (ordered by `sequence`), check that the pathways share a common endpoint. Endpoint resolution must handle the polymorphic nature of pathway subtypes — reuse the `_endpoint_nodes()` pattern from `graph.py` which returns canonical `(type, pk)` tuples covering Structure, Location, and ConduitJunction endpoints. Two consecutive segments are connected if their endpoint sets intersect.

**Advisory only** — does not block saves. Infrastructure documentation is often incomplete.

### 4. Cable Detail Template Extensions

Modifications to the existing `dcim.cable` template extensions:

#### 4a. Route Status Panel

Displayed on the cable detail page. Shows:
- Segment count
- Route status badge: "Complete", "N gaps", or "No segments"
- List of gaps (if any) with pathway names and missing connection details
- Link to pull sheet (only if route is complete)
- SlackLoop table for this cable

#### 4b. Cable Route Map

Modify the existing `CableRouteMapExtension` in `template_content.py` to incorporate route status information. Not a separate extension — enhances the existing map panel that already renders pathway route geometry on cable detail pages.

- The cable's pathway geometries highlighted and colored per segment
- Structures along the route as markers
- Same base layers as the main map (Street / Satellite)

Reuses existing `detail-map.ts` infrastructure.

### 5. Pull Sheet Gating

Pull sheets are only available for cables with a complete (valid) route.

- **Pull sheet list:** shows all cables with segments, adds a status column indicating route validity
- **Pull sheet detail:** returns an error message if the route has gaps, directing the user to fix the route first
- **Slack totals:** `PullSheetDetailView` queries `SlackLoop` for the cable to compute total slack. The pull sheet template shows a separate slack section with SlackLoop entries grouped by structure, replacing the old per-segment slack column.

### 6. Navigation

Reorganize the plugin menu. Move cable routing items into their own group:

```
Pathways (plugin menu)
├── Infrastructure
│   ├── Structures
│   ├── Conduits
│   ├── Aerial Spans
│   ├── Direct Buried
│   ├── Innerducts
│   ├── Conduit Banks
│   └── Junctions
├── Cable Routing
│   ├── Cable Segments
│   ├── Slack Loops
│   └── Pull Sheets  (moved from Tools)
├── GIS
│   ├── Map
│   ├── Site Geometries
│   └── Circuit Routes
└── Tools
    ├── Route Finder
    └── Neighbors
```

### 7. Migration

A single schema migration (no data migration — plugin is pre-release, no production data):
1. Creates the `SlackLoop` model
2. Removes `slack_loop_location` and `slack_length` from CableSegment
3. Re-adds `sequence` (PositiveIntegerField, default=0) to CableSegment
4. Updates Meta ordering to `['cable', 'sequence']`

## Files Affected

### New files
- `netbox_pathways/routing.py` — route validation logic
- Migration file for model changes

### Modified files
- `models.py` — CableSegment field changes + SlackLoop model
- `forms.py` — CableSegment form cleanup (including `CableSegmentImportForm`) + SlackLoopForm
- `tables.py` — CableSegment table update + SlackLoopTable
- `filters.py` — CableSegment filter update + SlackLoopFilterSet
- `api/serializers.py` — CableSegment serializer update + SlackLoopSerializer
- `api/views.py` — SlackLoop viewset + CableSegment queryset update
- `api/urls.py` — SlackLoop router registration
- `views.py` — SlackLoop views + pull sheet gating
- `urls.py` — SlackLoop URL patterns
- `search.py` — SlackLoop search index
- `ui/panels.py` — SlackLoop panel + CableSegment panel update
- `navigation.py` — menu reorganization
- `template_content.py` — route status panel + modify existing CableRouteMapExtension + SlackLoop panels on Cable/Structure detail
- `templates/netbox_pathways/pullsheet_detail.html` — gap check + slack section redesign

### Deleted files
- None (admin.py already removed)
