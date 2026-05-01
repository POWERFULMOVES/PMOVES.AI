import fs from 'node:fs';
import path from 'node:path';
import { bundle } from '@remotion/bundler';
import { renderMedia, renderStill, selectComposition } from '@remotion/renderer';
import { normalizeProvenanceLivingDoc } from '../dist/provenanceLivingDoc.js';

const cwd = process.cwd();
const entryPoint = path.resolve(cwd, 'src', 'remotion', 'index.tsx');
const inputPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.resolve(cwd, 'demos', 'provenance_living_doc.request.json');
const outputPath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.resolve(cwd, 'demos', 'provenance_living_doc.preview.png');

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
