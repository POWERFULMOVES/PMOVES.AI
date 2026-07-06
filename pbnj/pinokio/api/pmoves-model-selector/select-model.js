// select-model.js — the model-selection UI. Pure UI over the live APIs:
//   registry        GET  http://127.0.0.1:8110/api/models
//   gpu-orchestrator GET http://127.0.0.1:8200/models   (loaded + registry known)
//   gpu-orchestrator POST http://127.0.0.1:8200/models/load           {model_id, provider}
//   gpu-orchestrator POST http://127.0.0.1:8200/models/unload/{provider}/{model_id}
//
// There are NO hardcoded model ids anywhere: the picker is built entirely from
// the API responses at runtime. Both services must be reachable for the load
// flow (the launcher is a thin UI, not a cache).
//
// Invoke from pinokio.js:
//   { href: "select-model.js" }                        -> load flow (default)
//   { href: "select-model.js", params: { action: "unload" } } -> unload flow
module.exports = {
  run: [
    // ================= LOAD FLOW (default) =================
    {
      method: "net",
      when: "{{args.action != 'unload'}}",
      params: { url: "http://127.0.0.1:8200/models", method: "get" }
    },
    {
      method: "local.set",
      when: "{{args.action != 'unload'}}",
      params: { gpu_models: "{{input}}" }
    },
    {
      method: "net",
      when: "{{args.action != 'unload'}}",
      params: { url: "http://127.0.0.1:8110/api/models", method: "get" }
    },
    {
      method: "local.set",
      when: "{{args.action != 'unload'}}",
      params: { registry_models: "{{input}}" }
    },
    {
      method: "input",
      when: "{{args.action != 'unload'}}",
      params: {
        title: "Load a model",
        description: "Pick a model to load via the gpu-orchestrator (:8200). List is built live from :8200/models + registry :8110.",
        form: [{
          type: "select",
          key: "selection",
          title: "Model (provider/model_id)",
          // Merge gpu-orchestrator (registry + loaded) with the registry :8110
          // catalog, dedupe on provider/model_id, carry a JSON {provider,model_id}
          // value so the load POST needs no hardcoded ids.
          items: "{{ (() => { const seen={}; const out=[]; const push=(id,prov,tag)=>{ if(!id) return; prov=prov||'ollama'; const k=prov+'/'+id; if(seen[k]) return; seen[k]=1; out.push({ text:k+(tag?' '+tag:''), value:JSON.stringify({provider:prov,model_id:id}) }); }; const g=local.gpu_models||{}; (g.registry||[]).forEach(m=>push(m.id||m.model_id, m.provider, m.vram_mb?('['+m.vram_mb+'MB]'):'')); (g.loaded||[]).forEach(m=>push(m.id||m.model_id||m.model_key, m.provider, '[loaded]')); const r=local.registry_models; const rl=Array.isArray(r)?r:((r&&(r.items||r.models||r.data))||[]); rl.forEach(m=>push(m.model_id||m.id||m.name, m.provider_type||m.provider, '(catalog)')); return out.length?out:[{text:'(no models reachable — is registry :8110 / gpu-orchestrator :8200 up?)', value:'{}'}]; })() }}"
        }]
      }
    },
    {
      method: "local.set",
      when: "{{args.action != 'unload'}}",
      params: { sel: "{{JSON.parse(input.selection)}}" }
    },
    {
      method: "net",
      when: "{{args.action != 'unload'}}",
      params: {
        url: "http://127.0.0.1:8200/models/load",
        method: "post",
        data: {
          model_id: "{{local.sel.model_id}}",
          provider: "{{local.sel.provider}}"
        }
      }
    },
    {
      method: "notify",
      when: "{{args.action != 'unload'}}",
      params: {
        html: "Load requested: {{local.sel.provider}}/{{local.sel.model_id}} — {{input.message || 'queued'}}"
      }
    },

    // ================= UNLOAD FLOW =================
    {
      method: "net",
      when: "{{args.action == 'unload'}}",
      params: { url: "http://127.0.0.1:8200/models/loaded", method: "get" }
    },
    {
      method: "local.set",
      when: "{{args.action == 'unload'}}",
      params: { loaded_models: "{{input}}" }
    },
    {
      method: "input",
      when: "{{args.action == 'unload'}}",
      params: {
        title: "Unload a model",
        description: "Pick a currently-loaded model to unload (gpu-orchestrator :8200).",
        form: [{
          type: "select",
          key: "usel",
          title: "Loaded model (provider/model_id)",
          items: "{{ (() => { const out=[]; const r=local.loaded_models; const ll=Array.isArray(r)?r:((r&&(r.models||r.loaded))||[]); ll.forEach(m=>{ const id=m.id||m.model_id||m.model_key; const prov=m.provider||'ollama'; if(!id) return; out.push({ text:prov+'/'+id, value:JSON.stringify({provider:prov,model_id:id}) }); }); return out.length?out:[{text:'(no loaded models — nothing to unload)', value:'{}'}]; })() }}"
        }]
      }
    },
    {
      method: "local.set",
      when: "{{args.action == 'unload'}}",
      params: { sel: "{{JSON.parse(input.usel)}}" }
    },
    {
      method: "net",
      when: "{{args.action == 'unload'}}",
      params: {
        url: "http://127.0.0.1:8200/models/unload/{{local.sel.provider}}/{{local.sel.model_id}}",
        method: "post"
      }
    },
    {
      method: "notify",
      when: "{{args.action == 'unload'}}",
      params: {
        html: "Unload requested: {{local.sel.provider}}/{{local.sel.model_id}} — {{input.message || 'done'}}"
      }
    }
  ]
}
