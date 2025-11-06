import React, { useMemo } from "react";
import { useSkin } from "./SkinProvider";
import { burstPath, cloudPath } from "./bubbleSynth";
type Props = { children?:React.ReactNode; archetype?:string; variant?:string; className?:string; seed?:number; tail?:boolean; };
export function ComicBubble({ children, archetype="speech.round", variant="primary", className="", seed=42, tail=true }: Props){
  const { skin } = useSkin();
  const b = skin?.components?.bubble; const a = b?.archetypes?.[archetype]; const v = b?.variants?.[variant];
  if (!a || a.renderer === "svg9"){
    const imgKey = a?.svg || b?.svg; const s = b?.nineSlice || { top:16, right:16, bottom:16, left:16 };
    const imgUrl = imgKey && skin ? (skin.assets.baseUrl + skin.assets.images[imgKey]) : undefined;
    const tailUrl = b?.tailSvg && skin ? (skin.assets.baseUrl + skin.assets.images[b.tailSvg]) : undefined;
    const style: React.CSSProperties = { borderStyle:"solid", borderWidth:`${s.top}px ${s.right}px ${s.bottom}px ${s.left}px`, borderImageSource: imgUrl ? `url("${imgUrl}")` : undefined, borderImageSlice:`${s.top} ${s.right} ${s.bottom} ${s.left} fill`, borderImageRepeat:"stretch", padding:"var(--space-4,1rem)" };
    if (v?.fill) (style as any)["--bubble-fill"] = v.fill;
    if (v?.stroke) (style as any)["--bubble-stroke"] = v.stroke;
    if (v?.strokeWidth) (style as any)["--bubble-strokeWidth"] = v.strokeWidth;
    if (v?.strokeDasharray) (style as any)["--bubble-strokeDasharray"] = v.strokeDasharray;
    return (<div className={`relative ${className}`} style={style} data-variant={variant} data-archetype={archetype}><div style={{ lineHeight:"var(--lh-tight,1.2)", fontSize:"var(--text-md,1rem)" }}>{children}</div>{tail && tailUrl && <img alt="" src={tailUrl} aria-hidden style={{ position:"absolute", width:24, height:24, left:16, bottom:-12 }} />}</div>);
  }
  const pathD = useMemo(()=>{
    if (!a) return ""; if (a.synth === "burst"){ const p = { spikes: 16, innerR: 0.75, outerR: 1.15, irregularity: 0.15, ...(a.params||{}) }; return burstPath(seed, p.spikes, p.innerR, p.outerR, p.irregularity); }
    if (a.synth === "cloud"){ const p = { lobes: 8, noise: 0.2, ...(a.params||{}) }; return cloudPath(seed, p.lobes, p.noise); } return "";
  },[a,seed]);
  const stroke = v?.stroke || "var(--bubble-stroke,#121212)"; const fill = v?.fill || "var(--bubble-fill,#ffffff)"; const strokeWidth = v?.strokeWidth || 3; const dash = v?.strokeDasharray;
  return (<svg viewBox="-128 -128 256 256" preserveAspectRatio="xMidYMid meet" className={className} data-archetype={archetype}><path d={pathD} fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeDasharray={dash} /><foreignObject x="-110" y="-90" width="220" height="180"><div xmlns="http://www.w3.org/1999/xhtml" style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100%", padding:"1rem", fontSize:"var(--text-md,1rem)", lineHeight:"var(--lh-tight,1.2)"}}><div>{children}</div></div></foreignObject></svg>);
}