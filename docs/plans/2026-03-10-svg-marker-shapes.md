# SVG Marker Shapes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace circular DivIcon markers with inline SVG shapes that visually match each structure type (circles, squares, diamonds, triangles, crosshairs).

**Architecture:** A new `STRUCTURE_SHAPES` map replaces `STRUCTURE_ICONS`, mapping each structure type to an SVG markup string. The `_structureIcon()` function emits inline SVG instead of an MDI font icon inside a colored circle. The sidebar highlight uses the same SVG shapes at a larger size. CSS is simplified — `.pw-marker-pin` and `.mdi` rules are replaced by `.pw-marker svg` styling.

**Tech Stack:** TypeScript, Leaflet `L.divIcon`, inline SVG, CSS `filter: drop-shadow`

---

### Task 1: Define SVG shape catalog and replace `STRUCTURE_ICONS` in `pathways-map.ts`

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/src/pathways-map.ts:38-75`

**Step 1: Replace `STRUCTURE_ICONS` with `STRUCTURE_SHAPES`**

Replace lines 38-52 (`STRUCTURE_ICONS` map) with:

```typescript
const STRUCTURE_SHAPES: Record<string, string> = {
    'pole':               '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/>',
    'manhole':            '<circle cx="10" cy="10" r="8"/>',
    'handhole':           '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/>',
    'cabinet':            '<rect x="2" y="2" width="16" height="16" rx="4"/>',
    'vault':              '<rect x="2" y="2" width="16" height="16" rx="2"/>',
    'pedestal':           '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/>',
    'building_entrance':  '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'splice_closure':     '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'tower':              '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><line x1="10" y1="2" x2="10" y2="18" stroke-width="1.5"/><line x1="2" y1="10" x2="18" y2="10" stroke-width="1.5"/>',
    'roof':               '<polygon points="10,2 18,17 2,17"/>',
    'equipment_room':     '<rect x="3" y="3" width="14" height="14" rx="4" fill="none" stroke-width="2.5"/>',
    'telecom_closet':     '<rect x="3" y="3" width="10" height="10" rx="1" transform="rotate(45 10 10)"/>',
    'riser_room':         '<rect x="3.5" y="3.5" width="9" height="9" rx="1" fill="none" stroke-width="2.5" transform="rotate(45 10 10)"/>',
};
```

**Step 2: Rewrite `_structureIcon()` to emit SVG**

Replace lines 64-75 with:

```typescript
function _structureIcon(type: string, size = 20): L.DivIcon {
    const color = STRUCTURE_COLORS[type] || '#616161';
    const shape = STRUCTURE_SHAPES[type] || '<circle cx="10" cy="10" r="8"/>';
    const half = size / 2;
    return L.divIcon({
        className: 'pw-marker',
        html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="' + size +
              '" height="' + size + '" stroke="white" fill="' + color + '">' +
              shape + '</svg>',
        iconSize: [size, size] as [number, number],
        iconAnchor: [half, half] as [number, number],
        popupAnchor: [0, -(half + 2)] as [number, number],
    });
}
```

**Step 3: Update `setDeps()` call — rename `structureIcons` to `structureShapes`**

In the `setDeps()` call (~line 333), change:
```typescript
        structureIcons: STRUCTURE_ICONS,
```
to:
```typescript
        structureShapes: STRUCTURE_SHAPES,
```

**Step 4: Build and verify no TypeScript errors**

Run: `cd netbox_pathways/static/netbox_pathways && npm run typecheck`
Expected: Errors in sidebar.ts (references old `STRUCTURE_ICONS`) — that's expected, we fix it next task.

**Step 5: Commit**

```
git add netbox_pathways/static/netbox_pathways/src/pathways-map.ts
git commit -m "feat(map): replace STRUCTURE_ICONS with SVG STRUCTURE_SHAPES"
```

---

### Task 2: Update `sidebar.ts` to use SVG shapes for highlighting

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/src/sidebar.ts:21,83-101,888-908`

