"""Charset and shape inspection for a secret at the moment the funnel delivers it.

The funnel has always validated PRESENCE, and for a handful of labels it also
validates LENGTH (``Entry.min_length``). It has never validated CHARSET. Grepping
``secrets_sync.py`` and ``chit_manifest_register.py`` for ``isascii`` returned
zero hits before this module existed.

The measured defect that forced the gap open: ``GATE_API_KEY`` is delivered with
an EM DASH (U+2014) inside the key. Nothing in this pipeline noticed. It is known
only because a third-party vendor CLI inspected the value before putting it in an
HTTP header and said so in plain language -- "contained 1 non-ASCII character
(U+2014) ... stripped so the key can be sent as an HTTP header. This usually
means the key was copy-pasted from a PDF, rich-text editor, or web page that
substituted lookalike Unicode glyphs for ASCII letters." When an outside tool has
better credential hygiene than the pipeline whose entire job is credential
delivery, that is the gap.

This is the ``E2B_API_KEY`` failure recurring, not a novel one. That key arrived
42 characters starting ``b_`` instead of 44 starting ``e2b_`` -- the leading
``e2`` lost somewhere in the funnel. A presence check passed the truncated value,
the E2B Danger Room never ran, and for weeks nobody traced it back to delivery. A
credential that is PRESENT BUT CORRUPT does not fail here; it fails later,
elsewhere, as an opaque auth error in a service nobody is watching.

Two rules this module follows without exception:

  * **It never emits a secret's value, or any span of it.** A finding names the
    VARIABLE, the offending CODEPOINT (as ``U+XXXX NAME``, never the glyph -- the
    glyph would be one character of the secret, and the codepoint already says
    everything an operator needs), the POSITION, and the total LENGTH. Length
    disclosure is already established here: the ``min_length`` warning prints
    "have N chars". Leaking a credential into a log while adding credential
    validation would be worse than the defect being closed.

  * **It never repairs.** The vendor CLI stripped the em dash and carried on; this
    module refuses instead. Stripping is a GUESS at what the value was meant to
    be, and a "repaired" key that is still not the real key produces the same
    opaque 401 while destroying the evidence that anything was ever wrong. A
    funnel that silently edits secrets is worse than one that refuses to ship them.

Proportionality, deliberately: not every non-ASCII character is corruption.

  * A character in ``LOOKALIKE_SUBSTITUTIONS`` is a rich-text substitution for an
    ASCII character a credential can legitimately contain (em dash for hyphen,
    smart quote for straight quote, non-breaking space for space) or is outright
    INVISIBLE (zero-width space, BOM). These are never chosen on purpose and
    several cannot be seen at all, so they can never be ruled out by eye.
    Verdict: WITHHOLD.
  * Any other non-ASCII character -- a letter with a diacritic, say -- may be a
    deliberate part of a human-chosen PASSWORD, and several registered labels are
    passwords (``DASHBOARD_PASSWORD``, ``AP_POSTGRES_PASSWORD``, ``SMTP_PASS``,
    ``JUICEFS_META_PASSWORD``). Withholding those would break a node that works
    today, so the verdict is WARN: named and visible, but still delivered.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List

# Codepoint -> the ASCII character it was almost certainly substituted FOR.
# An empty string means the character is invisible and stands for nothing at all.
#
# The table is a security surface, so it is written out rather than derived from a
# Unicode category: ``unicodedata.category`` would sweep in every dash, quote and
# space in Unicode including ones no editor ever autocorrects, and the point is to
# name the observed copy-paste failure class, not to ban a category.
LOOKALIKE_SUBSTITUTIONS: Dict[str, str] = {
    # Dashes autocorrected in place of ASCII hyphen-minus. U+2014 is the one
    # actually observed in GATE_API_KEY.
    "\u2010": "-",  # HYPHEN
    "\u2011": "-",  # NON-BREAKING HYPHEN
    "\u2012": "-",  # FIGURE DASH
    "\u2013": "-",  # EN DASH
    "\u2014": "-",  # EM DASH  <- the measured defect
    "\u2015": "-",  # HORIZONTAL BAR
    "\u2212": "-",  # MINUS SIGN
    "\uff0d": "-",  # FULLWIDTH HYPHEN-MINUS
    # "Smart quotes". Straight quotes do occur in human-chosen passwords, so the
    # curly forms are substitutions rather than plausible originals.
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK
    "\u201a": "'",  # SINGLE LOW-9 QUOTATION MARK
    "\u201b": "'",  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
    "\u2032": "'",  # PRIME
    "\u201c": '"',  # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',  # RIGHT DOUBLE QUOTATION MARK
    "\u201e": '"',  # DOUBLE LOW-9 QUOTATION MARK
    "\u201f": '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    "\u2033": '"',  # DOUBLE PRIME
    # Non-ASCII spaces. A non-breaking space is the classic artifact of copying a
    # key out of rendered HTML, and it is indistinguishable from a space.
    "\u00a0": " ",  # NO-BREAK SPACE
    "\u2002": " ",  # EN SPACE
    "\u2003": " ",  # EM SPACE
    "\u2004": " ",  # THREE-PER-EM SPACE
    "\u2005": " ",  # FOUR-PER-EM SPACE
    "\u2006": " ",  # SIX-PER-EM SPACE
    "\u2007": " ",  # FIGURE SPACE
    "\u2008": " ",  # PUNCTUATION SPACE
    "\u2009": " ",  # THIN SPACE
    "\u200a": " ",  # HAIR SPACE
    "\u202f": " ",  # NARROW NO-BREAK SPACE
    "\u205f": " ",  # MEDIUM MATHEMATICAL SPACE
    "\u3000": " ",  # IDEOGRAPHIC SPACE
    # Invisible, standing for nothing. These are the worst of the family: an
    # operator comparing the delivered value against the vendor's console by eye
    # sees two identical strings.
    "\u00ad": "",  # SOFT HYPHEN
    "\u200b": "",  # ZERO WIDTH SPACE
    "\u200c": "",  # ZERO WIDTH NON-JOINER
    "\u200d": "",  # ZERO WIDTH JOINER
    "\u2060": "",  # WORD JOINER
    "\ufeff": "",  # ZERO WIDTH NO-BREAK SPACE / BOM
    # An ellipsis where three dots were typed -- and also the signature of a value
    # copied from a UI that ELIDED the middle of the key, in which case the value
    # is truncated as well as mis-charactered.
    "\u2026": "...",  # HORIZONTAL ELLIPSIS
}


@dataclass(frozen=True)
class ShapeVerdict:
    """Findings for one value. Both lists hold value-free, printable strings.

    Callers MUST branch on ``verdict.withhold`` explicitly and never on the
    verdict object. A dataclass instance is always truthy, so ``if verdict:``
    would read as "there is a problem" while being unconditionally true -- the
    same trap that would have silently disabled every CHIT signature check had
    ``verify_cgp``'s bool return been widened to a dataclass.
    """

    withhold: List[str] = field(default_factory=list)
    warn: List[str] = field(default_factory=list)


def describe_codepoint(ch: str) -> str:
    """``U+2014 EM DASH``. Never the glyph itself -- that is secret material."""
    try:
        return f"U+{ord(ch):04X} {unicodedata.name(ch)}"
    except ValueError:
        # Control characters and unassigned codepoints have no Unicode name.
        return f"U+{ord(ch):04X} (unnamed)"


def _substitution_note(ascii_equivalent: str) -> str:
    if ascii_equivalent == "":
        return "an INVISIBLE character standing for nothing"
    if ascii_equivalent == " ":
        return "a rich-text substitution for an ASCII space"
    return f"a rich-text substitution for ASCII {ascii_equivalent!r}"


def inspect_value(label: str, value: str, *, prefix: str = "") -> ShapeVerdict:
    """Inspect one delivered secret. Returns findings; emits nothing itself.

    ``prefix`` is the registered vendor prefix, when the label declares one. A
    mismatch is unambiguous -- the registry author opted in by naming a prefix the
    vendor guarantees -- so it withholds. The prefix is public (``e2b_``), not
    secret, and is safe to name in the finding.
    """
    withhold: List[str] = []
    warn: List[str] = []
    total = len(value)

    for position, ch in enumerate(value, start=1):
        if ch.isascii():
            continue
        where = f"{label}: {describe_codepoint(ch)} at position {position} of {total}"
        ascii_equivalent = LOOKALIKE_SUBSTITUTIONS.get(ch)
        if ascii_equivalent is None:
            warn.append(f"{where} -- non-ASCII, cannot be sent as an HTTP header")
        else:
            withhold.append(f"{where} -- {_substitution_note(ascii_equivalent)}")

    if prefix and not value.startswith(prefix):
        withhold.append(
            f"{label}: does not start with the registered prefix {prefix!r} "
            f"(value is {total} chars) -- this is the shape that would have caught "
            "the 42-character 'b_' E2B key at delivery"
        )

    # Surrounding whitespace is the same family one rung over: present, non-empty
    # and wrong. ``_first_usable`` only STRIPS to decide emptiness -- it emits the
    # unstripped value -- so `KEY=abc ` reaches a bearer header with the space
    # attached and 401s. WARN rather than withhold: a password may legitimately end
    # in a space, and unlike the lookalikes this one is visible in a hexdump.
    if value != value.strip():
        warn.append(
            f"{label}: {total - len(value.lstrip())} leading / "
            f"{total - len(value.rstrip())} trailing whitespace character(s) "
            f"(value is {total} chars) -- the funnel emits the UNSTRIPPED value"
        )

    return ShapeVerdict(withhold=withhold, warn=warn)
