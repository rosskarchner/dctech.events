#!/usr/bin/env node
const esbuild = require('esbuild');
const fs = require('fs');
const path = require('path');

// Check if we're in watch mode
const isWatch = process.argv.includes('--watch');

// Ensure output directory exists
const outDir = path.join(__dirname, 'static', 'js', 'dist');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

// Build options for event submission
const submitBuildOptions = {
  entryPoints: ['static/js/submit.js'],
  bundle: true,
  minify: true,
  sourcemap: true,
  format: 'esm',
  target: ['es2020'],
  outfile: 'static/js/dist/submit.bundle.js',
  logLevel: 'info'
};

// Build options for group submission
const submitGroupBuildOptions = {
  entryPoints: ['static/js/submit-group.js'],
  bundle: true,
  minify: true,
  sourcemap: true,
  format: 'esm',
  target: ['es2020'],
  outfile: 'static/js/dist/submit-group.bundle.js',
  logLevel: 'info'
};

// Build options for event editing
const editBuildOptions = {
  entryPoints: ['static/js/edit.js'],
  bundle: true,
  minify: true,
  sourcemap: true,
  format: 'esm',
  target: ['es2020'],
  outfile: 'static/js/dist/edit.bundle.js',
  logLevel: 'info'
};

// Build options for groups editing
const editGroupsBuildOptions = {
  entryPoints: ['static/js/edit-groups.js'],
  bundle: true,
  minify: true,
  sourcemap: true,
  format: 'esm',
  target: ['es2020'],
  outfile: 'static/js/dist/edit-groups.bundle.js',
  logLevel: 'info'
};

async function build() {
  try {
    if (isWatch) {
      const submitContext = await esbuild.context(submitBuildOptions);
      const submitGroupContext = await esbuild.context(submitGroupBuildOptions);
      const editContext = await esbuild.context(editBuildOptions);
      const editGroupsContext = await esbuild.context(editGroupsBuildOptions);
      await Promise.all([
        submitContext.watch(),
        submitGroupContext.watch(),
        editContext.watch(),
        editGroupsContext.watch()
      ]);
      console.log('Watching for changes...');
    } else {
      await Promise.all([
        esbuild.build(submitBuildOptions),
        esbuild.build(submitGroupBuildOptions),
        esbuild.build(editBuildOptions),
        esbuild.build(editGroupsBuildOptions)
      ]);
      console.log('Build completed successfully!');
    }
  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1);
  }
}

build();
