import sys, json
from lxml import etree

def extract_xml(xml_text: str, namespace: str = 'pmoves', doc_id: str = 'doc'):
    parser = etree.XMLParser(recover=True)
    root = etree.fromstring(xml_text.encode('utf-8'), parser=parser)
    chunks = []
    sec_counter = 0
    def add(section, text, kind='text'):
        chunks.append({
            'doc_id': doc_id,
            'section_id': section,
            'chunk_id': f"{doc_id}-{section}-{len(chunks)+1}",
            'namespace': namespace,
            'text': text.strip(),
            'kind': kind
        })
    for el in root.iter():
        tag = etree.QName(el.tag).localname.lower() if isinstance(el.tag, str) else ''
        txt = (el.text or '').strip()
        if not txt:
            continue
        if tag in ('title','h1','h2','h3','header'):
            sec_counter += 1
            add(f"sec{sec_counter}", txt, 'title')
        elif tag in ('p','para','paragraph'):
            add(f"sec{sec_counter or 1}", txt, 'paragraph')
            qs = [s.strip() for s in txt.split('?') if s.strip()]
            for q in qs:
                if txt.find(q+'?') != -1:
                    add(f"sec{sec_counter or 1}", q+'?', 'question')
        elif tag in ('q','question'):
            add(f"sec{sec_counter or 1}", txt if txt.endswith('?') else txt+'?', 'question')
        else:
            if len(txt) > 40:
                add(f"sec{sec_counter or 1}", txt, 'text')
    return chunks

def main():
    if len(sys.argv) < 3:
        print('Usage: xml_to_jsonl.py /path/input.xml /path/output.jsonl [namespace] [doc_id]')
        sys.exit(2)
    in_path, out_path = sys.argv[1], sys.argv[2]
    ns = sys.argv[3] if len(sys.argv) > 3 else 'pmoves'
    doc_id = sys.argv[4] if len(sys.argv) > 4 else 'doc'
    xml = open(in_path, 'r', encoding='utf-8').read()
    chunks = extract_xml(xml, ns, doc_id)
    with open(out_path, 'w', encoding='utf-8') as w:
        for c in chunks:
            w.write(json.dumps(c, ensure_ascii=False) + '\n')
    print(f'Wrote {len(chunks)} chunks to {out_path}')

if __name__ == '__main__':
    main()

