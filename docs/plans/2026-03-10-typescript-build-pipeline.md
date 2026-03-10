# TypeScript + esbuild Build Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the plugin's JavaScript to TypeScript with esbuild bundling, producing minified output with sourcemaps.

**Architecture:** TypeScript source lives in `static/netbox_pathways/src/`, esbuild compiles to `static/netbox_pathways/dist/`. Leaflet is treated as an external global (loaded from CDN). Each `.ts` entrypoint produces one `.min.js` bundle. The big `pathways-map.js` is split into modules (`sidebar.ts`, `popover.ts`, main).

**Tech Stack:** TypeScript 5.8, esbuild 0.25, @types/leaflet, Node 18+

---

### Task 1: Scaffold build tooling

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/package.json`
- Create: `netbox_pathways/static/netbox_pathways/tsconfig.json`
- Create: `netbox_pathways/static/netbox_pathways/bundle.cjs`
- Modify: `.gitignore`

**Step 1: Create package.json**

Create `netbox_pathways/static/netbox_pathways/package.json`:

```json
{
  "private": true,
  "scripts": {
    "build": "node bundle.cjs",
    "watch": "node bundle.cjs --watch",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "esbuild": "^0.25.0",
    "typescript": "~5.8.0",
    "@types/leaflet": "^1.9.0",
    "@types/leaflet.markercluster": "^1.5.0"
  }
}
```

**Step 2: Create tsconfig.json**

Create `netbox_pathways/static/netbox_pathways/tsconfig.json`:

```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ES2016",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "noEmit": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "declaration": false,
    "sourceMap": true
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

**Step 3: Create bundle.cjs**

Create `netbox_pathways/static/netbox_pathways/bundle.cjs`:

```javascript
const esbuild = require('esbuild');
const path = require('path');
const fs = require('fs');

const srcDir = path.join(__dirname, 'src');
const outDir = path.join(__dirname, 'dist');

// Find top-level .ts entrypoints (not in types/)
const entryPoints = fs.readdirSync(srcDir)
  .filter(f => f.endsWith('.ts') && !f.endsWith('.d.ts'))
  .map(f => path.join(srcDir, f));

const isWatch = process.argv.includes('--watch');

const buildOptions = {
  entryPoints,
  bundle: true,
  minify: !isWatch,
  sourcemap: 'linked',
  target: 'es2016',
  outdir: outDir,
  outExtension: { '.js': '.min.js' },
  external: ['leaflet'],
  globalName: undefined,
  format: 'iife',
  logLevel: 'info',
  // Leaflet is a global — tell esbuild to leave `import L from 'leaflet'` alone
  // and instead reference the global `L` variable.
  define: {},
};

async function main() {
  if (isWatch) {
    const ctx = await esbuild.context(buildOptions);
    await ctx.watch();
    console.log('Watching for changes...');
  } else {
    await esbuild.build(buildOptions);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
```

**Step 4: Add gitignore entries**

Append to `.gitignore`:

```
# TypeScript build artifacts
netbox_pathways/static/netbox_pathways/dist/
netbox_pathways/static/netbox_pathways/node_modules/
```

**Step 5: Install dependencies and verify build runs**

```bash
cd netbox_pathways/static/netbox_pathways
npm install
```

Expected: `node_modules/` created, no errors.

**Step 6: Commit**

```bash
git add package.json tsconfig.json bundle.cjs .gitignore
git commit -m "chore(build): scaffold esbuild + TypeScript tooling"
```

---

### Task 2: Create type declarations

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/src/types/netbox.d.ts`
- Create: `netbox_pathways/static/netbox_pathways/src/types/leaflet-extensions.d.ts`
- Create: `netbox_pathways/static/netbox_pathways/src/types/features.ts`

**Step 1: Create NetBox global type declarations**

Create `src/types/netbox.d.ts`:

```typescript
/** Globals provided by NetBox and our plugin templates. */

interface PathwaysConfig {
  apiBase: string;
  maxNativeZoom: number;
  overlays?: OverlayConfig[];
  baseLayers?: BaseLayerConfig[];
}

interface OverlayConfig {
  name: string;
  type: 'wms' | 'wmts' | 'tile';
  url: string;
  [key: string]: unknown;
}

interface BaseLayerConfig {
  name: string;
  url: string;
  tileSize?: number;
  zoomOffset?: number;
  attribution?: string;
  maxNativeZoom?: number;
  [key: string]: unknown;
}

