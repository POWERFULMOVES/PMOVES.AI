import os, json, re
from typing import Dict, Any
import requests

from .base import BaseProvider

def _parse_json_from_text(text: str) -> Dict[str, Any]:
    # Try to extract JSON block from text (handles fenced code blocks)
    m = re.search(r"\{[\s\S]*\}\s*$", text.strip())
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # fallback entire content
    try:
        return json.loads(text)
    except Exception:
        return {"chunks": [], "errors": []}

SYS_PROMPT = (
    "You are a precise information extraction engine. Segment input into a small set of coherent chunks suitable for retrieval (50-300 words each). "
    "Also extract any troubleshooting errors. Return strict JSON with fields: {chunks: [{doc_id, section_id, chunk_id, namespace, text, kind}], errors: [{message, code, service, host, severity, timestamp, stack}]}."
)

USER_TMPL_TEXT = (
    "Namespace: {ns} DocID: {doc}\n\n"
    "Text to segment and analyze:\n"""{content}"""\n"
)

USER_TMPL_XML = (
    "Namespace: {ns} DocID: {doc}\n\n"
    "XML to segment and analyze for IT errors:\n"""{content}"""\n"
)

class OpenAIChatProvider(BaseProvider):
    def __init__(self):
        self.base = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENROUTER_API_BASE", "https://api.openai.com")
        self.key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        if not self.key:
            raise RuntimeError("OpenAI-compatible provider selected but no API key configured")

    def _chat(self, content: str) -> Dict[str, Any]:
        url = f"{self.base.rstrip('/')}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.key}", "content-type": "application/json"}
        data = {"model": self.model, "response_format": {"type":"json_object"}, "messages": [
            {"role":"system","content": SYS_PROMPT},
            {"role":"user","content": content}
        ]}
        r = requests.post(url, headers=headers, json=data, timeout=60)
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"]
        return _parse_json_from_text(txt)

    def extract_text(self, document: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        body = USER_TMPL_TEXT.format(ns=namespace, doc=doc_id, content=document)
        return self._chat(body)

    def extract_xml(self, xml: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        body = USER_TMPL_XML.format(ns=namespace, doc=doc_id, content=xml)
        return self._chat(body)

class GeminiProvider(BaseProvider):
    def __init__(self):
        self.key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        if not self.key:
            raise RuntimeError("Gemini provider selected but no API key configured")

    def _call(self, content: str) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.key}"
        payload = {"contents": [{"parts": [{"text": SYS_PROMPT + "\n\n" + content}]}]}
        r = requests.post(url, headers={"content-type":"application/json"}, json=payload, timeout=60)
        r.raise_for_status()
        txt = (r.json().get("candidates") or [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        return _parse_json_from_text(txt)

    def extract_text(self, document: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        return self._call(USER_TMPL_TEXT.format(ns=namespace, doc=doc_id, content=document))

    def extract_xml(self, xml: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        return self._call(USER_TMPL_XML.format(ns=namespace, doc=doc_id, content=xml))

