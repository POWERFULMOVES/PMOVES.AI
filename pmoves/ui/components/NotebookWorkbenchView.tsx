"use client";

import { startTransition, useEffect, useMemo, useState, type ReactNode } from "react";
import { SkinProvider } from "@/runtime/skin/SkinProvider";
import {
  MultiViewEditor,
  SnapshotBrowser,
  SnapshotBookmarksPro,
  SnapshotScrubber,
  GroupManager,
  type MessageView,
  useSupabaseViews,
} from "@/runtime/notebook";

import DashboardNavigation, { type NavKey } from "@/components/DashboardNavigation";
import type { Message } from "@/runtime/notebook/useSupabaseViews";

const SKIN_URL = "/skins/comic-pop/1.1.0/skin.json";
const THEME_URL = "/styles/pbnj.css";

type EditorView = MessageView & { localId: string };

type Layer = {
  id: string;
  view: EditorView;
  content: ReactNode;
};

type NotebookWorkbenchViewProps = {
  showNavigation?: boolean;
  activeNavKey?: NavKey;
};

const cloneViews = (views: MessageView[]): EditorView[] =>
  views.map((view, index) => ({ ...view, localId: view.id ?? `${view.message_id}-${index}` }));

const stripEditorView = (view: EditorView): MessageView => {
  const { localId: _ignore, ...rest } = view;
  return rest;
};

