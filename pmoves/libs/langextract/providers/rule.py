import re
from typing import Dict, Any, List, Tuple

from .base import BaseProvider
from ..chunking import (
    Span,
    iter_paragraphs,
    max_chars_from_env,
    overlap_chars_from_env,
    split_span,
)

ERROR_TAGS = {"error","exception","stacktrace","stack","code","message","service","host","timestamp","time","severity","level"}

# A question segment ends at "?" followed by whitespace (unchanged rule).
_QUESTION_SEP = re.compile(r"(?<=[\?])\s+")


def _question_spans(text: str, start: int, end: int) -> List[Tuple[int, int]]:
    """Offsets of each "?"-terminated segment of ``text[start:end]``.

    Mirrors the original split on ``_QUESTION_SEP`` + ``endswith('?')``
    rule, but keeps absolute offsets so question chunks map back to the source.
    """
    out: List[Tuple[int, int]] = []
    pos = start
    bounds = [(m.start(), m.end()) for m in _QUESTION_SEP.finditer(text, start, end)]
    bounds.append((end, end))
    for seg_end, nxt in bounds:
        s, e = pos, seg_end
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if s < e and text[e - 1] == "?":
            out.append((s, e))
        pos = nxt
    return out


def _chunk(
    doc_id: str,
    namespace: str,
    section: str,
    local_id: str,
    span: Span,
    kind: str,
) -> Dict[str, Any]:
    """Build one chunk dict.

    Keys kept from the original contract: doc_id, section_id, chunk_id,
    namespace, text, kind. Added: parent_section, char_start, char_end,
    chunk_strategy. These map onto CGP point fields (cgp.v2 allows char
    offsets via additionalProperties) with no schema change.
    """
    return {
        'doc_id': doc_id,
        'section_id': section,
        'chunk_id': f"{doc_id}-{section}-{local_id}",
        'namespace': namespace,
        'text': span.text,
        'kind': kind,
        'parent_section': section,
        'char_start': span.start,
        'char_end': span.end,
        'chunk_strategy': span.strategy,
    }


