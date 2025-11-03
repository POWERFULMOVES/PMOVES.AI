"use client";

import React, { useMemo, useState } from "react";
import { useGroups } from "./useGroups";

type MemberCandidate = { id: string; text?: string };

type Props = {
  threadId: string;
  availableMessages: MemberCandidate[];
  onSelectGroupMembers?: (ids: string[]) => void;
  onFocusGroup?: (groupId: string | null) => void;
};

export function GroupManager({
  threadId,
  availableMessages,
  onSelectGroupMembers,
  onFocusGroup,
}: Props) {
  const { groups, members, createGroup, renameGroup, deleteGroup, addMember, removeMember } = useGroups(threadId);
  const [newName, setNewName] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

  const selectedMembers = useMemo(() => {
    if (!selectedGroupId) return new Set<string>();
    return new Set(members[selectedGroupId] || []);
  }, [members, selectedGroupId]);

  return (
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 8,
        padding: 12,
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 12,
      }}
    >
      <div>
        <h3 style={{ marginTop: 0 }}>Groups</h3>
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {groups.map((group) => (
            <li key={group.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button
                onClick={() => {
                  setSelectedGroupId(group.id);
                  onFocusGroup?.(group.id);
                }}
                style={{ minWidth: 120, textAlign: "left" }}
              >
                {group.name}
              </button>
              <button
                onClick={() => {
                  const name = window.prompt("Rename group", group.name) || group.name;
                  renameGroup(group.id, name);
                }}
              >
                Rename
              </button>
              <button onClick={() => deleteGroup(group.id)}>Delete</button>
              <button onClick={() => onSelectGroupMembers?.(members[group.id] || [])}>Select</button>
            </li>
          ))}
        </ul>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <input
            placeholder="New group name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
          />
          <button
            onClick={async () => {
              if (!newName) return;
              const group = await createGroup(newName);
              if (group) {
                setSelectedGroupId(group.id);
                onFocusGroup?.(group.id);
              }
              setNewName("");
            }}
          >
            Create
          </button>
        </div>
      </div>
      <div>
        <h3 style={{ marginTop: 0 }}>Members</h3>
        {selectedGroupId ? (
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 6,
              maxHeight: 240,
              overflowY: "auto",
            }}
          >
            {availableMessages.map((message) => {
              const checked = selectedMembers.has(message.id);
              return (
                <li key={message.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) =>
                        event.target.checked
                          ? addMember(selectedGroupId, message.id)
                          : removeMember(selectedGroupId, message.id)
                      }
                    />
                    <span style={{ maxWidth: 180, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {message.text || message.id}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        ) : (
          <p>Select a group to manage members.</p>
        )}
      </div>
    </div>
  );
}
