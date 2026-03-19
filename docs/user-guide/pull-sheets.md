# Pull Sheets

Pull sheets are field crew documents that show the complete physical route of a cable through pathways, with lengths and slack requirements at each segment.

## What's Included

A pull sheet contains:

- **Cable header** — Cable ID, type, and endpoints
- **Route table** — Ordered list of pathway segments:

| Column | Description |
|--------|-------------|
| Sequence | Segment order |
| Pathway | Pathway name |
| Type | Conduit, aerial span, etc. |
| From | Entry structure or location |
| To | Exit structure or location |
| Length | Pathway segment length |
| Slack | Extra cable stored at this segment |

- **Totals** — Total route length and total slack

## Viewing Pull Sheets

1. Navigate to a Cable's detail page in NetBox
2. The **Pull Sheet** section shows the cable's route if Cable Segments are configured
3. Use the print button for a printer-friendly layout

## Setting Up Cable Segments

Pull sheets are generated from Cable Segments. To create a pull sheet:

1. Ensure your pathways and structures exist
2. Navigate to **Plugins > Pathways > Cable Segments**
3. Create segments linking the cable to each pathway in sequence

### Example

A cable running through three pathways:

| Seq | Pathway | Type | From | To | Length | Slack |
|-----|---------|------|------|----|--------|-------|
| 1 | C-101 | Conduit | Bldg A Entrance | MH-001 | 50m | 3m |
| 2 | C-205 | Conduit | MH-001 | MH-002 | 200m | 0m |
| 3 | C-310 | Conduit | MH-002 | Bldg B Entrance | 75m | 3m |
| | | | | **Total** | **325m** | **6m** |

## API Access

Pull sheet data can be retrieved via the REST API by querying Cable Segments filtered by cable:

```
GET /api/plugins/pathways/cable-segments/?cable_id={id}&ordering=sequence
```

This returns the ordered list of segments with pathway details, suitable for generating custom pull sheet formats.

## Tips

- Keep sequence numbers consistent — gaps are fine but order matters
- Record slack at entry/exit points for accurate cable length calculations
- Add access notes on structures to help field crews locate entry points
- Use the print layout for field-ready documents
