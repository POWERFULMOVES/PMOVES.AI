from typing import Dict, Any, Optional


class BaseProvider:
    def extract_text(
        self,
        document: str,
        namespace: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def extract_xml(
        self,
        xml: str,
        namespace: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError
