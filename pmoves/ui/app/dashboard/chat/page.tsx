"use client";

import { useEffect, useState } from "react";
import DashboardNavigation from "../../../components/DashboardNavigation";

type ChatMsg = { id: number; role: string; agent?: string | null; avatar_url?: string | null; content: string; created_at: string };

async function fetchMessages(): Promise<ChatMsg[]> {
  const res = await fetch('/api/chat/messages', { cache: 'no-store' });
  if (!res.ok) return [];
  const j = await res.json();
  return (j.items ?? []) as ChatMsg[];
}

async function sendMessage(content: string): Promise<void> {
  await fetch('/api/chat/send', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ content, role: 'user' })});
}

export default function ChatDashboardPage() {
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    let active = true;
    const load = async () => { const m = await fetchMessages(); if (active) setMsgs(m); };
    load();
    const t = setInterval(load, 3000);
    return () => { active = false; clearInterval(t); };
  }, []);

  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="chat" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Realtime Chat</h1>
        <p className="text-sm text-neutral-600">Unified chat feed; agent avatars and true realtime will be wired next.</p>
      </header>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2 rounded border border-neutral-200 p-4">
          <div className="flex flex-col gap-3 max-h-[480px] overflow-auto">
            {msgs.map((m) => (
              <div key={m.id} className="flex items-start gap-3">
                <img src={m.avatar_url || '/avatars/owner.png'} alt={m.agent || m.role} className="h-8 w-8 rounded-full border" />
                <div>
                  <div className="text-xs text-neutral-500">{new Date(m.created_at).toLocaleString()} – {m.agent || m.role}</div>
                  <div className="text-sm whitespace-pre-wrap">{m.content}</div>
                </div>
              </div>
            ))}
            {msgs.length === 0 && <div className="text-sm text-neutral-500">No messages yet.</div>}
          </div>
          <form className="mt-4 flex gap-2" onSubmit={async (e) => { e.preventDefault(); const c = input.trim(); if (!c) return; setInput(''); await sendMessage(c); setMsgs(await fetchMessages()); }}>
            <input id="chatMessage" name="chatMessage" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type a message…" className="flex-1 rounded border px-2 py-1" />
            <button className="rounded bg-slate-900 px-3 py-1 text-white">Send</button>
          </form>
        </div>
        <div className="rounded border border-neutral-200 p-4 text-sm">
          <div className="mb-2 font-medium">Native UIs</div>
          <ul className="list-disc pl-4">
            <li><a className="underline" href={process.env.NEXT_PUBLIC_ARCHON_UI_URL || 'http://localhost:3737'} target="_blank" rel="noreferrer">Archon UI</a></li>
            <li><a className="underline" href={process.env.NEXT_PUBLIC_AGENT_ZERO_UI_URL || 'http://localhost:8081'} target="_blank" rel="noreferrer">Agent Zero UI</a></li>
          </ul>
        </div>
      </div>
    </div>
  );
}
