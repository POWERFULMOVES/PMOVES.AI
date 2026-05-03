import fs from 'node:fs';
import path from 'node:path';
import { bundle } from '@remotion/bundler';
import { renderMedia, renderStill, selectComposition } from '@remotion/renderer';
import { normalizeProvenanceLivingDoc } from '../src/provenanceLivingDoc.ts';

const cwd = process.cwd();
const entryPoint = path.resolve(cwd, 'src', 'remotion', 'index.tsx');
const argv = process.argv.slice(2);

function resolveCliPath(value) {
  return path.isAbsolute(value) ? value : path.resolve(cwd, value);
}

let defaultInputPath = path.resolve(cwd, 'demos', 'provenance_living_doc.request.json');
let defaultOutputPath = path.resolve(cwd, 'demos', 'provenance_living_doc.preview.png');
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

if (extension === '.png' || extension === '.jpg' || extension === '.jpeg') {
  await renderStill({
    serveUrl,
    composition,
    inputProps: { doc },
    output: outputPath,
    imageFormat: extension === '.jpg' || extension === '.jpeg' ? 'jpeg' : 'png',
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
}, null, 2));
