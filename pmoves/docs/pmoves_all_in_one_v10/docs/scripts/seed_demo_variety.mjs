import { createClient } from '@supabase/supabase-js';
const url=process.env.SUPABASE_URL, key=process.env.SUPABASE_ANON_KEY, threadId=process.env.THREAD_ID, userId=process.env.USER_ID;
if(!url||!key||!threadId||!userId){ console.error("Set SUPABASE_URL, SUPABASE_ANON_KEY, THREAD_ID, USER_ID"); process.exit(1); }
const supabase=createClient(url,key); const rnd=()=>Math.floor(Math.random()*2**31);
async function main(){
  const msgs=[ { text:"hey! quick status update?", archetype:"speech.round", variant:"primary" }, { text:"ALERT: anomaly detected!", archetype:"speech.shout", variant:"shout" }, { text:"hmm… let me think about this.", archetype:"thought.cloud", variant:"primary" } ];
  for (const m of msgs){
    const { data:msg, error } = await supabase.from('chat_messages').insert({ thread_id:threadId, author_id:userId, role:'user', text:m.text, cgp:{ codebook:"pmoves-cgp-32k@1", spectrum:[Math.random(),Math.random()] } }).select('*').single(); if(error) throw error;
    const { data:block, error:e2 } = await supabase.from('content_blocks').insert({ message_id:msg.id, kind:'text', uri:'inline://text', meta:{ lang:'en' } }).select('*').single(); if(e2) throw e2;
    const { error:e3 } = await supabase.from('message_views').insert({ message_id:msg.id, block_id:block.id, archetype:m.archetype, variant:m.variant, seed:rnd(), layout:{ x:80+Math.floor(Math.random()*120), y:80+Math.floor(Math.random()*120), w:320, h:200, z:0 } }); if(e3) throw e3;
  } console.log("Seeded 3 messages with views.");
} main().catch(e=>{ console.error(e); process.exit(1); });