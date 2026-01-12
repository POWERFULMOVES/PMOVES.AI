import subprocess
import json
from typing import Any, Dict, List, Optional

def _capture(args: List[str]) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=25)
        return p.stdout if p.returncode == 0 else (p.stderr or p.stdout)
    except Exception as exc:  # pragma: no cover
        return f"<error {type(exc).__name__}: {exc}>"


def extractor_count() -> int:
    try:
        from yt_dlp.extractor import gen_extractor_classes  # type: ignore
        return len(list(gen_extractor_classes()))  # type: ignore
    except Exception:
        out = _capture(["yt-dlp", "--list-extractors"])
        return len([ln for ln in out.splitlines() if ln.strip()])


def version_info() -> Dict[str, Any]:
    ver = "unknown"
    try:
        import yt_dlp  # type: ignore
        ver = getattr(yt_dlp, "__version__", ver)
        if ver == "unknown":
            # Some builds expose version as a module
            try:
                from yt_dlp import version as yv  # type: ignore
                ver = getattr(yv, "__version__", ver)
            except Exception:
                pass
    except Exception:
        pass
    return {"yt_dlp_version": str(ver)}


def options_catalog() -> Dict[str, Any]:
    """Return a lightweight catalog of CLI options parsed from yt_dlp's argparse."""
    try:
        import yt_dlp.options as yopts  # type: ignore
        parser = yopts.create_parser()  # argparse.ArgumentParser
        catalog: List[Dict[str, Any]] = []
        for action in getattr(parser, "_actions", []):
            # Skip positional placeholders
            if not getattr(action, "option_strings", None):
                continue
            opt = {
                "flags": list(action.option_strings),
                "dest": getattr(action, "dest", None),
                "help": getattr(action, "help", None),
                "default": getattr(action, "default", None),
                "nargs": getattr(action, "nargs", None),
                "choices": list(getattr(action, "choices", [])) if getattr(action, "choices", None) else None,
                "type": getattr(getattr(action, "type", None), "__name__", None)
                if getattr(action, "type", None) else None,
            }
            catalog.append(opt)
        return {
            "options": catalog,
            "counts": {"options": len(catalog)},
        }
    except Exception as exc:  # pragma: no cover
        # Fallback to raw --help text only
        txt = _capture(["yt-dlp", "--help"])
        return {"options": [], "counts": {"options": 0}, "help_text": txt}
