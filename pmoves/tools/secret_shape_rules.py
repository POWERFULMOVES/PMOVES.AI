"""Per-label secret shape rules, as pydantic models over a tracked rules file.

Until this module the funnel's shape constraints were hand-rolled: an ``Entry``
dataclass carrying ``min_length``/``prefix``, ``isinstance`` checks at manifest
load, and an ``if len(value) < min_length`` at delivery. Worse, the per-label
values lived only in the secrets manifest, which is zero-access by design -- so
nobody could confirm that the provider keys about to be rotated had any rule at
all. ``chit_manifest_register.REGISTRY`` registers ``HF_TOKEN`` with no shape,
and registers none of the other rotated provider labels.

So the rules move to ``pmoves/config/secret_shapes.yaml``: tracked, reviewable,
holding RULES ONLY -- never a value. ``ShapeRuleSet`` validates that file at
load time and a malformed file raises ``RulesFileError``, which every CLI entry
point maps to exit 3 (could not measure). A funnel that cannot read its rules
cannot say whether a delivered key is well-formed, and must not pretend to.

The guarantees ``secret_shape`` already makes hold here too:

  * A finding never carries the value or any span of it: label, expected shape
    (the public prefix, lengths, charset pattern), observed LENGTH, whether the
    prefix matched, and the POSITION of the first out-of-charset character.
  * ``check`` returns a list. Branch on its truthiness, which is honest for a
    list; there is no verdict object here to be always-truthy.
"""

from __future__ import annotations

import argparse
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, List, Literal, Optional, Sequence, Tuple

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES_PATH = REPO_ROOT / "pmoves" / "config" / "secret_shapes.yaml"

# Exit doctrine shared with the rest of pmoves/tools: 0 clean / 1 findings /
# 3 could-not-measure.
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_UNMEASURED = 3

# An env-var name. Upper case by convention, but the funnel does not enforce
# that, so neither does the model.
LABEL_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


# A charset must be ONE character class repeated over the whole value:
# ``^[...]+$``. That is the only form for which "first character outside the
# class" is well defined, so it is the only form the model admits.
_CHARSET_FORM = re.compile(r"^\^\[(?:[^\]\\]|\\.)+\]\+\$$")


class RulesFileError(Exception):
    """The rules file is absent, unparseable, or fails the model. Exit 3."""


def prefix_matches(value: str, prefixes: Sequence[str]) -> bool:
    """The one definition of "starts with a registered prefix" in the funnel."""
    return not prefixes or any(value.startswith(p) for p in prefixes)


class ShapeRule(BaseModel):
    """The documented shape of one credential label.

    ``length_source`` exists so a reviewer can see where every number came from
    without leaving the file:

      * ``documented`` -- the provider's docs state the length, or state the
        components it is built from.
      * ``example`` -- the length of the provider's own published example. Used
        only as a FLOOR (``min_length``); an example is not a specification.
      * ``floor`` -- a conservative lower bound chosen here, not by the
        provider. Catches gross truncation and nothing finer.
      * ``none`` -- no length constraint.

    An ``exact_length`` is accepted only with ``length_source: documented``.
    Inventing an exact length for a provider that never promised one would
    withhold a valid key the day the provider lengthens its format.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(pattern=LABEL_PATTERN)
    prefixes: Tuple[StrictStr, ...] = ()
    min_length: StrictInt = Field(default=0, ge=0)
    max_length: Optional[StrictInt] = Field(default=None, ge=1)
    exact_length: Optional[StrictInt] = Field(default=None, ge=1)
    charset: Optional[StrictStr] = None
    length_source: Literal["documented", "example", "floor", "none"] = "none"
    docs: Tuple[StrictStr, ...] = ()

    @field_validator("prefixes")
    @classmethod
    def _prefixes_are_printable_ascii(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        for prefix in value:
            if not prefix or not prefix.isascii() or not prefix.isprintable():
                raise ValueError(f"prefix {prefix!r} must be non-empty printable ASCII")
        return value

    @field_validator("charset")
    @classmethod
    def _charset_compiles(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not _CHARSET_FORM.match(value):
            raise ValueError(
                f"charset {value!r} must have the form ^[...]+$ -- one character "
                "class over the whole value, so a mismatch has a position"
            )
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"charset is not a valid regex: {exc}") from None
        return value

    @field_validator("docs")
    @classmethod
    def _docs_are_https(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        for url in value:
            if not url.startswith("https://"):
                raise ValueError(f"docs entry {url!r} must be an https:// URL")
        return value

    @model_validator(mode="after")
    def _lengths_are_coherent(self) -> "ShapeRule":
        if self.exact_length is not None:
            if self.min_length or self.max_length is not None:
                raise ValueError("exact_length excludes min_length/max_length")
            if self.length_source != "documented":
                raise ValueError(
                    "exact_length requires length_source: documented -- do not "
                    "invent an exact length the provider never published"
                )
        if self.max_length is not None and self.min_length > self.max_length:
            raise ValueError("min_length exceeds max_length")
        constrained = bool(self.min_length or self.max_length or self.exact_length)
        if constrained and self.length_source == "none":
            raise ValueError("a length constraint needs a length_source")
        if not constrained and self.length_source != "none":
            raise ValueError(f"length_source {self.length_source!r} with no length constraint")
        return self

    def expected(self) -> str:
        """Human description of the shape. Public facts only."""
        parts: List[str] = []
        if self.prefixes:
            parts.append("prefix " + " or ".join(repr(p) for p in self.prefixes))
        if self.exact_length is not None:
            parts.append(f"exactly {self.exact_length} chars ({self.length_source})")
        else:
            if self.min_length:
                parts.append(f">= {self.min_length} chars ({self.length_source})")
            if self.max_length is not None:
                parts.append(f"<= {self.max_length} chars ({self.length_source})")
        if self.charset:
            parts.append(f"charset {self.charset}")
        return "; ".join(parts) or "unconstrained"

    def violations(self, value: str) -> FrozenSet[str]:
        """Which constraint families fail: a subset of {prefix, length, charset}."""
        total = len(value)
        failed = set()
        if not prefix_matches(value, self.prefixes):
            failed.add("prefix")
        if (
            (self.exact_length is not None and total != self.exact_length)
            or total < self.min_length
            or (self.max_length is not None and total > self.max_length)
        ):
            failed.add("length")
        if self.charset and not re.fullmatch(self.charset, value):
            failed.add("charset")
        return frozenset(failed)

    def check(self, value: str) -> List[str]:
        """Return value-free findings; an empty list means the value conforms."""
        failed = self.violations(value)
        if not failed:
            return []
        observed = [
            f"observed {len(value)} chars",
            "prefix-match " + ("no" if "prefix" in failed else "yes"),
        ]
        if self.charset:
            if "charset" in failed:
                # Position only. The character itself would be one character of
                # the secret; a lookalike glyph is already named by codepoint in
                # secret_shape.inspect_value, which runs first.
                # Well defined because the model admits only ^[class]+$: test
                # each character against the bare class.
                char_class = re.compile(self.charset[1:-2])
                first_bad = next(
                    (pos for pos, ch in enumerate(value, start=1)
                     if not char_class.fullmatch(ch)),
                    None,
                )
                where = f" (first mismatch at position {first_bad})" if first_bad else ""
                observed.append("charset-match no" + where)
            else:
                observed.append("charset-match yes")
        return [f"{self.label}: expected {self.expected()}; " + ", ".join(observed)]


class ShapeRuleSet(BaseModel):
    """The whole rules file. Labels are unique; unknown keys are refused."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    rules: Tuple[ShapeRule, ...]

    @model_validator(mode="after")
    def _labels_unique(self) -> "ShapeRuleSet":
        seen: Dict[str, int] = {}
        for rule in self.rules:
            seen[rule.label] = seen.get(rule.label, 0) + 1
        dupes = sorted(label for label, count in seen.items() if count > 1)
        if dupes:
            raise ValueError(f"duplicate rule labels: {', '.join(dupes)}")
        return self

    def by_label(self) -> Dict[str, ShapeRule]:
        return {rule.label: rule for rule in self.rules}