declare global {
  interface Window {
    PATHWAYS_CONFIG?: PathwaysConfig;
    initializePathwaysMap?: (mapId: string, config: Record<string, unknown>) => void;
  }
}

export {};
```

**Step 2: Create Leaflet extension declarations**

Create `src/types/leaflet-extensions.d.ts`:

```typescript
/** Type augmentations for Leaflet plugins and django-leaflet. */

import 'leaflet';
import 'leaflet.markercluster';

declare module 'leaflet' {
  interface MarkerOptions {
    /** Set by our highlight system to preserve original icon. */
    _origIcon?: L.Icon | L.DivIcon;
  }

  interface PathOptions {
    /** Set by our highlight system to preserve original style. */
    _origStyle?: L.PathOptions;
  }
}

/** django-leaflet fires this custom event on each map widget init. */
interface MapInitEvent extends CustomEvent {
  detail: {
    map: L.Map;
  };
}
```

**Step 3: Create feature type interfaces**

Create `src/types/features.ts`:

```typescript
/** Shared types for map features and sidebar entries. */

export interface GeoJSONProperties {
  id: number;
  name: string;
  url: string;
  structure_type?: string;
  pathway_type?: string;
  site_name?: string;
  cluster?: boolean;
  point_count?: number;
  [key: string]: unknown;
}

export type FeatureType = 'structure' | 'conduit' | 'aerial' | 'direct_buried';

export interface FeatureEntry {
  props: GeoJSONProperties;
  featureType: FeatureType;
  layer: L.Layer;
  latlng: L.LatLng;
}

/** Field definition for the detail panel: [label, data_key, unit_suffix?] */
export type DetailFieldDef = [string, string] | [string, string, string];

/** Resolved display value from the REST API. */
export interface ResolvedValue {
  text: string;
  url?: string | null;
}

export interface PathwayStyle {
  color: string;
  weight: number;
  opacity: number;
  dashArray: string;
}

export interface PathwayLayerConfig {
  endpoint: string;
  layer: L.LayerGroup;
  featureType: FeatureType;
  style: PathwayStyle;
}
```

**Step 4: Run typecheck to verify declarations compile**

```bash
cd netbox_pathways/static/netbox_pathways
npx tsc --noEmit
```

Expected: passes (no source files yet, just declarations).

**Step 5: Commit**

```bash
git add src/types/
git commit -m "chore(build): add TypeScript type declarations"
```

---

### Task 3: Migrate point-polygon-widget.ts

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/src/point-polygon-widget.ts`
- Modify: `netbox_pathways/forms.py:14`

**Step 1: Create the TypeScript source**

Create `src/point-polygon-widget.ts`:

```typescript
/**
 * Disable the polyline draw tool on PointPolygonWidget maps.
 *
 * django-leaflet fires a 'map:init' event per widget. We intercept it
 * and remove the polyline button from any draw control on that map.
 */

declare const L: typeof import('leaflet');

document.addEventListener('map:init', ((e: CustomEvent) => {
  const map: L.Map | undefined = e.detail?.map;
  if (!map) return;

  // The draw control is stored on the map by django-leaflet
  for (const key in map) {
    if (
      key.indexOf('drawControl') === 0 &&
      (map as Record<string, any>)[key]?._toolbars
    ) {
      const drawToolbar = (map as Record<string, any>)[key]._toolbars.draw;
      if (drawToolbar?._modes?.polyline) {
        const btn: HTMLElement | undefined = drawToolbar._modes.polyline.button;
        if (btn?.parentNode) {
          btn.parentNode.removeChild(btn);
        }
      }
    }
  }
}) as EventListener);
```

**Step 2: Build and verify output exists**

```bash
cd netbox_pathways/static/netbox_pathways
npm run build
ls -la dist/point-polygon-widget.min.js
```

Expected: file exists with minified output + sourcemap.

**Step 3: Run typecheck**

```bash
npm run typecheck
```

Expected: PASS — no type errors.

**Step 4: Update the Django form to reference the new path**

In `netbox_pathways/forms.py`, change line 14:

```python
# Before:
js = ('netbox_pathways/js/point-polygon-widget.js',)

# After:
js = ('netbox_pathways/dist/point-polygon-widget.min.js',)
```

**Step 5: Verify Django system check passes**

```bash
cd /opt/netbox-pathways
python /opt/netbox/netbox/manage.py check
```

Expected: System check identified no issues.

**Step 6: Commit**

```bash
git add src/point-polygon-widget.ts netbox_pathways/forms.py
git commit -m "feat(build): migrate point-polygon-widget to TypeScript"
```

---

