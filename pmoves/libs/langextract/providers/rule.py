import re
from typing import Dict, Any, List
from lxml import etree

from .base import BaseProvider

ERROR_TAGS = {"error","exception","stacktrace","stack","code","message","service","host","timestamp","time","severity","level"}

class RuleProvider(BaseProvider):
    def extract_text(
        self,
        document: str,
        namespace: str,
        doc_id: str,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        chunks: List[Dict[str, Any]] = []
        # split paragraphs by blank lines
        paras = re.split(r"\n\s*\n+", document or "")
        sec = 0
        for para in paras:
            p = para.strip()
            if not p:
                continue
            sec += 1
            section = f"sec{sec}"
            chunks.append({
                'doc_id': doc_id,
                'section_id': section,
                'chunk_id': f"{doc_id}-{section}-{len(chunks)+1}",
                'namespace': namespace,
                'text': p,
                'kind': 'paragraph'
            })
            # extract questions
            sentences = re.split(r"(?<=[\?])\s+", p)
            for s in sentences:
                st = s.strip()
                if st.endswith('?'):
                    chunks.append({
                        'doc_id': doc_id,
                        'section_id': section,
                        'chunk_id': f"{doc_id}-{section}-{len(chunks)+1}",
                        'namespace': namespace,
                        'text': st,
                        'kind': 'question'
                    })
        return {"chunks": chunks, "errors": []}

    def extract_xml(
        self,
        xml: str,
        namespace: str,
        doc_id: str,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring((xml or '').encode('utf-8'), parser=parser)
        chunks: List[Dict[str,Any]] = []
        errors: List[Dict[str,Any]] = []
        sec_counter = 0

        def add_chunk(section: str, text: str, kind: str = 'text'):
            chunks.append({
                'doc_id': doc_id,
                'section_id': section,
                'chunk_id': f"{doc_id}-{section}-{len(chunks)+1}",
                'namespace': namespace,
                'text': (text or '').strip(),
                'kind': kind
            })

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
                add_chunk(f"sec{sec_counter}", txt, 'title')
            elif tag in ('p','para','paragraph'):
                add_chunk(f"sec{sec_counter or 1}", txt, 'paragraph')
                qs = [s.strip() for s in txt.split('?') if s.strip()]
                for q in qs:
                    if txt.find(q+'?') != -1:
                        add_chunk(f"sec{sec_counter or 1}", q+'?', 'question')
            elif tag in ('q','question'):
                add_chunk(f"sec{sec_counter or 1}", txt if txt.endswith('?') else txt+'?', 'question')
            else:
                if len(txt) > 40:
                    add_chunk(f"sec{sec_counter or 1}", txt, 'text')

        return {"chunks": chunks, "errors": errors}

