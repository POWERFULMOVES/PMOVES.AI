import { mulberry32 } from "./rng";

export function burstPath(
  seed: number,
  spikes: number,
  innerR: number,
  outerR: number,
  irregularity = 0.12
) {
  const rnd = mulberry32(seed);
  const points: Array<[number, number]> = [];
  const total = Math.max(4, Math.floor(spikes) * 2);
  for (let i = 0; i < total; i += 1) {
    const angle = (i / total) * Math.PI * 2;
    const base = i % 2 === 0 ? outerR : innerR;
    const radius = base * (1 + (rnd() - 0.5) * 2 * irregularity);
    points.push([Math.cos(angle) * radius, Math.sin(angle) * radius]);
  }
  let path = `M ${points[0][0]} ${points[0][1]}`;
  for (let i = 1; i < points.length; i += 1) {
    path += ` L ${points[i][0]} ${points[i][1]}`;
  }
  return `${path} Z`;
}

export function cloudPath(seed: number, lobes: number, noise = 0.2) {
  const rnd = mulberry32(seed);
  const steps = Math.max(8, lobes * 4);
  const radius = 1;
  let path = "";
  for (let i = 0; i <= steps; i += 1) {
    const t = (i / steps) * Math.PI * 2;
    const r = radius * (1 + (rnd() - 0.5) * 2 * noise);
    const x = Math.cos(t) * r;
    const y = Math.sin(t) * r;
    path += `${i === 0 ? "M" : " L"} ${x} ${y}`;
  }
  return `${path} Z`;
}
