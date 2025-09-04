from typing import Dict, Any

class BaseProvider:
    def extract_text(self, document: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def extract_xml(self, xml: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        raise NotImplementedError

