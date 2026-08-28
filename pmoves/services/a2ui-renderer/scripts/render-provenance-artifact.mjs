import fs from 'node:fs';
import path from 'node:path';
import { bundle } from '@remotion/bundler';
import { renderMedia, renderStill, selectComposition } from '@remotion/renderer';
// Default-import (not named): this .mjs entry is native ESM, but the package is
// CommonJS (tsconfig module: commonjs, no "type" in package.json), so tsx transpiles
// the imported .ts to CJS. A named ESM import from a CJS module fails static binding
// ("does not provide an export named ..."); the module object via default import works.
import provenanceLivingDoc from '../src/provenanceLivingDoc.ts';

const { normalizeProvenanceLivingDoc } = provenanceLivingDoc;

const cwd = process.cwd();
const entryPoint = path.resolve(cwd, 'src', 'remotion', 'index.tsx');
const argv = process.argv.slice(2);

function resolveCliPath(value) {
  return path.isAbsolute(value) ? value : path.resolve(cwd, value);
}

let defaultInputPath = path.resolve(cwd, 'demos', 'provenance_living_doc.request.json');
let defaultOutputPath = path.resolve(cwd, 'demos', 'provenance_living_doc.preview.png');
let frameArg = null; // --frame N: absolute still frame (wins over fraction)
let frameFractionArg = null; // --frame-fraction F: still frame as fraction of timeline (0..1)
const positionalArgs = [];

for (let index = 0; index < argv.length; index += 1) {
  const arg = argv[index];
  if (arg === '--default-input') {
    const next = argv[index + 1];
    if (!next) {
      throw new Error('Missing value for --default-input');
    }
    defaultInputPath = resolveCliPath(next);
    index += 1;
    continue;
  }
  if (arg === '--default-output') {
    const next = argv[index + 1];
    if (!next) {
      throw new Error('Missing value for --default-output');
    }
    defaultOutputPath = resolveCliPath(next);
    index += 1;
    continue;
  }
  if (arg === '--frame') {
    const next = argv[index + 1];
    if (next === undefined) {
      throw new Error('Missing value for --frame');
    }
    frameArg = Number.parseInt(next, 10);
    if (!Number.isInteger(frameArg) || frameArg < 0) {
      throw new Error(`--frame must be a non-negative integer, got: ${next}`);
    }
    index += 1;
    continue;
  }
  if (arg === '--frame-fraction') {
    const next = argv[index + 1];
    if (next === undefined) {
      throw new Error('Missing value for --frame-fraction');
    }
    frameFractionArg = Number.parseFloat(next);
    if (!Number.isFinite(frameFractionArg) || frameFractionArg < 0 || frameFractionArg > 1) {
      throw new Error(`--frame-fraction must be a number in [0, 1], got: ${next}`);
    }
    index += 1;
    continue;
  }
  positionalArgs.push(arg);
}

const inputPath = positionalArgs[0]
  ? resolveCliPath(positionalArgs[0])
  : defaultInputPath;
const outputPath = positionalArgs[1]
  ? resolveCliPath(positionalArgs[1])
  : defaultOutputPath;

const raw = fs.readFileSync(inputPath, 'utf8');
const doc = normalizeProvenanceLivingDoc(JSON.parse(raw));
const extension = path.extname(outputPath).toLowerCase();

const serveUrl = await bundle({ entryPoint });
const composition = await selectComposition({
  serveUrl,
  id: 'ProvenanceLivingDoc',
  inputProps: { doc },
});
const durationInFrames = Math.ceil((doc.duration_ms / 1000) * composition.fps);

// Every element in this composition reveals from opacity 0 over the first ~70 frames,
// so a still at frame 0 captures a blank intro. Default to a mid-timeline frame so the
// thumbnail shows fully-revealed content for any animated composition without
// hard-coding this comp's reveal schedule. Override with --frame or --frame-fraction.
const DEFAULT_STILL_FRACTION = 0.5;

let renderedFrame = null;

if (extension === '.png' || extension === '.jpg' || extension === '.jpeg') {
  // Bound the still by the DOCUMENT's duration (normalization allows up to 24s),
  // matching the media path below — otherwise a still can't thumbnail past the
  // registered 12s/360-frame composition even though the rendered video runs longer.
  // renderStill validates frame < composition.durationInFrames, so override it too.
  const maxFrame = Math.max(0, durationInFrames - 1);
  if (frameArg !== null) {
    renderedFrame = Math.min(frameArg, maxFrame);
  } else {
    const fraction = frameFractionArg !== null ? frameFractionArg : DEFAULT_STILL_FRACTION;
    renderedFrame = Math.min(Math.round(fraction * maxFrame), maxFrame);
  }
  await renderStill({
    serveUrl,
    composition: { ...composition, durationInFrames },
    inputProps: { doc },
    output: outputPath,
    imageFormat: extension === '.jpg' || extension === '.jpeg' ? 'jpeg' : 'png',
    frame: renderedFrame,
    overwrite: true,
  });
} else if (extension === '.mp4' || extension === '.webm' || extension === '.gif') {
  const codec = extension === '.webm' ? 'vp8' : extension === '.gif' ? 'gif' : 'h264';
  await renderMedia({
    serveUrl,
    composition: { ...composition, durationInFrames },
    inputProps: { doc },
    codec,
    outputLocation: outputPath,
  });
} else {
  throw new Error(`Unsupported output extension: ${extension}`);
}

console.log(JSON.stringify({
  ok: true,
  input: inputPath,
  output: outputPath,
  frame: renderedFrame,
  durationInFrames,
  fps: composition.fps,
  width: composition.width,
  height: composition.height,
}, null, 2));
