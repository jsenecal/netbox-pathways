# Quick Start

This guide walks through creating your first infrastructure records in NetBox Pathways.

## Step 1: Create Structures

Structures represent physical locations where cables enter, exit, or transition between pathway types. Start by creating at least two structures.

1. Navigate to **Plugins > Pathways > Structures**
2. Click **Add**
3. Fill in the required fields:
    - **Name**: A unique identifier (e.g., `MH-001`)
    - **Structure Type**: Select the type (e.g., Manhole)
    - **Site**: Assign to a NetBox site
    - **Location**: Click the map to place the structure, or enter coordinates directly
4. Save and repeat for your second structure

!!! tip
    Assign structures to NetBox Sites to enable site-based filtering throughout the plugin.

## Step 2: Create a Pathway

Pathways connect structures. Create a conduit between your two structures.

1. Navigate to **Plugins > Pathways > Conduits**
2. Click **Add**
3. Fill in the fields:
    - **Name**: e.g., `C-001`
    - **Start Structure**: Select your first structure
    - **End Structure**: Select your second structure
    - **Path**: Draw the route on the map
    - **Material**: e.g., PVC
    - **Inner Diameter**: e.g., `100` mm
4. Save

You can also create **Aerial Spans**, **Direct Buried** routes, or **Innerducts** following the same pattern.

## Step 3: Create a Conduit Bank

If your structure has a wall with multiple conduit openings (common in manholes), create a conduit bank.

1. Navigate to **Plugins > Pathways > Conduit Banks**
2. Click **Add**
3. Fill in:
    - **Name**: e.g., `MH-001 North Wall`
    - **Structure**: Select the structure
    - **Configuration**: e.g., 2x3 (2 rows, 3 columns)
    - **Total Conduits**: `6`
4. Save

Then edit your conduits to assign them a **Conduit Bank** and **Bank Position** (e.g., `A1`, `B2`).

## Step 4: Route a Cable

Link a NetBox `dcim.Cable` to pathways using Cable Segments.

1. First, ensure you have a Cable created in NetBox under **Devices > Cables**
2. Navigate to **Plugins > Pathways > Cable Segments**
3. Click **Add**
4. Fill in:
    - **Cable**: Select the NetBox cable
    - **Pathway**: Select the conduit or pathway
    - **Sequence**: `1` (order of this segment in the cable's route)
    - **Slack Length**: Any slack at this segment (meters)
5. Add more segments to trace the full route of the cable

## Step 5: View the Map

Navigate to **Plugins > Pathways > Map** to see your infrastructure:

- Structure markers show locations with type-specific shapes and colors
- Pathway lines connect structures with type-specific styling
- Click any feature to see details in the sidebar
- Use layer toggles to show/hide feature types

## Step 6: Generate a Pull Sheet

Once cable segments are configured:

1. Navigate to the Cable detail page in NetBox
2. Look for the **Pull Sheet** section
3. The pull sheet shows the ordered route: each pathway segment, its type, endpoints, length, and slack

## Next Steps

- [Concepts](../user-guide/concepts.md) — Understand the data model in depth
- [Interactive Map](../user-guide/interactive-map.md) — Full map feature reference
- [QGIS Integration](../user-guide/qgis-integration.md) — Connect GIS tools to your data
- [API Examples](../developer/api-examples.md) — Automate with the REST API
