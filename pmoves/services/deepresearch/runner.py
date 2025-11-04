"""Runtime support for deep research executions."""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, Iterable, Optional

from .cookbooks import load_cookbooks
from .models import ResearchRequest

CookbookLoader = Callable[[Iterable[str]], Dict[str, str]]
DispatchFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def _excerpt(markdown: str, limit: int = 500) -> str:
    text = markdown.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}…"


class DeepResearchRunner:
    """Coordinates context assembly and provider dispatch for deep research."""

    def __init__(
        self,
        *,
        openrouter_client: Optional[DispatchFn] = None,
        local_client: Optional[DispatchFn] = None,
        cookbook_loader: CookbookLoader = load_cookbooks,
    ) -> None:
        self._openrouter_client = openrouter_client
        self._local_client = local_client
        self._cookbook_loader = cookbook_loader

    def _prepare_user_payload(self, request: ResearchRequest) -> Dict[str, Any]:
        user_payload: Dict[str, Any] = {
            "prompt": request.prompt,
            "context": list(request.context),
        }
        if request.metadata:
            user_payload["metadata"] = copy.deepcopy(request.metadata)
        notebook = copy.deepcopy(request.notebook) if request.notebook else {}
        if notebook:
            user_payload["notebook"] = notebook
        resources = request.resources
        if resources and resources.cookbooks:
            cookbook_payload = self._cookbook_loader(resources.cookbooks)
            if cookbook_payload:
                context_entries = user_payload.setdefault("context", [])
                notebook = user_payload.setdefault("notebook", {})
                attachments = notebook.setdefault("attachments", [])
                for path, content in cookbook_payload.items():
                    context_entries.append(f"# Cookbook: {path}\n\n{content}")
                    attachments.append(
                        {
                            "type": "cookbook",
                            "path": path,
                            "excerpt": _excerpt(content),
                        }
                    )
                user_payload.setdefault("resources", {})["cookbooks"] = list(
                    cookbook_payload.keys()
                )
        if request.model:
            user_payload["model"] = request.model
        return user_payload

    def _dispatch(
        self, client: Optional[DispatchFn], provider: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if client is not None:
            return client(payload)
        return {"provider": provider, "payload": payload}

    def _run_openrouter(self, request: ResearchRequest) -> Dict[str, Any]:
        user_payload = self._prepare_user_payload(request)
        return self._dispatch(self._openrouter_client, "openrouter", user_payload)

    def _run_local(self, request: ResearchRequest) -> Dict[str, Any]:
        user_payload = self._prepare_user_payload(request)
        return self._dispatch(self._local_client, "local", user_payload)
