# TypeScript + esbuild Build Pipeline — Design

**Date**: 2026-03-10
**Status**: Approved

## Goals

- Type safety across all JS (catch bugs at compile time)
- Minified production output (smaller payloads)
- Modern JS features (modules, async/await) with ES2016 target
- Alignment with NetBox core's TypeScript + esbuild pattern

## Approach

**esbuild** — same bundler NetBox core uses. Fast (<100ms builds), handles
TypeScript transpilation + minification + sourcemaps in one pass, minimal config.

## Source / Output Layout

```
netbox_pathways/
  static/
    netbox_pathways/
      package.json              # Scoped to static dir
      tsconfig.json
      bundle.cjs                # esbuild script (~30 lines)
      src/                      # TypeScript source
        pathways-map.ts         # Main map init, data loading
        sidebar.ts              # Sidebar panel (extracted from IIFE)
        popover.ts              # Hover popover (extracted)
        detail-map.ts           # Detail page maps
        point-polygon-widget.ts # Draw widget
        types/
          leaflet.d.ts          # Leaflet + MarkerCluster augmentations
          netbox.d.ts           # NetBox globals (csrftoken, etc.)
          features.ts           # FeatureEntry, GeoJSONProperties, MapConfig
      dist/                     # esbuild output (gitignored)
        pathways-map.min.js
        pathways-map.min.js.map
        detail-map.min.js
        detail-map.min.js.map
        point-polygon-widget.min.js
      vendor/                   # Unchanged — vendored libs
      css/                      # Unchanged — hand-authored CSS
```

- Templates reference `dist/foo.min.js` instead of `js/foo.js`
- `dist/` is gitignored; built on install and in CI
- Old `js/` directory deleted after migration is validated

## Build Tooling

**package.json** (minimal, private):
- `devDependencies`: esbuild ^0.25, typescript ^5.8, @types/leaflet ^1.9
- Scripts: `build`, `watch`, `typecheck`

**bundle.cjs**:
- Finds all `src/*.ts` entrypoints (not `src/types/`)
- Outputs to `dist/` with `.min.js` suffix
- Minification + linked sourcemaps
- `--watch` flag for dev mode
- Target: `es2016`
- Leaflet treated as external global

**tsconfig.json**:
- `strict: true`
- `target: "ES2016"`, `module: "ESNext"`
- `noEmit: true` (tsc for type-checking only; esbuild for output)

## Migration Strategy

Incremental, each phase independently deployable:

1. **Scaffolding** — package.json, tsconfig, bundle.cjs, type declarations, Makefile, .gitignore updates
2. **point-polygon-widget.ts** (35 lines) — trivial conversion, smoke test for pipeline
3. **detail-map.ts** (399 lines) — extract config interfaces, type Leaflet interactions
4. **pathways-map.ts** (1535 lines) — break monolith into modules:
   - Sidebar IIFE → `sidebar.ts` class/module
   - Popover → `popover.ts` class/module
   - Typed interfaces: `FeatureEntry`, `DetailFields`, `GeoJSONProperties`, `MapConfig`
   - Enums for structure/pathway types and colors
   - async/await replacing XHR callbacks

## Makefile

```makefile
STATIC_DIR := netbox_pathways/static/netbox_pathways

build:        cd $(STATIC_DIR) && npm install && npm run build
watch:        cd $(STATIC_DIR) && npm run watch
typecheck:    cd $(STATIC_DIR) && npm run typecheck
install:      build → pip install -e .
dev:          build → pip install -e '.[dev]'
lint:         ruff check . + typecheck
clean:        rm -rf dist/ node_modules/
```

## Developer Workflow

- `make watch` — esbuild rebuilds on save (~10ms), Django serves new files on refresh
- `make typecheck` — type errors without building
- `make lint` — Python (ruff) + TypeScript in one command
- `make dev` — full onboarding (npm install + build + pip install)

## CI / Production

- `dist/` gitignored; CI builds from source
- Dockerfile runs `npm install && npm run build` before `pip install`
- Wheel includes `dist/*.min.js`, excludes `src/*.ts`

## Python Packaging

`pyproject.toml` updates:
- `package-data` includes `dist/**`, `vendor/**`, `css/**`
- Excludes `src/**`, `node_modules/**` from wheel
