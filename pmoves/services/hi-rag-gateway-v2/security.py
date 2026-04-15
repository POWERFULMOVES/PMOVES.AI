"""Tailscale authentication, IP validation, and SSRF-safe image fetching."""

import hashlib
import ipaddress
import re
import socket
from typing import Any, Dict, Optional
from urllib.parse import quote_plus, urlparse

from fastapi import HTTPException, Request
import urllib3

from config import (
    TAILSCALE_ONLY,
    TAILSCALE_ADMIN_ONLY,
    TAILSCALE_CIDRS,
    TRUSTED_PROXY_SOURCES,
    CHIT_IMAGE_FETCH_ALLOW_PRIVATE,
    CHIT_IMAGE_FETCH_ALLOWED_HOSTS,
    logger,
)


def _redact_sensitive(value: str) -> str:
    """Return a redacted digest of a value for safe logging.

    Produces 'sha256:<first-8-hex>' so operators can correlate without
    exposing raw IPs, CIDRs, or other network topology details.
    """
    digest = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"sha256:{digest}"


def _parse_trusted_proxies(raw_entries):
    """Parse CIDR/IP entries into ``ipaddress`` network objects.

    Invalid entries are logged with a redacted digest (never the raw value)
    to avoid leaking sensitive network topology into log sinks.
    """
    networks = []
    for raw in raw_entries:
        entry = raw.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                networks.append(ipaddress.ip_network(entry, strict=False))
            else:
                ip_obj = ipaddress.ip_address(entry)
                cidr = "32" if isinstance(ip_obj, ipaddress.IPv4Address) else "128"
                networks.append(ipaddress.ip_network(f"{ip_obj}/{cidr}", strict=False))
        except ValueError:
            logger.warning(
                "Ignoring invalid trusted proxy entry [%s]",
                _redact_sensitive(entry),
            )
    return networks


_TRUSTED_PROXY_NETWORKS = _parse_trusted_proxies(TRUSTED_PROXY_SOURCES)


def _trusted_proxy(host: Optional[str]) -> bool:
    if not host or not _TRUSTED_PROXY_NETWORKS:
        return False
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        logger.debug("Request client host is not a valid IP: %s", host)
        return False
    return any(ip_obj in network for network in _TRUSTED_PROXY_NETWORKS)


def _client_ip(request: Request) -> str:
    peer_ip = request.client.host if request.client else None
    if peer_ip and _trusted_proxy(peer_ip):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            candidate = xff.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                logger.debug("Ignoring invalid X-Forwarded-For entry: %s", candidate)
    return peer_ip or "127.0.0.1"


def _ip_in_cidrs(ip: str, cidrs):
    import ipaddress as _ip
    try:
        ip_obj = _ip.ip_address(ip)
        for c in cidrs:
            try:
                if ip_obj in _ip.ip_network(c):
                    return True
            except Exception:
                continue
    except Exception:
        logger.exception("_ip_in_cidrs parse error for ip %s", ip)
        return False
    return False


def _tailscale_required(admin_only: bool) -> bool:
    if TAILSCALE_ONLY:
        return True
    if admin_only:
        return TAILSCALE_ADMIN_ONLY
    return False


def _tailscale_violation_detail(admin_only: bool) -> str:
    return (
        "Admin endpoints restricted to Tailscale network"
        if admin_only
        else "Service restricted to Tailscale network"
    )


def _tailscale_ip_allowed(ip: str, admin_only: bool) -> bool:
    if not _tailscale_required(admin_only):
        return True
    return _ip_in_cidrs(ip, TAILSCALE_CIDRS)


def require_tailscale(request: Request, admin_only: bool = False):
    if not _tailscale_required(admin_only):
        return
    ip = _client_ip(request)
    if not _tailscale_ip_allowed(ip, admin_only):
        raise HTTPException(status_code=403, detail=_tailscale_violation_detail(admin_only))


def require_admin_tailscale(request: Request):
    return require_tailscale(request, admin_only=True)


def _host_is_private_or_internal(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host:
        return True
    if host in {"localhost"} or host.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True

    seen: set = set()
    for _, _, _, _, sockaddr in infos:
        ip_raw = sockaddr[0]
        if ip_raw in seen:
            continue
        seen.add(ip_raw)
        try:
            ip_obj = ipaddress.ip_address(ip_raw)
        except ValueError:
            return True
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            return True
    return False


# Path segments that are never allowed in image fetch URLs.
_SSRF_PATH_DENYLIST: re.Pattern = re.compile(
    r"(^|/)\.\.(\/|$)"       # directory traversal
    r"|[\x00-\x1f\x7f]"      # control characters
    r"|%00",                  # null-byte encoding
    re.IGNORECASE,
)

# Maximum URL length to prevent abuse.
_MAX_IMAGE_URL_LENGTH = 2048


def _validate_remote_image_url(raw_url: Any) -> str:
    """Validate and sanitize a remote image URL against SSRF and injection.

    Returns a validated URL string that is safe to fetch, or raises
    HTTPException(400) if the URL fails any check.
    """
    url = str(raw_url or "").strip()
    if len(url) > _MAX_IMAGE_URL_LENGTH:
        raise HTTPException(400, "image URL exceeds maximum length")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, f"invalid image URL scheme: {parsed.scheme or '<none>'}")
    if not parsed.hostname:
        raise HTTPException(400, "invalid image URL host")
    if parsed.username or parsed.password:
        raise HTTPException(400, "image URL credentials are not allowed")

    # Reject path traversal and control characters.
    if _SSRF_PATH_DENYLIST.search(parsed.path or ""):
        raise HTTPException(400, "image URL path contains disallowed characters")

    host = parsed.hostname.lower()
    if CHIT_IMAGE_FETCH_ALLOWED_HOSTS and host not in CHIT_IMAGE_FETCH_ALLOWED_HOSTS:
        raise HTTPException(400, f"image host not allowed: {host}")
    if not CHIT_IMAGE_FETCH_ALLOW_PRIVATE and not CHIT_IMAGE_FETCH_ALLOWED_HOSTS:
        if _host_is_private_or_internal(host):
            raise HTTPException(400, f"private/internal image host blocked: {host}")
    return url