### Task 4: Migrate detail-map.ts

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/src/detail-map.ts`
- Modify: `netbox_pathways/template_content.py:105`
- Modify: `netbox_pathways/templates/netbox_pathways/route_finder.html:123`
- Modify: `netbox_pathways/templates/netbox_pathways/cable_trace.html:117`
- Modify: `netbox_pathways/templates/netbox_pathways/neighbors.html:130`

**Step 1: Convert detail-map.js to TypeScript**

Create `src/detail-map.ts`. This is a direct port of the 399-line `js/detail-map.js` with type annotations added:

- Add `declare const L: typeof import('leaflet');` at top
- Type `CFG` as `PathwaysConfig`
- Type function parameters and return values
- Type the inline data interfaces (`PointData`, `LineData`)
- Replace `var` with `const`/`let`
- Convert XHR callbacks to typed functions

The file keeps the same IIFE structure — esbuild wraps it in IIFE by default with `format: 'iife'`.

**Step 2: Build and verify**

```bash
cd netbox_pathways/static/netbox_pathways
npm run build
npm run typecheck
```

Expected: both pass, `dist/detail-map.min.js` exists.

**Step 3: Update all template references**

Four locations reference `js/detail-map.js`:

1. `netbox_pathways/template_content.py:105`:
   ```python
   # Before:
   detail_js = static('netbox_pathways/js/detail-map.js')
   # After:
   detail_js = static('netbox_pathways/dist/detail-map.min.js')
   ```

2. `templates/netbox_pathways/route_finder.html:123`:
   ```html
   <!-- Before -->
   <script src="{% static 'netbox_pathways/js/detail-map.js' %}"></script>
   <!-- After -->
   <script src="{% static 'netbox_pathways/dist/detail-map.min.js' %}"></script>
   ```

3. `templates/netbox_pathways/cable_trace.html:117`: same change as above.

4. `templates/netbox_pathways/neighbors.html:130`: same change as above.

**Step 4: Verify Django check**

```bash
python /opt/netbox/netbox/manage.py check
```

Expected: no issues.

**Step 5: Commit**

```bash
git add src/detail-map.ts netbox_pathways/template_content.py \
  netbox_pathways/templates/netbox_pathways/route_finder.html \
  netbox_pathways/templates/netbox_pathways/cable_trace.html \
  netbox_pathways/templates/netbox_pathways/neighbors.html
git commit -m "feat(build): migrate detail-map to TypeScript"
```

---

### Task 5: Extract shared types and modules from pathways-map

This is prep work before the big migration. Extract the Sidebar IIFE and Popover object into importable modules.

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/src/sidebar.ts`
- Create: `netbox_pathways/static/netbox_pathways/src/popover.ts`

**Step 1: Create sidebar.ts**

Extract the Sidebar IIFE (lines ~100-920 of `pathways-map.js`) into a proper module:

- Export a `Sidebar` class or namespace with typed methods:
  `init(map)`, `show()`, `hide()`, `setFeatures()`, `showList()`,
  `showDetail()`, `selectFeature()`, `onFeatureCreated()`
- Import types from `./types/features`
- Type all internal state (`_selected: FeatureEntry | null`, etc.)
- Convert `_fetchDetail` XHR to `fetch()` with async/await
- Replace `_resolveValue` with typed overloads
- Type `DETAIL_FIELDS` as `Record<string, DetailFieldDef[]>`
- Type all DOM manipulation

**Step 2: Create popover.ts**

Extract the Popover object (lines ~923-953) into a module:

- Export a `Popover` class with `init(map)`, `show(latlng, props)`, `hide()`
- Type all parameters

**Step 3: Typecheck**

```bash
npm run typecheck
```

Expected: PASS.

**Step 4: Commit**

```bash
git add src/sidebar.ts src/popover.ts
git commit -m "feat(build): extract sidebar and popover as TypeScript modules"
```

---

