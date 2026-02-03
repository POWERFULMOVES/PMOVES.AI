import { mulberry32 } from "./rng";
export function burstPath(seed:number, spikes:number, innerR:number, outerR:number, irregularity=0.12){
  const rnd = mulberry32(seed); const pts:[number,number][]=[]; const N=Math.max(4,Math.floor(spikes)*2);
  for (let i=0;i<N;i++){ const a=(i/N)*Math.PI*2; const rBase=(i%2===0)?outerR:innerR; const r=rBase*(1+(rnd()-0.5)*2*irregularity); pts.push([Math.cos(a)*r, Math.sin(a)*r]); }
  let d=`M ${pts[0][0]} ${pts[0][1]}`; for (let i=1;i<pts.length;i++) d+=` L ${pts[i][0]} ${pts[i][1]}`; return d+" Z";
}
export function cloudPath(seed:number, lobes:number, noise=0.2){
  const rnd = mulberry32(seed); const steps=Math.max(8,lobes*4); const R=1; let d="";
  for (let i=0;i<=steps;i++){ const t=(i/steps)*Math.PI*2; const r=R*(1+(rnd()-0.5)*2*noise); const x=Math.cos(t)*r, y=Math.sin(t)*r; d+=(i===0? "M ":" L ")+`${x} ${y} `; } return d+" Z";
}