export function NotebookWorkbenchView({
  showNavigation = true,
  activeNavKey = "notebook-workbench",
}: NotebookWorkbenchViewProps) {
  const [threadId, setThreadId] = useState("");
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [selection, setSelection] = useState<string[]>([]);
  const [draftViews, setDraftViews] = useState<Record<string, EditorView[]>>({});

  const { messages, views, saveNewView, loading, error } = useSupabaseViews(threadId);

  const messagesById = useMemo(() => {
    const map: Record<string, Message> = {};
    messages.forEach((message) => {
      map[message.id] = message;
    });
    return map;
  }, [messages]);

  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = THEME_URL;
    document.head.appendChild(link);
    return () => {
      document.head.removeChild(link);
    };
  }, []);

  useEffect(() => {
    if (!selectedMessageId && messages.length > 0) {
      startTransition(() => setSelectedMessageId(messages[0].id));
    }
  }, [messages, selectedMessageId]);

  useEffect(() => {
    if (!selectedMessageId) return;
    const source = views[selectedMessageId] || [];
    startTransition(() => {
      setDraftViews((prev) => {
        const current = prev[selectedMessageId];
        const needsClone =
          !current ||
          current.length !== source.length ||
          source.some((view, index) => current[index]?.id !== view.id);
        if (!needsClone) return prev;
        return { ...prev, [selectedMessageId]: cloneViews(source) };
      });
    });
  }, [selectedMessageId, views]);

  const activeDrafts = useMemo(
    () => (selectedMessageId ? draftViews[selectedMessageId] ?? [] : []),
    [draftViews, selectedMessageId]
  );

  const layers: Layer[] = useMemo(() => {
    if (!selectedMessageId) return [];
    return activeDrafts.map((view) => {
      const message = messagesById[view.message_id];
      const content = (
        <div style={{ display: "grid", gap: 8 }}>
          <strong style={{ fontFamily: "inherit" }}>{message?.text ?? "Message"}</strong>
          <small style={{ opacity: 0.65 }}>{view.variant || "primary"}</small>
        </div>
      );
      return { id: view.localId, view, content };
    });
  }, [activeDrafts, messagesById, selectedMessageId]);

  const availableMessages = useMemo(
    () => messages.map((message) => ({ id: message.id, text: message.text })),
    [messages]
  );

  const handleChangeLayer = (layerId: string, patch: Partial<MessageView>) => {
    if (!selectedMessageId) return;
    setDraftViews((prev) => {
      const list = (prev[selectedMessageId] || []).map((view) => {
        if (view.localId !== layerId) return view;
        const next: EditorView = { ...view, ...patch };
        if (patch.layout) {
          next.layout = { ...(view.layout || {}), ...(patch.layout as any) };
        }
        if (patch.style) {
          next.style = { ...(view.style || {}), ...(patch.style as any) };
        }
        return next;
      });
      return { ...prev, [selectedMessageId]: list };
    });
  };

  const handleCommitLayer = async (layerId: string) => {
    if (!selectedMessageId) return;
    const list = draftViews[selectedMessageId] || [];
    const match = list.find((view) => view.localId === layerId);
    if (!match) return;
    await saveNewView(stripEditorView(match));
  };

  const handleReorderLayers = (order: string[]) => {
    if (!selectedMessageId) return;
    setDraftViews((prev) => {
      const list = prev[selectedMessageId] || [];
      const map = new Map(list.map((view) => [view.localId, view] as const));
      const reordered = order
        .map((id) => map.get(id))
        .filter((view): view is EditorView => Boolean(view));
      return { ...prev, [selectedMessageId]: reordered };
    });
  };

  const persistSnapshotViews = async (snapshotViews: any[]) => {
    for (const snapshot of snapshotViews) {
      await saveNewView({
        message_id: snapshot.message_id,
        block_id: snapshot.block_id || snapshot.view_id,
        archetype: snapshot.archetype || "speech.round",
        variant: snapshot.variant || undefined,
        seed: snapshot.seed ?? undefined,
        layout: snapshot.layout || null,
        style: snapshot.style || null,
        locked: snapshot.locked ?? false,
        visible: snapshot.visible ?? true,
        z: snapshot.z ?? 0,
      });
    }
  };

  const layerFromSnapshot = (snapshot: any[]) =>
    snapshot.map((view: any, index: number) => ({
      id: `${view.message_id}-${index}`,
      view,
      content: <div>{messagesById[view.message_id]?.text || view.message_id}</div>,
    }));

  const handleSelectGroupMembers = (messageIds: string[]) => {
    if (!selectedMessageId) return;
    const ids = (draftViews[selectedMessageId] || [])
      .filter((view) => messageIds.includes(view.message_id))
      .map((view) => view.localId);
    setSelection(ids);
  };

  const resolvedNavKey: NavKey = activeNavKey ?? "notebook-workbench";
  const containerClasses = showNavigation
    ? "mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:gap-8 md:p-8"
    : undefined;

  return (
    <SkinProvider url={SKIN_URL}>
      <div className={containerClasses}>
        {showNavigation ? <DashboardNavigation active={resolvedNavKey} /> : null}
        <main style={{ padding: 24, display: "grid", gap: 24 }}>
          <header style={{ display: "grid", gap: 12 }}>
            <h1 style={{ margin: 0 }}>Notebook Workbench</h1>
            <p style={{ margin: 0, opacity: 0.75 }}>
              Explore chat message views, manage layout, and persist new variants directly into Supabase.
            </p>
            <label style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <span>Thread ID</span>
              <input
                value={threadId}
                onChange={(event) => {
                  const value = event.target.value.trim();
                  setThreadId(value);
                  setSelectedMessageId(null);
                  setDraftViews({});
                  setSelection([]);
                }}
                placeholder="00000000-0000-0000-0000-000000000000"
                style={{ minWidth: 320 }}
              />
            </label>
            {error && <p style={{ color: "#ff5c5c" }}>{error}</p>}
          </header>

          {!threadId ? (
            <section style={{ opacity: 0.7 }}>
              Enter a thread identifier to load messages, views, snapshots, and groups. Use `make supa-start` then run the seed script if you need demo content.
            </section>
          ) : (
            <div style={{ display: "grid", gap: 24 }}>
              <section style={{ display: "grid", gap: 12 }}>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                  <label>
                    <span style={{ display: "block", fontSize: 12, opacity: 0.7 }}>Message</span>
                    <select
                      value={selectedMessageId ?? ""}
                      onChange={(event) => {
                        setSelectedMessageId(event.target.value || null);
                        setSelection([]);
                      }}
                      style={{ minWidth: 260 }}
                    >
                      <option value="" disabled>
                        Choose a message…
                      </option>
                      {messages.map((message) => (
                        <option key={message.id} value={message.id}>
                          {message.text || message.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  <span style={{ opacity: 0.7 }}>{loading ? "Loading views…" : `${activeDrafts.length} views loaded`}</span>
                </div>
                {selectedMessageId && layers.length > 0 && (
                  <MultiViewEditor
                    layers={layers}
                    onChangeLayer={handleChangeLayer}
                    onCommitNewView={handleCommitLayer}
                    onReorderLayers={handleReorderLayers}
                    selection={selection}
                    onSelectionChange={setSelection}
                  />
                )}
                {selectedMessageId && layers.length === 0 && !loading && (
                  <p style={{ opacity: 0.7 }}>
                    This message has no saved views yet. Drag, position, and save a new layout.
                  </p>
                )}
              </section>

              <section style={{ display: "grid", gap: 24, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
                <GroupManager
                  threadId={threadId}
                  availableMessages={availableMessages}
                  onSelectGroupMembers={handleSelectGroupMembers}
                />
                <SnapshotBookmarksPro threadId={threadId} onPick={(iso) => console.log("bookmark", iso)} />
                <SnapshotScrubber
                  threadId={threadId}
                  onChange={(iso) => {
                    console.debug("Scrubber moved to", iso);
                  }}
                />
              </section>

              <section style={{ border: "1px solid #333", borderRadius: 12, padding: 16, display: "grid", gap: 16 }}>
                <h2 style={{ margin: 0 }}>Snapshots</h2>
                <SnapshotBrowser
                  threadId={threadId}
                  toLayers={layerFromSnapshot}
                  onPersist={persistSnapshotViews}
                />
              </section>
            </div>
          )}
        </main>
      </div>
    </SkinProvider>
  );
}

export default NotebookWorkbenchView;