**Step 1: Rename the dependency**

Line 21, change:
```typescript
let STRUCTURE_ICONS: Record<string, string>;
```
to:
```typescript
let STRUCTURE_SHAPES: Record<string, string>;
```

**Step 2: Update `_applyHighlightVisuals()` — SVG selected marker**

Replace the structure branch (lines 88-101) with:

```typescript
    if (entry.featureType === 'structure') {
        const marker = layer as L.Marker & { _origIcon?: L.Icon | L.DivIcon };
        marker._origIcon = (marker as any).getIcon();
        const type = entry.props.structure_type || '';
        const color = STRUCTURE_COLORS[type] || '#616161';
        const shape = STRUCTURE_SHAPES[type] || '<circle cx="10" cy="10" r="8"/>';
        marker.setIcon(L.divIcon({
            className: 'pw-marker pw-marker-selected',
            html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="26" height="26"' +
                  ' stroke="white" fill="' + color + '">' + shape + '</svg>',
            iconSize: [26, 26] as [number, number],
            iconAnchor: [13, 13] as [number, number],
            popupAnchor: [0, -14] as [number, number],
        }));
    }
```

**Step 3: Update `SidebarDeps` interface and `setDeps()`**

In the `SidebarDeps` interface (~line 894), change:
```typescript
    structureIcons: Record<string, string>;
```
to:
```typescript
    structureShapes: Record<string, string>;
```

In `setDeps()` (~line 905), change:
```typescript
    STRUCTURE_ICONS = deps.structureIcons;
```
to:
```typescript
    STRUCTURE_SHAPES = deps.structureShapes;
```

**Step 4: Build and verify no TypeScript errors**

Run: `cd netbox_pathways/static/netbox_pathways && npm run typecheck`
Expected: PASS (both pathways-map.ts and sidebar.ts now use `STRUCTURE_SHAPES`)

**Step 5: Commit**

```
git add netbox_pathways/static/netbox_pathways/src/sidebar.ts
git commit -m "feat(map): update sidebar highlight to use SVG shapes"
```

---

### Task 3: Update `detail-map.ts` to use SVG shapes

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/src/detail-map.ts:217-256,349-358`

**Step 1: Replace `STRUCTURE_ICONS` with `STRUCTURE_SHAPES`**

Replace lines 217-231 with:

```typescript
    const STRUCTURE_SHAPES: Record<string, string> = {
        'Pole':               '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/>',
        'Manhole':            '<circle cx="10" cy="10" r="8"/>',
        'Handhole':           '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/>',
        'Cabinet':            '<rect x="2" y="2" width="16" height="16" rx="4"/>',
        'Vault':              '<rect x="2" y="2" width="16" height="16" rx="2"/>',
        'Pedestal':           '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/>',
        'Building Entrance':  '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
        'Splice Closure':     '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
        'Tower':              '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><line x1="10" y1="2" x2="10" y2="18" stroke-width="1.5"/><line x1="2" y1="10" x2="18" y2="10" stroke-width="1.5"/>',
        'Rooftop':            '<polygon points="10,2 18,17 2,17"/>',
        'Equipment Room':     '<rect x="3" y="3" width="14" height="14" rx="4" fill="none" stroke-width="2.5"/>',
        'Telecom Closet':     '<rect x="3" y="3" width="10" height="10" rx="1" transform="rotate(45 10 10)"/>',
        'Riser Room':         '<rect x="3.5" y="3.5" width="9" height="9" rx="1" fill="none" stroke-width="2.5" transform="rotate(45 10 10)"/>',
    };
