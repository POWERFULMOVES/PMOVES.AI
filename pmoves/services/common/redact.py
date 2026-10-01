"""Fail-closed credential redaction for URLs that reach logs or API responses.

Stdlib only, so any service can import it. Services whose image does not ship
``services/common`` carry an inline copy of ``redact_url`` inside an
``except ImportError`` block; ``tests/test_redact_url_copies.py`` requires every
copy to be AST-identical to the function below, so edit them together
(``python3 pmoves/tools/sync_redact_url_copies.py`` rewrites the copies).

Rule: for every ``scheme://`` in the text, everything between the scheme and the
LAST ``@`` before the next scheme becomes ``***``. With no scheme at all,
everything before the last ``@`` becomes ``***``. The last ``@`` (not the first,
and not whatever ``urllib.parse.urlsplit`` decides the netloc is) is what keeps
unencoded ``/ # ? , @`` and whitespace in a password from ending the authority
early and leaking the remainder. A path containing ``@`` is over-redacted; that is
the accepted cost. Query parameters named like a secret are masked too.
"""

import re as _re


def redact_url(url):
    if url is None:
        return ""
    text = str(url)
    schemes = list(_re.finditer(r"(?<![A-Za-z0-9+.\-:/@%])[A-Za-z][A-Za-z0-9+.\-]*://", text))
    if not schemes:
        at = text.rfind("@")
        out = "***" + text[at:] if at >= 0 else text
    else:
        out = text[: schemes[0].start()]
        for i, m in enumerate(schemes):
            end = schemes[i + 1].start() if i + 1 < len(schemes) else len(text)
            seg = text[m.end():end]
            at = seg.rfind("@")
            out += m.group(0) + ("***" + seg[at:] if at >= 0 else seg)
    return _re.sub(
        r"(?i)([?&;](?:password|passwd|pass|pwd|secret|token|api_?key|access_token)=)[^&#\s]*",
        r"\1***",
        out,
    )
