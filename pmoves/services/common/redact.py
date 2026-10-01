"""Fail-closed credential redaction for URLs that reach logs or API responses.

Stdlib only, so any service can import it. Services whose image does not ship
``services/common`` carry an inline copy of ``redact_url`` inside an
``except ImportError`` block; ``services/common/tests/test_redact.py`` requires
every copy to be AST-identical to the function below, so edit them together
(``python3 pmoves/tools/sync_redact_url_copies.py`` rewrites the copies).

Rule, anchored on ``@`` rather than on scheme names:

* For each ``@``, if a ``://`` occurs after the previous ``@``, everything from
  the FIRST such ``://`` up to this ``@`` becomes ``***``.
* If no ``://`` occurs since the previous ``@``, the previous mask is extended to
  this ``@`` (several ``@`` inside one password), or, before any mask exists,
  everything from the start of the text up to this ``@`` becomes ``***``.

Taking the first ``://`` (not the nearest) means a password containing ``/ # ?
, @``, whitespace or a ``scheme://``-like run cannot end the userinfo early, and
no scheme-name heuristic can be fooled by text before the scheme. The cost is
over-redaction: a credential-free URL followed by a credentialed one in the same
string, or prose with an ``@`` after a URL (an email address), is masked up to
that ``@``. Leaking is not acceptable; over-masking is.

Query and fragment parameters are masked when the parameter NAME contains
password, passwd, pwd, pass, secret, token, api-key/api_key/apikey, auth,
signature or sig (case-insensitive, so ``sslpassword=``, ``access_token=``,
``X-Api-Key=``, ``#access_token=`` and ``?auth=`` are all masked).

Out of scope: secrets carried in the URL PATH (Discord/Slack webhook URLs, presigned
object paths) are passed through unchanged; do not rely on ``redact_url`` for
those -- log ``bool(url)`` or the host instead.
"""

import re as _re


def redact_url(url):
    if url is None:
        return ""
    text = str(url)
    spans = []
    prev_at = -1
    for match in _re.finditer("@", text):
        at = match.start()
        scheme = text.find("://", prev_at + 1, at)
        if scheme >= 0:
            spans.append([scheme + 3, at])
        elif spans:
            spans[-1][1] = at
        else:
            spans.append([0, at])
        prev_at = at
    out = []
    pos = 0
    for start, end in spans:
        out.append(text[pos:start] + "***")
        pos = end
    out.append(text[pos:])
    return _re.sub(
        r"(?i)([?&;#][\w.\-]*(?:password|passwd|pwd|pass|secret|token|api[_\-]?key|auth|signature|sig)[\w.\-]*=)[^&#;\s]*",
        r"\1***",
        "".join(out),
    )