```

Note: detail-map uses display labels as keys (e.g., `'Pole'`) not slug keys (e.g., `'pole'`).

**Step 2: Rewrite `_structureIcon()` to emit SVG**

Replace lines 239-250 with:

```typescript
    function _structureIcon(type: string, size = 20): L.DivIcon {
        const color: string = STRUCTURE_COLORS[type] || '#616161';
        const shape: string = STRUCTURE_SHAPES[type] || '<circle cx="10" cy="10" r="8"/>';
        const half: number = size / 2;
        return L.divIcon({
            className: 'pw-marker',
            html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="' + size +
                  '" height="' + size + '" stroke="white" fill="' + color + '">' +
                  shape + '</svg>',
            iconSize: [size, size] as [number, number],
            iconAnchor: [half, half] as [number, number],
            popupAnchor: [0, -(half + 2)] as [number, number],
        });
    }
```

**Step 3: Update fallback icon in `_addInlineData()`**

Replace lines 351-358 (the fallback `L.divIcon` for non-structure points) with:

```typescript
                    : L.divIcon({
                        className: 'pw-marker',
                        html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="28" height="28"' +
                              ' stroke="white" fill="' + (pt.color || '#1565c0') + '">' +
                              '<circle cx="10" cy="10" r="8"/></svg>',
                        iconSize: [28, 28] as [number, number],
                        iconAnchor: [14, 14] as [number, number],
                        popupAnchor: [0, -16] as [number, number],
                    });
```

**Step 4: Typecheck**

Run: `cd netbox_pathways/static/netbox_pathways && npm run typecheck`
Expected: PASS

**Step 5: Commit**

```
git add netbox_pathways/static/netbox_pathways/src/detail-map.ts
git commit -m "feat(map): update detail-map markers to SVG shapes"
```

---

### Task 4: Update CSS — remove old marker-pin styles, add SVG styling

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/css/leaflet-theme.css:107-140`

**Step 1: Replace marker CSS**

Replace lines 107-140 (everything from `/* --- Structure marker icons ---` through the dark-mode selected rule) with:

```css
/* --- Structure marker icons --------------------------------------- */

.pw-marker {
    background: none !important;
    border: none !important;
}

.pw-marker-svg {
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.4));
    stroke-width: 1.5;
}

/* Outline-style shapes set their own stroke-width; inherit fill/stroke from SVG */

/* Selected marker highlight */
.pw-marker-selected .pw-marker-svg {
    filter: drop-shadow(0 0 3px rgba(32, 107, 196, 0.7))
            drop-shadow(0 0 8px rgba(32, 107, 196, 0.5));
}
[data-bs-theme="dark"] .pw-marker-selected .pw-marker-svg {
    filter: drop-shadow(0 0 3px rgba(99, 163, 230, 0.8))
            drop-shadow(0 0 10px rgba(99, 163, 230, 0.5));
}
```

**Step 2: Remove unused CSS variables**

In the `:root` block (line 20-21), remove:
```css
    --pw-map-marker-bg: #fff;
    --pw-map-marker-border: #000;
```

In the `[data-bs-theme="dark"]` block (lines 38-39), remove:
```css
    --pw-map-marker-bg: #343a40;
    --pw-map-marker-border: #adb5bd;
```

These were only used conceptually for markers and are no longer needed.

**Step 3: Build and verify**

Run: `cd netbox_pathways/static/netbox_pathways && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```
git add netbox_pathways/static/netbox_pathways/css/leaflet-theme.css
git commit -m "feat(map): update CSS for SVG marker shapes"
```

---

### Task 5: Visual verification and final build

**Step 1: Full build**

Run: `cd netbox_pathways/static/netbox_pathways && npm run build`
Expected: Build succeeds, `dist/` updated

**Step 2: Typecheck**

Run: `cd netbox_pathways/static/netbox_pathways && npm run typecheck`
Expected: PASS, zero errors

**Step 3: Lint**

Run: `ruff check netbox_pathways/`
Expected: PASS (no Python changes but good to verify nothing broke)

**Step 4: Verify SVG output**

Visually inspect the generated SVG by reading `dist/pathways-map.min.js` and searching for `pw-marker-svg` to confirm the SVG markup is embedded correctly in the bundle.

**Step 5: Commit built output if dist/ is tracked, or skip if gitignored**

`dist/` is gitignored per the build pipeline design. No commit needed for built files.
