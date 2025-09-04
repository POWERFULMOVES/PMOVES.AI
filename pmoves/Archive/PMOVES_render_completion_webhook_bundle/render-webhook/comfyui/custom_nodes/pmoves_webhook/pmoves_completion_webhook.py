
# PMOVES ComfyUI node: POST completion to webhook
import os, requests, json

WEBHOOK_URL = os.environ.get("PMOVES_WEBHOOK_URL","http://localhost:8085/comfy/webhook")
WEBHOOK_TOKEN = os.environ.get("PMOVES_WEBHOOK_TOKEN","")

def _headers():
    h = {"content-type":"application/json"}
    if WEBHOOK_TOKEN:
        h["Authorization"] = f"Bearer {WEBHOOK_TOKEN}"
    return h

class PMovesCompletionWebhook:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "s3_uri": ("STRING",),
                "presigned_get": ("STRING",),
                "bucket": ("STRING", {"default":"outputs"}),
                "key": ("STRING", {"default":"comfy/result.png"}),
                "title": ("STRING", {"default":"Comfy Render"}),
                "namespace": ("STRING", {"default":"pmoves"}),
                "author": ("STRING", {"default":"DARKXSIDE"}),
                "tags": ("STRING", {"default":"comfy,render"}),
                "auto_approve": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "graph_hash": ("STRING", {"default":""})
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("studio_response",)
    FUNCTION = "notify"
    CATEGORY = "PMOVES/Webhook"

    def notify(self, s3_uri, presigned_get, bucket, key, title, namespace, author, tags, auto_approve, graph_hash=""):
        j = {
            "bucket": bucket, "key": key,
            "s3_uri": s3_uri, "presigned_get": presigned_get,
            "title": title, "namespace": namespace,
            "author": author, "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
            "auto_approve": bool(auto_approve),
            "graph_hash": graph_hash or None
        }
        r = requests.post(WEBHOOK_URL, headers=_headers(), data=json.dumps(j), timeout=20)
        r.raise_for_status()
        return (r.text,)

NODE_CLASS_MAPPINGS = {
    "PMovesCompletionWebhook": PMovesCompletionWebhook
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PMovesCompletionWebhook": "PMOVES • Completion Webhook → Supabase"
}
