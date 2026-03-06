# Pull Sheets

A pull sheet is a document used by field crews when pulling cable through conduit and pathway infrastructure. It shows the complete route a cable takes — which pathway segments, in what order, with entry/exit points, lengths, and slack requirements.

## Accessing Pull Sheets

Navigate to **Plugins → Pathways → Pull Sheets** to see a list of cables that have pathway segments routed.

Click **View Pull Sheet** on any cable to see its complete routing document.

Direct URL: `/plugins/pathways/pull-sheets/`

## Pull Sheet Contents

### Cable Header

- **Cable label** — The NetBox cable identifier
- **Type** — Cable type (fiber, copper, etc.)
- **Status** — Cable status (planned, installed, etc.)
- **Cable length** — Total cable length from NetBox
- **Color** — Cable color code
- **Description** — Cable description

### Route Table

Each row represents one segment of the cable's route, ordered by sequence:

| Column | Description |
|--------|-------------|
| **#** | Sequence number |
| **Pathway** | Name of the pathway segment (links to pathway detail) |
| **Type** | Pathway type (Conduit, Aerial, Direct Buried, etc.) |
| **From** | Start endpoint (structure or location name) |
| **To** | End endpoint (structure or location name) |
| **Length** | Pathway segment length in meters |
| **Slack** | Slack length at this segment in meters |
| **Notes** | Segment-specific comments |

### Totals

- **Total Pathway Length** — Sum of all pathway segment lengths
- **Total Slack** — Sum of all slack lengths
- **Estimated Pull Length** — Pathway length + slack

## Printing

Click the **Print** button on any pull sheet to produce a clean printout. The button is hidden in print output.

## Setting Up Cable Routes

To create a pull sheet for a cable, you need to define its route using Cable Segments:

1. Navigate to **Plugins → Pathways → Cable Segments**
2. Click **Add**
3. Select the **Cable** from NetBox
4. Select the **Pathway** segment the cable passes through
5. Set the **Sequence** number (order in the route)
6. Optionally set entry/exit points, slack loop location, and slack length
7. Repeat for each pathway segment in the cable's route

### Example Route

A cable running from Manhole A to Building B through three pathway segments:

| Sequence | Pathway | Type | From | To |
|----------|---------|------|------|----|
| 1 | C-001 | Conduit | Manhole A | Pole 5 |
| 2 | AS-005 | Aerial | Pole 5 | Pole 12 |
| 3 | C-042 | Conduit | Pole 12 | Building B |

## API Access

Cable segment routing data is also available via the REST API:

```bash
# Get all segments for a specific cable
curl -H "Authorization: Token <your-token>" \
  "https://your-netbox/api/plugins/pathways/cable-segments/?cable_id=42"
```
