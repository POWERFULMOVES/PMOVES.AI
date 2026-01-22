import base64
import os
from typing import Dict

import pyqrcode
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="PMOVES Grayjay Plugin Host", version="0.1.0")


def _public_host_url(request: Request) -> str:
    configured = os.getenv("GRAYJAY_PLUGIN_HOST_PUBLIC_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _jellyfin_manifest(request: Request) -> Dict[str, str]:
    return {
        "id": os.getenv("GRAYJAY_JELLYFIN_PLUGIN_ID", "pmoves-jellyfin"),
        "name": os.getenv("GRAYJAY_JELLYFIN_PLUGIN_NAME", "PMOVES Jellyfin"),
        "type": "jellyfin",
        "description": os.getenv(
            "GRAYJAY_JELLYFIN_PLUGIN_DESCRIPTION",
            "Self-hosted Jellyfin integration for PMOVES.",
        ),
        "server_url": os.getenv("JELLYFIN_PUBLIC_URL", "http://localhost:8096"),
        "icon": os.getenv("GRAYJAY_JELLYFIN_PLUGIN_ICON", ""),
        "manifest_version": 1,
        "registry_url": f"{_public_host_url(request)}/plugins",
    }


@app.get("/healthz")
def healthz() -> Dict[str, bool]:
    return {"ok": True}


@app.get("/plugins")
def list_plugins(request: Request) -> Dict[str, object]:
    manifest_url = f"{_public_host_url(request)}/plugins/jellyfin/manifest"
    entry = {
        "id": os.getenv("GRAYJAY_JELLYFIN_PLUGIN_ID", "pmoves-jellyfin"),
        "name": os.getenv("GRAYJAY_JELLYFIN_PLUGIN_NAME", "PMOVES Jellyfin"),
        "manifest_url": manifest_url,
        "description": os.getenv(
            "GRAYJAY_JELLYFIN_PLUGIN_DESCRIPTION",
            "Connect Grayjay to the PMOVES Jellyfin instance.",
        ),
        "tags": ["jellyfin", "pmoves", "self-hosted"],
    }
    return {
        "title": os.getenv("GRAYJAY_PLUGIN_REGISTRY_TITLE", "PMOVES Plugin Registry"),
        "plugins": [entry],
    }


@app.get("/plugins/jellyfin/manifest")
def jellyfin_manifest(request: Request) -> Dict[str, object]:
    return _jellyfin_manifest(request)


@app.get("/plugins/jellyfin/qr")
def jellyfin_qr(request: Request) -> JSONResponse:
    manifest_url = f"{_public_host_url(request)}/plugins/jellyfin/manifest"
    qr = pyqrcode.create(manifest_url)
    buffer = qr.png_as_base64_str(scale=5)
    data_uri = f"data:image/png;base64,{buffer}"
    return JSONResponse({
        "manifest_url": manifest_url,
        "data_uri": data_uri,
    })


@app.get("/")
def root(request: Request) -> Dict[str, object]:
    return {
        "registry": os.getenv("GRAYJAY_PLUGIN_REGISTRY_TITLE", "PMOVES Plugin Registry"),
        "plugins_endpoint": f"{_public_host_url(request)}/plugins",
    }