class ManifestShape(BaseModel):
    """The typed fields of one secrets-manifest entry.

    Strict types throughout. ``min_length: true`` is a bool, not an int, and
    ``required: "false"`` is a STRING -- which ``bool()`` turns into True, so a
    hand-rolled ``bool(item.get("required", True))`` silently made a quoted
    "false" mandatory. YAML makes both easy to write by accident.

    ``label`` must be an env-var name. Every rule built from this entry carries
    it, and a label the model refuses must be refused HERE, at manifest load,
    with a message -- not deep inside ``build_outputs`` as a traceback.
    """

    model_config = ConfigDict(extra="ignore")

    label: str = Field(default="_", pattern=LABEL_PATTERN)
    required: StrictBool = True
    min_length: StrictInt = Field(default=0, ge=0)
    prefix: StrictStr = ""

    def as_rule(self, label: str) -> Optional[ShapeRule]:
        if not self.min_length and not self.prefix:
            return None
        return ShapeRule(
            label=label,
            prefixes=(self.prefix,) if self.prefix else (),
            min_length=self.min_length,
            length_source="floor" if self.min_length else "none",
        )


def format_validation_error(exc: ValidationError) -> List[str]:
    return [
        f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
        for err in exc.errors()
    ]


def parse_rules(text: str, *, source: str = "<rules>") -> ShapeRuleSet:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesFileError(f"{source}: not valid YAML ({exc.__class__.__name__})") from None
    try:
        return ShapeRuleSet.model_validate(data)
    except ValidationError as exc:
        raise RulesFileError(
            f"{source}: rules file fails the model:\n  "
            + "\n  ".join(format_validation_error(exc))
        ) from None


def load_rules(path: Path | str = DEFAULT_RULES_PATH) -> Dict[str, ShapeRule]:
    """Load and validate a rules file. Raises ``RulesFileError`` on any problem."""
    return dict(_load_rules_cached(str(Path(path).resolve())))


@lru_cache(maxsize=8)
def _load_rules_cached(resolved: str) -> Dict[str, ShapeRule]:
    path = Path(resolved)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RulesFileError(f"{path}: cannot read rules file ({exc.__class__.__name__})") from None
    return parse_rules(text, source=str(path)).by_label()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the secret shape rules file.")
    parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH))
    args = parser.parse_args(argv)
    try:
        rules = load_rules(args.rules)
    except RulesFileError as exc:
        print(f"secret-shapes: COULD-NOT-MEASURE -- {exc}", file=sys.stderr)
        return EXIT_UNMEASURED
    for label in sorted(rules):
        print(f"{label}: {rules[label].expected()}")
    print(f"secret-shapes: {len(rules)} rule(s) valid")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
