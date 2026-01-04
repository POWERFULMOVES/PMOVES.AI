"use client";

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Skin = any;

const SkinCtx = createContext<{ skin?: Skin } | null>(null);

export const useSkin = () => {
  const ctx = useContext(SkinCtx);
  if (!ctx) {
    throw new Error("SkinProvider is missing from the component tree");
  }
  return ctx;
};

export function SkinProvider({ url, children }: { url: string; children: React.ReactNode }) {
  const [skin, setSkin] = useState<Skin>();

  useEffect(() => {
    let alive = true;
    (async () => {
      const response = await fetch(url);
      const json = await response.json();
      if (!alive) return;
      setSkin(json);

      const root = document.documentElement;
      const applyTokens = (node: any) => {
        Object.entries(node).forEach(([key, value]) => {
          if (value && typeof value === "object" && !key.startsWith("--")) {
            applyTokens(value);
          } else if (key.startsWith("--")) {
            root.style.setProperty(key, String(value));
          }
        });
      };
      if (json?.tokens) {
        applyTokens(json.tokens);
      }
    })();
    return () => {
      alive = false;
    };
  }, [url]);

  const value = useMemo(() => ({ skin }), [skin]);

  return <SkinCtx.Provider value={value}>{children}</SkinCtx.Provider>;
}
