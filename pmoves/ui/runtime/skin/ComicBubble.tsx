"use client";

import Image from "next/image";
import React, { useMemo } from "react";
import { useSkin } from "./SkinProvider";
import { burstPath, cloudPath } from "./bubbleSynth";

export type ComicBubbleProps = {
  children?: React.ReactNode;
  archetype?: string;
  variant?: string;
  className?: string;
  seed?: number;
  tail?: boolean;
};

export function ComicBubble({
  children,
  archetype = "speech.round",
  variant = "primary",
  className = "",
  seed = 42,
  tail = true,
}: ComicBubbleProps) {
  const { skin } = useSkin();
  const bubble = skin?.components?.bubble;
  const archetypeDef = bubble?.archetypes?.[archetype];
  const variantDef = bubble?.variants?.[variant];

  const pathD = useMemo(() => {
    if (!archetypeDef || archetypeDef.renderer === "svg9") return "";
    if (archetypeDef.synth === "burst") {
      const params = {
        spikes: 16,
        innerR: 0.75,
        outerR: 1.15,
        irregularity: 0.15,
        ...(archetypeDef.params || {}),
      };
      return burstPath(seed, params.spikes, params.innerR, params.outerR, params.irregularity);
    }
    if (archetypeDef.synth === "cloud") {
      const params = {
        lobes: 8,
        noise: 0.2,
        ...(archetypeDef.params || {}),
      };
      return cloudPath(seed, params.lobes, params.noise);
    }
    return "";
  }, [archetypeDef, seed]);

  if (!archetypeDef || archetypeDef.renderer === "svg9") {
    const imgKey = archetypeDef?.svg || bubble?.svg;
    const slice = bubble?.nineSlice || { top: 16, right: 16, bottom: 16, left: 16 };
    const baseUrl = skin?.assets?.baseUrl || "";
    const imgUrl = imgKey && skin ? `${baseUrl}${skin.assets.images[imgKey]}` : undefined;
    const tailUrl = bubble?.tailSvg && skin ? `${baseUrl}${skin.assets.images[bubble.tailSvg]}` : undefined;

    const style: React.CSSProperties = {
      borderStyle: "solid",
      borderWidth: `${slice.top}px ${slice.right}px ${slice.bottom}px ${slice.left}px`,
      borderImageSource: imgUrl ? `url("${imgUrl}")` : undefined,
      borderImageSlice: `${slice.top} ${slice.right} ${slice.bottom} ${slice.left} fill`,
      borderImageRepeat: "stretch",
      padding: "var(--space-4,1rem)",
    };

    if (variantDef?.fill) (style as any)["--bubble-fill"] = variantDef.fill;
    if (variantDef?.stroke) (style as any)["--bubble-stroke"] = variantDef.stroke;
    if (variantDef?.strokeWidth) (style as any)["--bubble-strokeWidth"] = variantDef.strokeWidth;
    if (variantDef?.strokeDasharray) (style as any)["--bubble-strokeDasharray"] = variantDef.strokeDasharray;

    return (
      <div className={`relative ${className}`} style={style} data-variant={variant} data-archetype={archetype}>
        <div style={{ lineHeight: "var(--lh-tight,1.2)", fontSize: "var(--text-md,1rem)" }}>{children}</div>
        {tail && tailUrl && (
          <Image
            alt=""
            src={tailUrl}
            width={24}
            height={24}
            aria-hidden
            style={{ position: "absolute", left: 16, bottom: -12 }}
          />
        )}
      </div>
    );
  }

  const stroke = variantDef?.stroke || "var(--bubble-stroke,#121212)";
  const fill = variantDef?.fill || "var(--bubble-fill,#ffffff)";
  const strokeWidth = variantDef?.strokeWidth || 3;
  const dash = variantDef?.strokeDasharray;

  return (
    <svg viewBox="-128 -128 256 256" preserveAspectRatio="xMidYMid meet" className={className} data-archetype={archetype}>
      <path d={pathD} fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeDasharray={dash} />
      <foreignObject x="-110" y="-90" width="220" height="180">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            padding: "1rem",
            fontSize: "var(--text-md,1rem)",
            lineHeight: "var(--lh-tight,1.2)",
          }}
        >
          <div>{children}</div>
        </div>
      </foreignObject>
    </svg>
  );
}
