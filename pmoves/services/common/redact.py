"""Fail-closed credential redaction for URLs that reach logs or API responses.

Stdlib only, so any service can import it. Services whose image does not ship
``services/common`` carry an inline copy of ``redact_url`` inside an
``except ImportError`` block; ``services/common/tests/test_redact.py`` requires
every copy to be AST-identical to the function below, so edit them together
(``python3 pmoves/tools/sync_redact_url_copies.py`` rewrites the copies).

Rule, anchored on ``@`` rather than on scheme names:

* For each ``@``, if a ``://`` occurs after the previous ``@``, everything from
  the FIRST such ``://`` up to this ``@`` becomes ``***``.
* If no ``://`` occurs since the previous ``@`` -- or one does, but the text
  between that ``@`` and the ``://`` has no separator (whitespace , ; quotes
  brackets), so it cannot be the start of a second URL -- the previous mask is
  extended to this ``@`` (several ``@``, or an ``@...://`` run, inside one
  password). Before any mask exists, everything from the start of the text up
  to this ``@`` becomes ``***``.

Taking the first ``://`` (not the nearest) means a password containing ``/ # ?
, @``, whitespace or a ``scheme://``-like run cannot end the userinfo early, and
no scheme-name heuristic can be fooled by text before the scheme. The cost is
over-redaction: a credential-free URL followed by a credentialed one in the same
string, or prose with an ``@`` after a URL (an email address), is masked up to
that ``@``. Leaking is not acceptable; over-masking is.

Query and fragment parameters are masked when the parameter NAME contains
password, passwd, pwd, pass, secret, token, key, auth, signature or sig
(case-insensitive, so ``sslpassword=``, ``access_token=``, ``X-Api-Key=``,
``#access_token=``, ``?auth=`` and the bare Google/YouTube ``?key=`` are all
masked; so is an unrelated ``?monkey=`` -- over-masking again).

Do NOT wire this into a ``logging.Filter`` or apply it to free text. It is for
values known to be URLs: in prose, any ``@`` (an email address) masks
everything before it (``user ops@example.com`` -> ``***@example.com``),
destroying log context.

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
        if scheme >= 0 and (not spans or _re.search(r"[\s,;'\"()<>|\[\]{}]", text[prev_at + 1:scheme])):
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
        r"(?i)([?&;#][\w.\-]*(?:password|passwd|pwd|pass|secret|token|key|auth|signature|sig)[\w.\-]*=)[^&#;\s]*",
        r"\1***",
        "".join(out),
    )
