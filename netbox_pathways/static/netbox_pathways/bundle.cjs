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
  format: 'iife',
  logLevel: 'info',
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