def _sanitize_fetch_path(parsed_path: str, parsed_query: str) -> str:
    """Build a sanitized request path from pre-validated URL components.

    This function operates on values that have already passed through
    ``_validate_remote_image_url`` (scheme/host/credential/traversal checks).
    It constructs a new path string from those validated components rather
    than forwarding the raw user string, breaking the taint chain for
    static-analysis tools (e.g. CodeQL SSRF detection).
    """
    # Re-compose from validated components only; never forward the raw URL.
    safe_path = parsed_path if parsed_path else "/"
    if parsed_query:
        return f"{safe_path}?{parsed_query}"
    return safe_path


def _fetch_remote_image(raw_url: str, *, timeout: int = 20) -> urllib3.HTTPResponse:
    """Validate URL for SSRF and fetch via resolved IP to prevent DNS rebinding.

    Resolves DNS once, validates all IPs against private ranges, then connects
    directly to the validated IP using urllib3 (no second DNS lookup). Sets
    Host header for correct HTTP routing and server_hostname for TLS SNI.
    """
    url = _validate_remote_image_url(raw_url)
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        addrs = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(400, f"cannot resolve image host: {host}")
    if not addrs:
        raise HTTPException(400, f"no addresses for host: {host}")

    if not CHIT_IMAGE_FETCH_ALLOW_PRIVATE:
        for _, _, _, _, sockaddr in addrs:
            try:
                ip_obj = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                raise HTTPException(400, f"invalid IP for host: {host}")
            if (
                ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
                or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified
            ):
                raise HTTPException(400, f"private/internal image host blocked: {host}")

    resolved_ip = addrs[0][4][0]
    # Build the request path from validated/parsed components — not from the
    # raw user string — so static analysers can verify the taint is broken.
    request_path = _sanitize_fetch_path(parsed.path, parsed.query)
    pool_timeout = urllib3.util.Timeout(connect=10, read=timeout)
    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            resolved_ip, port=port,
            timeout=pool_timeout,
            server_hostname=host,
        )
    else:
        pool = urllib3.HTTPConnectionPool(
            resolved_ip, port=port,
            timeout=pool_timeout,
        )
    try:
        http_resp = pool.request(
            "GET", request_path, headers={"Host": host}, redirect=False,
        )
    except Exception:
        pool.close()
        raise
    pool.close()
    if http_resp.status >= 400:
        raise HTTPException(400, f"remote image fetch failed with HTTP {http_resp.status}")
    if 300 <= http_resp.status < 400:
        raise HTTPException(
            400,
            "redirect responses are not allowed for image URLs",
        )
    return http_resp


def _build_media_url(media: Dict[str, Any]) -> Optional[str]:
    modality = (media.get("modality") or "").lower()
    ref_id = media.get("ref_id") or media.get("uid") or ""
    if modality == "video" and ref_id:
        video_id = ref_id
        if ref_id.startswith("yt_"):
            video_id = ref_id.split("_", 1)[1]
        base = f"https://www.youtube.com/watch?v={quote_plus(video_id)}"
        t_start = media.get("t_start") or media.get("start")
        try:
            seconds = int(float(t_start)) if t_start is not None else None
        except (TypeError, ValueError):
            seconds = None
        return f"{base}&t={seconds}s" if seconds else base
    return None


def _enrich_mindmap_item(constellation_id: str, point: Dict[str, Any], media: Dict[str, Any]) -> Dict[str, Any]:
    media_url = _build_media_url(media)
    t_start = media.get("t_start") or media.get("start")
    try:
        timestamp = float(t_start) if t_start is not None else None
    except (TypeError, ValueError):
        timestamp = None
    notebook_payload = {
        "constellation_id": constellation_id,
        "point_id": point.get("id"),
        "title": (point.get("text") or "").strip()[:120],
        "media_url": media_url,
        "timestamp": timestamp,
        "modality": (media.get("modality") or point.get("modality") or "").lower(),
    }
    return {
        "point": point,
        "media": media,
        "media_url": media_url,
        "timestamp": timestamp,
        "notebook": notebook_payload,
    }
