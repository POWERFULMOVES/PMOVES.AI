"use client";

import React, { useEffect, useState } from "react";
import { ComicBubble } from "@/runtime/skin/ComicBubble";
import type { MessageView } from "./useSupabaseViews";

type Layer = { id: string; view: MessageView; content?: React.ReactNode };

type SelectionState = { ids: Set<string> };

type DragState =
  | {
      id: string;
      start: { x: number; y: number };
      orig: { x: number; y: number; w: number; h: number };
      mode: "move";
    }
  | {
      id: string;
      start: { x: number; y: number };
      orig: { x: number; y: number; w: number; h: number };
      mode: "resize";
      handle: string;
    };

type Props = {
  layers: Layer[];
  onChangeLayer?: (id: string, next: Partial<MessageView>) => void;
  onCommitNewView?: (id: string) => void;
  onSelectionChange?: (ids: string[]) => void;
  onReorderLayers?: (ids: string[]) => void;
  smartSnap?: boolean;
  baselinePx?: number;
};

type Guides = { v?: number; h?: number };

type Rect = { x: number; y: number; w: number; h: number };

type Point = { x: number; y: number };

const defaultRect = (layout: any): Rect => ({
  x: layout?.x ?? 80,
  y: layout?.y ?? 80,
  w: layout?.w ?? 320,
  h: layout?.h ?? 200,
});

