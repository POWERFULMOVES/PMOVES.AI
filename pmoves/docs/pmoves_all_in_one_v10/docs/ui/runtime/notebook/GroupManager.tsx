import React, { useMemo, useState } from "react";
import { useGroups } from "./useGroups";
export function GroupManager({ threadId, availableMessages, onSelectGroupMembers }:{ threadId:string; availableMessages:{id:string;text?:string}[]; onSelectGroupMembers?:(ids:string[])=>void; }){
  const { groups, members, createGroup, renameGroup, deleteGroup, addMember, removeMember } = useGroups(threadId);
  const [newName,setNewName]=useState(""); const [selected,setSelected]=useState<string|null>(null);
  const groupMembers = useMemo(()=> selected ? new Set(members[selected]||[]) : new Set<string>(), [selected, members]);
  return (<div style={{ border:"1px solid #333", borderRadius:8, padding:12, display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
    <div><h3 style={{marginTop:0}}>Groups</h3>
      <ul style={{listStyle:"none",padding:0,margin:0,display:"flex",flexDirection:"column",gap:6}}>
        {groups.map(g=>(<li key={g.id} style={{display:"flex",gap:8,alignItems:"center"}}><button onClick={()=>setSelected(g.id)} style={{minWidth:120,textAlign:"left"}}>{g.name}</button><button onClick={()=>{ const name=prompt("Rename group",g.name)||g.name; renameGroup(g.id,name); }}>Rename</button><button onClick={()=>deleteGroup(g.id)}>Delete</button><button onClick={()=> onSelectGroupMembers?.(members[g.id]||[]) }>Select</button></li>))}
      </ul>
      <div style={{display:"flex",gap:8,marginTop:8}}><input placeholder="New group name" value={newName} onChange={e=>setNewName(e.target.value)} /><button onClick={async()=>{ if(!newName) return; const g=await createGroup(newName); if(g) setSelected(g.id); setNewName(""); }}>Create</button></div>
    </div>
    <div><h3 style={{marginTop:0}}>Members</h3>
      {selected ? (<ul style={{listStyle:"none",padding:0,margin:0,display:"grid",gridTemplateColumns:"1fr 1fr",gap:6,maxHeight:240,overflowY:"auto"}}>
        {availableMessages.map(m=>{ const checked=groupMembers.has(m.id); return (<li key={m.id} style={{display:"flex",alignItems:"center",gap:8}}><label style={{display:"flex",alignItems:"center",gap:6}}><input type="checkbox" checked={checked} onChange={e=> e.target.checked ? addMember(selected,m.id) : removeMember(selected,m.id) } /><span style={{maxWidth:180,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{m.text||m.id}</span></label></li>); })}
      </ul>) : <p>Select a group to manage members.</p>}
    </div>
  </div>);
}