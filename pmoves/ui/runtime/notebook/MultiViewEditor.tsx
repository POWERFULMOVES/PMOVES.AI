"use client";

import React, { useState } from "react";
import type { MessageView } from "./useSupabaseViews";
import { SelectionCanvas } from "./SelectionCanvas";
import { CanvasToolbar } from "./CanvasToolbar";
import { BaselineOverlay } from "./BaselineOverlay";

type Layer = { id: string; view: MessageView; content?: React.ReactNode };

type Props = {
  layers: Layer[];
  onChangeLayer: (id: string, next: Partial<MessageView>) => void;
  onCommitNewView: (id: string) => Promise<void> | void;
  onReorderLayers: (ids: string[]) => void;
  selection?: string[];
  onSelectionChange?: (ids: string[]) => void;
};

export function MultiViewEditor({
  layers,
  onChangeLayer,
  onCommitNewView,
  onReorderLayers,
  selection: externalSelection,
  onSelectionChange,
}: Props) {
  const [selectionState, setSelectionState] = useState<string[]>(externalSelection ?? []);
  const [smartSnap, setSmartSnap] = useState(true);
  const [baseline, setBaseline] = useState(false);

  const selection = externalSelection ?? selectionState;
  const setSelection = onSelectionChange ?? setSelectionState;

  function align(mode: "left" | "right" | "center" | "top" | "bottom" | "middle") {
    if (selection.length < 2) return;
    const rect = (id: string) => {
      const layer = layers.find((l) => l.id === id);
      if (!layer) throw new Error(`Layer ${id} not found`);
      const layout = layer.view.layout || {};
      return {
        id,
        x: layout.x ?? 0,
        y: layout.y ?? 0,
        w: layout.w ?? 320,
        h: layout.h ?? 200,
      };
    };
    const rects = selection.map(rect);
    const minX = Math.min(...rects.map((r) => r.x));
    const maxX = Math.max(...rects.map((r) => r.x + r.w));
    const midX = (minX + maxX) / 2;
    const minY = Math.min(...rects.map((r) => r.y));
    const maxY = Math.max(...rects.map((r) => r.y + r.h));
    const midY = (minY + maxY) / 2;

    rects.forEach((rectInfo) => {
      let { x, y } = rectInfo;
      if (mode === "left") x = minX;
      if (mode === "right") x = maxX - rectInfo.w;
      if (mode === "center") x = Math.round(midX - rectInfo.w / 2);
      if (mode === "top") y = minY;
      if (mode === "bottom") y = maxY - rectInfo.h;
      if (mode === "middle") y = Math.round(midY - rectInfo.h / 2);
      const layer = layers.find((l) => l.id === rectInfo.id);
      if (!layer) return;
      const layout = layer.view.layout || {};
      onChangeLayer(rectInfo.id, { layout: { ...layout, x, y } as any });
    });
  }

  function distribute(axis: "h" | "v") {
    if (selection.length < 3) return;
    const rects = selection.map((id) => {
      const layer = layers.find((l) => l.id === id);
      if (!layer) throw new Error(`Layer ${id} not found`);
      const layout = layer.view.layout || {};
      return {
        id,
        x: layout.x ?? 0,
        y: layout.y ?? 0,
        w: layout.w ?? 320,
        h: layout.h ?? 200,
      };
    });

    if (axis === "h") {
      const sorted = rects.slice().sort((a, b) => a.x - b.x);
      const min = sorted[0].x;
      const max = Math.max(...sorted.map((r) => r.x + r.w));
      const total = sorted.reduce((sum, r) => sum + r.w, 0);
      const space = (max - min - total) / (sorted.length - 1);
      let cursor = sorted[0].x + sorted[0].w + space;
      for (let i = 1; i < sorted.length - 1; i += 1) {
        const rectInfo = sorted[i];
        const layout = layers.find((l) => l.id === rectInfo.id)?.view.layout || {};
        onChangeLayer(rectInfo.id, {
          layout: { ...layout, x: Math.round(cursor - rectInfo.w / 2) } as any,
        });
        cursor += rectInfo.w + space;
      }
    } else {
      const sorted = rects.slice().sort((a, b) => a.y - b.y);
      const min = sorted[0].y;
      const max = Math.max(...sorted.map((r) => r.y + r.h));
      const total = sorted.reduce((sum, r) => sum + r.h, 0);
      const space = (max - min - total) / (sorted.length - 1);
      let cursor = sorted[0].y + sorted[0].h + space;
      for (let i = 1; i < sorted.length - 1; i += 1) {
        const rectInfo = sorted[i];
        const layout = layers.find((l) => l.id === rectInfo.id)?.view.layout || {};
        onChangeLayer(rectInfo.id, {
          layout: { ...layout, y: Math.round(cursor - rectInfo.h / 2) } as any,
        });
        cursor += rectInfo.h + space;
      }
    }
  }

  function equalize(mode: "w" | "h" | "both") {
    if (selection.length < 2) return;
    const reference = layers.find((l) => l.id === selection[0]);
    if (!reference) return;
    const layout = reference.view.layout || {};
    const width = layout.w ?? 320;
    const height = layout.h ?? 200;
    selection.slice(1).forEach((id) => {
      const currentLayout = layers.find((l) => l.id === id)?.view.layout || {};
      onChangeLayer(id, {
        layout: {
          ...currentLayout,
          w: mode === "w" || mode === "both" ? width : currentLayout.w ?? 320,
          h: mode === "h" || mode === "both" ? height : currentLayout.h ?? 200,
        } as any,
      });
    });
  }

  function reorder(op: "front" | "back" | "up" | "down") {
    if (!selection.length) return;
    const ids = layers.map((layer) => layer.id);
    const selected = new Set(selection);
    const remaining = ids.filter((id) => !selected.has(id));
    let result: string[] = [];
    if (op === "front") result = [...remaining, ...selection];
    if (op === "back") result = [...selection, ...remaining];
    if (op === "up") {
      result = ids.slice();
      for (let i = result.length - 2; i >= 0; i -= 1) {
        if (selected.has(result[i])) {
          const temp = result[i];
          result[i] = result[i + 1];
          result[i + 1] = temp;
        }
      }
    }
    if (op === "down") {
      result = ids.slice();
      for (let i = 1; i < result.length; i += 1) {
        if (selected.has(result[i])) {
          const temp = result[i];
          result[i] = result[i - 1];
          result[i - 1] = temp;
        }
      }
    }
    onReorderLayers(result);
  }

  async function saveSelection() {
    for (const id of selection) {
      await onCommitNewView(id);
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", gap: 12 }}>
      <CanvasToolbar
        selection={selection}
        onAlign={align}
        onDistribute={distribute}
        onEqualize={equalize}
        onReorder={reorder}
        onGroup={() => {}}
        onUngroup={() => {}}
        onSaveSelection={saveSelection}
        onLock={(value) =>
          selection.forEach((id) => onChangeLayer(id, { locked: value } as Partial<MessageView>))
        }
        onVisible={(value) =>
          selection.forEach((id) => onChangeLayer(id, { visible: value } as Partial<MessageView>))
        }
        smartSnap={smartSnap}
        setSmartSnap={setSmartSnap}
        baseline={baseline}
        setBaseline={setBaseline}
      />
      <div style={{ position: "relative" }}>
        <SelectionCanvas
          layers={layers}
          onChangeLayer={(id, next) => onChangeLayer(id, next)}
          onCommitNewView={(id) => onCommitNewView(id)}
          onSelectionChange={(ids) => setSelection(ids)}
          onReorderLayers={(ids) => onReorderLayers(ids)}
          smartSnap={smartSnap}
          baselinePx={20}
        />
        {baseline && <BaselineOverlay baseline={20} />}
      </div>
    </div>
  );
}