export function SelectionCanvas({
  layers,
  onChangeLayer,
  onCommitNewView,
  onSelectionChange,
  onReorderLayers: _onReorderLayers,
  smartSnap = true,
  baselinePx = 20,
}: Props) {
  const [selection, setSelection] = useState<SelectionState>({ ids: new Set() });
  const [drag, setDrag] = useState<DragState | null>(null);
  const [guides, setGuides] = useState<Guides>({});

  useEffect(() => {
    function nudge(id: string, dx: number, dy: number) {
      const layer = layers.find((l) => l.id === id);
      if (!layer || !onChangeLayer) return;
      const layout = layer.view.layout || {};
      onChangeLayer(id, {
        layout: {
          ...layout,
          x: (layout.x ?? 0) + dx,
          y: (layout.y ?? 0) + dy,
        } as any,
      });
    }

    function onKey(event: KeyboardEvent) {
      if (selection.ids.size === 0) return;
      const delta = event.shiftKey ? 10 : 1;
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
      }
      if (event.key === "ArrowLeft") selection.ids.forEach((id) => nudge(id, -delta, 0));
      if (event.key === "ArrowRight") selection.ids.forEach((id) => nudge(id, delta, 0));
      if (event.key === "ArrowUp") selection.ids.forEach((id) => nudge(id, 0, -delta));
      if (event.key === "ArrowDown") selection.ids.forEach((id) => nudge(id, 0, delta));
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [layers, onChangeLayer, selection.ids]);

  function updateSelection(id: string, additive: boolean) {
    setSelection((prev) => {
      const ids = new Set(additive ? prev.ids : []);
      if (additive && ids.has(id)) {
        ids.delete(id);
      } else {
        ids.add(id);
      }
      const next = { ids };
      onSelectionChange?.(Array.from(ids));
      return next;
    });
  }

  function computeSnap(x: number, y: number, w: number, h: number): [Point, Guides] {
    if (!smartSnap) return [{ x, y }, {}];
    const threshold = 6;
    const edges = layers.map((layer) => {
      const layout = defaultRect(layer.view.layout);
      return {
        left: layout.x,
        right: layout.x + layout.w,
        cx: layout.x + layout.w / 2,
        top: layout.y,
        bottom: layout.y + layout.h,
        cy: layout.y + layout.h / 2,
      };
    });

    let snappedX = x;
    let snappedY = y;
    let vGuide: number | undefined;
    let hGuide: number | undefined;

    const candidatesX = [x, x + w, x + w / 2];
    const candidatesY = [y, y + h, y + h / 2];

    candidatesX.forEach((candidate) => {
      edges.forEach((edge) => {
        [edge.left, edge.right, edge.cx].forEach((target) => {
          if (Math.abs(candidate - target) <= threshold) {
            const delta = target - candidate;
            snappedX += delta;
            vGuide = target;
          }
        });
      });
    });

    candidatesY.forEach((candidate) => {
      edges.forEach((edge) => {
        [edge.top, edge.bottom, edge.cy].forEach((target) => {
          if (Math.abs(candidate - target) <= threshold) {
            const delta = target - candidate;
            snappedY += delta;
            hGuide = target;
          }
        });
      });
    });

    if (baselinePx > 0) {
      const baseline = Math.round(snappedY / baselinePx) * baselinePx;
      if (Math.abs(baseline - snappedY) <= threshold) {
        snappedY = baseline;
        hGuide = baseline;
      }
    }

    return [{ x: snappedX, y: snappedY }, { v: vGuide, h: hGuide }];
  }

  function beginDragMove(event: React.MouseEvent, id: string) {
    const layer = layers.find((l) => l.id === id);
    if (!layer) return;
    const layout = defaultRect(layer.view.layout);
    const locked = (layer.view as any).locked === true;
    if (locked) return;

    updateSelection(id, event.shiftKey || event.metaKey || event.ctrlKey);
    const start = { x: event.clientX, y: event.clientY };
    setDrag({ id, start, orig: layout, mode: "move" });
    const doc = (event.currentTarget as HTMLElement).ownerDocument;
    doc.addEventListener("mousemove", handleMouseMove);
    doc.addEventListener("mouseup", handleMouseUp);
  }

  function beginResize(event: React.MouseEvent, id: string, handle: string) {
    event.stopPropagation();
    const layer = layers.find((l) => l.id === id);
    if (!layer) return;
    const layout = defaultRect(layer.view.layout);
    const locked = (layer.view as any).locked === true;
    if (locked) return;

    const start = { x: event.clientX, y: event.clientY };
    setDrag({ id, start, orig: layout, mode: "resize", handle });
    const doc = (event.currentTarget as HTMLElement).ownerDocument;
    doc.addEventListener("mousemove", handleMouseMove);
    doc.addEventListener("mouseup", handleMouseUp);
  }

  function handleMouseMove(event: MouseEvent) {
    setDrag((current) => {
      if (!current) return current;
      const dx = event.clientX - current.start.x;
      const dy = event.clientY - current.start.y;

      if (current.mode === "move") {
        const [point, guide] = computeSnap(
          current.orig.x + dx,
          current.orig.y + dy,
          current.orig.w,
          current.orig.h,
        );
        setGuides(guide);
        selection.ids.forEach((id) => {
          const layer = layers.find((l) => l.id === id);
          if (!layer || !onChangeLayer) return;
          const layout = layer.view.layout || {};
          onChangeLayer(id, {
            layout: {
              ...layout,
              x: point.x,
              y: point.y,
            } as any,
          });
        });
      } else {
        const { orig } = current;
        let x = orig.x;
        let y = orig.y;
        let w = orig.w;
        let h = orig.h;

        if (current.handle.includes("r")) w = Math.max(0, orig.w + dx);
        if (current.handle.includes("l")) {
          w = Math.max(0, orig.w - dx);
          x = orig.x + dx;
        }
        if (current.handle.includes("b")) h = Math.max(0, orig.h + dy);
        if (current.handle.includes("t")) {
          h = Math.max(0, orig.h - dy);
          y = orig.y + dy;
        }

        const [point, guide] = computeSnap(x, y, w, h);
        setGuides(guide);
        if (onChangeLayer) {
          const layer = layers.find((l) => l.id === current.id);
          const layout = layer?.view.layout || {};
          onChangeLayer(current.id, {
            layout: {
              ...layout,
              x: point.x,
              y: point.y,
              w,
              h,
            } as any,
          });
        }
      }
      return current;
    });
  }

  function handleMouseUp(event: MouseEvent) {
    const doc = (event.target as HTMLElement)?.ownerDocument ?? document;
    doc.removeEventListener("mousemove", handleMouseMove);
    doc.removeEventListener("mouseup", handleMouseUp);
    if (drag) {
      if (drag.mode === "move") {
        selection.ids.forEach((id) => onCommitNewView?.(id));
      } else {
        onCommitNewView?.(drag.id);
      }
    }
    setGuides({});
    setDrag(null);
  }

  function renderHandles(id: string, x: number, y: number, w: number, h: number) {
    const size = 8;
    const handles: Array<[string, number, number, string]> = [
      ["tl", x - size / 2, y - size / 2, "nwse-resize"],
      ["tr", x + w - size / 2, y - size / 2, "nesw-resize"],
      ["bl", x - size / 2, y + h - size / 2, "nesw-resize"],
      ["br", x + w - size / 2, y + h - size / 2, "nwse-resize"],
      ["l", x - size / 2, y + h / 2 - size / 2, "ew-resize"],
      ["r", x + w - size / 2, y + h / 2 - size / 2, "ew-resize"],
      ["t", x + w / 2 - size / 2, y - size / 2, "ns-resize"],
      ["b", x + w / 2 - size / 2, y + h - size / 2, "ns-resize"],
    ];
    return handles.map(([key, left, top, cursor]) => (
      <div
        key={key}
        onMouseDown={(evt) => beginResize(evt, id, key)}
        style={{
          position: "absolute",
          left,
          top,
          width: size,
          height: size,
          background: "#ffd400",
          border: "1px solid #121212",
          cursor,
        }}
      />
    ));
  }

  return (
    <div
      className="pmoves-canvas"
      style={{
        position: "relative",
        width: "100%",
        height: 480,
        background: "#0b0b10",
        border: "1px dashed #333",
        borderRadius: 8,
      }}
    >
      {guides.v !== undefined && (
        <div style={{ position: "absolute", left: guides.v, top: 0, bottom: 0, width: 1, background: "#ffd400" }} />
      )}
      {guides.h !== undefined && (
        <div style={{ position: "absolute", top: guides.h, left: 0, right: 0, height: 1, background: "#ffd400" }} />
      )}
      {layers.map((layer) => {
        const layout = defaultRect(layer.view.layout);
        const { x, y, w, h } = layout;
        const isSelected = selection.ids.has(layer.id);
        const locked = (layer.view as any).locked === true;
        const visible = (layer.view as any).visible !== false;
        if (!visible) return null;
        return (
          <div
            key={layer.id}
            onMouseDown={locked ? undefined : (event) => beginDragMove(event, layer.id)}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: w,
              height: h,
              cursor: locked ? "not-allowed" : "move",
              opacity: locked ? 0.85 : 1,
            }}
          >
            <ComicBubble
              archetype={layer.view.archetype}
              variant={layer.view.variant || "primary"}
              seed={layer.view.seed || 42}
              className="w-full h-full"
            >
              {layer.content || <div style={{ textAlign: "center" }}>Content</div>}
            </ComicBubble>
            {isSelected && !locked && (
              <>
                <div style={{ position: "absolute", inset: 0, border: "2px solid #ffd400", pointerEvents: "none" }} />
                {renderHandles(layer.id, x, y, w, h)}
              </>
            )}
            {locked && (
              <div
                style={{
                  position: "absolute",
                  top: 4,
                  right: 4,
                  background: "#0b0b10",
                  border: "1px solid #333",
                  borderRadius: 4,
                  padding: "2px 6px",
                  fontSize: 12,
                }}
              >
                🔒
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