### Task 6: Migrate pathways-map.ts (main entrypoint)

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/src/pathways-map.ts`
- Modify: `netbox_pathways/templates/netbox_pathways/map.html:321`

**Step 1: Create pathways-map.ts**

The main file imports from `./sidebar`, `./popover`, and `./types/features`. It contains:

- `initializePathwaysMap()` function (exported on `window`)
- Color/icon maps as typed `Record<string, string>` constants
- `_fetchGeoJSON` converted to async/await with `fetch()`
- `_loadData` using typed `PathwayLayerConfig[]` for the pathway configs
- `_haversine`, `_bboxParam`, `_debounce` as typed utility functions
- `_structureIcon`, `_clusterIcon` returning `L.DivIcon`
- `_addLineLabels` with typed parameters
- All the layer initialization, base layer setup, etc.

Key conversions:
- `var` → `const`/`let`
- IIFE wrapper removed (esbuild wraps in IIFE via `format: 'iife'`)
- XHR → `fetch()` + async/await
- Inline `Record<string, ...>` typing for color maps, icon maps
- Enum-like const objects for structure types, pathway types

**Step 2: Build and typecheck**

```bash
npm run build
npm run typecheck
```

Expected: both pass, `dist/pathways-map.min.js` exists.

**Step 3: Update map template**

In `netbox_pathways/templates/netbox_pathways/map.html:321`:

```html
<!-- Before -->
<script src="{% static 'netbox_pathways/js/pathways-map.js' %}"></script>
<!-- After -->
<script src="{% static 'netbox_pathways/dist/pathways-map.min.js' %}"></script>
```

**Step 4: Verify Django check**

```bash
python /opt/netbox/netbox/manage.py check
```

Expected: no issues.

**Step 5: Commit**

```bash
git add src/pathways-map.ts netbox_pathways/templates/netbox_pathways/map.html
git commit -m "feat(build): migrate pathways-map to TypeScript"
```

---

### Task 7: Update Makefile and pyproject.toml

**Files:**
- Modify: `Makefile`
- Modify: `pyproject.toml:8-9`

**Step 1: Add JS build targets to Makefile**

Add these targets to the existing `Makefile`:

```makefile
STATIC_DIR := netbox_pathways/static/netbox_pathways

# --- JavaScript / TypeScript ---

js-install: ## Install JS build dependencies
	cd $(STATIC_DIR) && npm install

js-build: js-install ## Build TypeScript → minified JS
	cd $(STATIC_DIR) && npm run build

js-watch: js-install ## Watch mode — rebuild on save
	cd $(STATIC_DIR) && npm run watch

js-typecheck: ## Type-check TypeScript without emitting
	cd $(STATIC_DIR) && npm run typecheck

js-clean: ## Remove JS build artifacts and node_modules
	rm -rf $(STATIC_DIR)/dist $(STATIC_DIR)/node_modules
```

Update existing targets:

```makefile
# Update lint to include typecheck
lint: ## Run ruff linter + TypeScript type-check
	ruff check netbox_pathways/
	cd $(STATIC_DIR) && npm run typecheck

# Update install to build JS first
install: js-build ## Install plugin in editable mode (builds JS first)
	pip install -e .

install-dev: js-build ## Install plugin with dev dependencies
	pip install -e ".[dev]"

# Add clean target
clean: js-clean ## Remove all build artifacts
```

**Step 2: Update pyproject.toml package-data**

In `pyproject.toml`, change lines 8-9 to exclude source and node_modules from the wheel:

```toml
[tool.setuptools.package-data]
netbox_pathways = [
    "templates/**/*",
    "static/**/dist/*",
    "static/**/vendor/*",
    "static/**/css/*",
    "static/**/qgis/*",
]
```

**Step 3: Verify install works end-to-end**

```bash
make clean
make install
python /opt/netbox/netbox/manage.py check
```

Expected: JS builds, plugin installs, Django check passes.

**Step 4: Commit**

```bash
git add Makefile pyproject.toml
git commit -m "chore(build): add JS build targets to Makefile, update packaging"
```

---

### Task 8: Remove old JS files and final cleanup

**Files:**
- Delete: `netbox_pathways/static/netbox_pathways/js/pathways-map.js`
- Delete: `netbox_pathways/static/netbox_pathways/js/detail-map.js`
- Delete: `netbox_pathways/static/netbox_pathways/js/point-polygon-widget.js`

**Step 1: Verify no remaining references to old paths**

```bash
grep -r "netbox_pathways/js/" netbox_pathways/ --include="*.py" --include="*.html"
```

Expected: no matches (all updated in prior tasks).

**Step 2: Delete old JS files**

```bash
rm netbox_pathways/static/netbox_pathways/js/pathways-map.js
rm netbox_pathways/static/netbox_pathways/js/detail-map.js
rm netbox_pathways/static/netbox_pathways/js/point-polygon-widget.js
rmdir netbox_pathways/static/netbox_pathways/js/
```

**Step 3: Full build + check**

```bash
make js-build
python /opt/netbox/netbox/manage.py check
```

Expected: both pass.

**Step 4: Commit**

```bash
git add -A
git commit -m "chore(build): remove old JS files, migration complete"
```