class RuleProvider(BaseProvider):
    """Local, deterministic extractor.

    Chunk ids are hierarchical and stable: ``{doc_id}-sec{N}-p{k}`` for the
    k-th capped sub-chunk of paragraph N and ``{doc_id}-sec{N}-q{j}`` for its
    j-th question. Editing paragraph N never renames chunks of paragraphs 1..N-1
    (the previous ``len(chunks)+1`` counter renumbered everything after the
    first edit). Lengths are capped by ``libs/langextract/chunking.py``
    (``LANGEXTRACT_MAX_CHARS``, default 2000).
    """

    def extract_text(
        self,
        document: str,
        namespace: str,
        doc_id: str,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        doc = document or ""
        mc, ov = max_chars_from_env(), overlap_chars_from_env()
        chunks: List[Dict[str, Any]] = []
        for n, (ps, pe) in enumerate(iter_paragraphs(doc), start=1):
            section = f"sec{n}"
            for k, span in enumerate(split_span(doc, ps, pe, max_chars=mc, overlap_chars=ov), start=1):
                chunks.append(_chunk(doc_id, namespace, section, f"p{k}", span, 'paragraph'))
            j = 0
            for qs, qe in _question_spans(doc, ps, pe):
                pieces = split_span(doc, qs, qe, max_chars=mc, overlap_chars=ov)
                if not pieces:
                    continue
                # An over-cap question segment keeps only its final piece:
                # that is where the question itself is; the lead-in is already
                # covered by the paragraph chunks.
                j += 1
                chunks.append(_chunk(doc_id, namespace, section, f"q{j}", pieces[-1], 'question'))
        return {"chunks": chunks, "errors": []}

    def extract_xml(
        self,
        xml: str,
        namespace: str,
        doc_id: str,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        # Lazy: lxml is only needed here. Importing it at module top made the
        # whole package (and therefore the shared chunker) unimportable in
        # images that never parse XML, e.g. hi-rag-gateway-v2.
        from lxml import etree

        parser = etree.XMLParser(recover=True)
        root = etree.fromstring((xml or '').encode('utf-8'), parser=parser)
        chunks: List[Dict[str,Any]] = []
        errors: List[Dict[str,Any]] = []
        sec_counter = 0
        elem_counter: Dict[str, int] = {}
        mc, ov = max_chars_from_env(), overlap_chars_from_env()

        def next_elem(section: str) -> int:
            elem_counter[section] = elem_counter.get(section, 0) + 1
            return elem_counter[section]

        def _xml_chunk(section: str, local_id: str, span: Span, kind: str) -> Dict[str, Any]:
            c = _chunk(doc_id, namespace, section, local_id, span, kind)
            # XML offsets are relative to the element's stripped text, not the
            # raw XML document.
            c['offset_basis'] = 'element_text'
            return c

        def add_chunks(section: str, eidx: int, text: str, kind: str = 'text'):
            text = (text or '').strip()
            for k, span in enumerate(split_span(text, 0, max_chars=mc, overlap_chars=ov), start=1):
                chunks.append(_xml_chunk(section, f"e{eidx}-p{k}", span, kind))

        def add_question(section: str, eidx: int, j: int, text: str, base: int = 0):
            pieces = split_span(text, 0, max_chars=mc, overlap_chars=ov)
            if not pieces:
                return
            last = pieces[-1]
            span = Span(last.text, base + last.start, base + last.end, last.strategy)
            chunks.append(_xml_chunk(section, f"e{eidx}-q{j}", span, 'question'))

        def maybe_error(el):
            tag = etree.QName(el.tag).localname.lower() if isinstance(el.tag, str) else ''
            if tag in ERROR_TAGS or (el.get('severity') or el.get('level')):
                rec: Dict[str, Any] = {
                    'doc_id': doc_id,
                    'namespace': namespace,
                    'tag': tag or 'error',
                    'message': (el.text or '').strip() or el.get('message') or '',
                    'code': el.get('code') or '',
                    'service': el.get('service') or el.get('component') or '',
                    'host': el.get('host') or '',
                    'severity': el.get('severity') or el.get('level') or '',
                    'timestamp': el.get('timestamp') or el.get('time') or ''
                }
                for child in el:
                    cname = etree.QName(child.tag).localname.lower() if isinstance(child.tag, str) else ''
                    ctext = (child.text or '').strip()
                    if cname in ('stacktrace','stack') and ctext:
                        rec['stack'] = ctext
                    if cname == 'message' and ctext and not rec.get('message'):
                        rec['message'] = ctext
                txt = (el.text or '').strip()
                if txt and not rec.get('message'):
                    m = re.search(r"(ERR|ERROR|EXC|FATAL)[^\n]{0,120}", txt, re.I)
                    if m:
                        rec['message'] = m.group(0)
                errors.append(rec)

        for el in root.iter():
            tag = etree.QName(el.tag).localname.lower() if isinstance(el.tag, str) else ''
            txt = (el.text or '').strip()
            if not txt:
                continue
            maybe_error(el)
            if tag in ('title','h1','h2','h3','header'):
                sec_counter += 1
                section = f"sec{sec_counter}"
                add_chunks(section, next_elem(section), txt, 'title')
            elif tag in ('p','para','paragraph'):
                section = f"sec{sec_counter or 1}"
                eidx = next_elem(section)
                add_chunks(section, eidx, txt, 'paragraph')
                qs = [s.strip() for s in txt.split('?') if s.strip()]
                j = 0
                for q in qs:
                    pos = txt.find(q+'?')
                    if pos != -1:
                        j += 1
                        add_question(section, eidx, j, q+'?', base=pos)
            elif tag in ('q','question'):
                section = f"sec{sec_counter or 1}"
                add_question(section, next_elem(section), 1, txt if txt.endswith('?') else txt+'?')
            else:
                if len(txt) > 40:
                    section = f"sec{sec_counter or 1}"
                    add_chunks(section, next_elem(section), txt, 'text')

        return {"chunks": chunks, "errors": errors}

