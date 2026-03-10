# SVG Marker Shapes — Design

**Date**: 2026-03-10
**Status**: Approved

## Goal

Replace circular DivIcon markers with inline SVG shapes that match the structure type — circles for manholes, squares for cabinets, diamonds for telecom closets, triangles for roofs, etc.

## Current State

All structure markers use an 18×18px `L.divIcon` with a circular `pw-marker-pin` div (`border-radius: 50%`) containing a small MDI font icon. The icon encodes shape semantics (e.g., `mdi-rhombus` for telecom closets) but the outer container is always circular.

## Approach

Inline SVG inside `L.divIcon`. Each marker contains a ~20×20px SVG with the shape as a native SVG element, filled with the structure color, white stroke for contrast, and CSS `drop-shadow` for depth.

## Shape Catalog

| Shape ID | SVG Element | Fill | Stroke | Used By |
|----------|------------|------|--------|---------|
| `circle-filled` | `<circle r="8"/>` | color | white 1.5px | manhole |
| `circle-outline` | `<circle r="8"/>` | transparent | color 2.5px | handhole, pole |
| `circle-dot` | circle + `<circle r="2.5"/>` | color (outer transparent, inner filled) | color 2.5px | splice_closure |
| `square-filled` | `<rect rx="2"/>` | color | white 1.5px | vault |
| `square-rounded` | `<rect rx="4"/>` | color | white 1.5px | cabinet |
| `square-outline` | `<rect rx="2"/>` | transparent | color 2.5px | pedestal, equipment_room |
| `square-dot` | rect + `<circle r="2.5"/>` | color (outer transparent, inner filled) | color 2.5px | building_entrance |
| `diamond-filled` | `<rect transform="rotate(45)"/>` | color | white 1.5px | telecom_closet |
| `diamond-outline` | `<rect transform="rotate(45)"/>` | transparent | color 2.5px | riser_room |
| `triangle` | `<polygon points="10,1 19,18 1,18"/>` | color | white 1.5px | roof |
| `crosshair` | circle + cross `<line>`s | transparent (circle) | color 2.5px | tower |

## Filled vs Outline

- **Filled**: Structure color fill, 1.5px white stroke — solid, prominent
- **Outline**: Transparent fill, 2.5px structure-colored stroke — hollow, lighter weight

## Marker Size

20×20px (up from 18×18). Anchor at center (10, 10). Popup anchor (0, -10).

## Selection Highlight

Existing `pw-marker-selected` blue glow via `box-shadow` on the DivIcon container — unchanged, works regardless of inner content.

## Files to Change

- `pathways-map.ts`: Replace `STRUCTURE_ICONS` with `STRUCTURE_SHAPES` map, rewrite `_structureIcon()` to emit inline SVG
- `leaflet-theme.css`: Remove `.pw-marker-pin` circle styles (border-radius, background, MDI font rules), add `.pw-marker svg` styling (drop-shadow, dimensions)
- No template changes needed — markers are created in JS

## What's NOT Changing

- `STRUCTURE_COLORS` map — same colors
- Cluster icons — still use ring/circle style
- Pathway line styles — unaffected
- Selection/highlight logic — unaffected
- MDI dependency — still used elsewhere in the plugin (sidebar, detail panel)
