from typing import Dict, Any

class BaseProvider:
    """Abstract base class for content extraction providers."""

    def extract_text(self, document: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        """Extracts content from a plain text document.

        Args:
            document: The text content of the document.
            namespace: The namespace of the document.
            doc_id: The unique identifier of the document.

        Raises:
            NotImplementedError: This method must be implemented by a subclass.
        """
        raise NotImplementedError

    def extract_xml(self, xml: str, namespace: str, doc_id: str) -> Dict[str, Any]:
        """Extracts content from an XML document.

        Args:
            xml: The XML content of the document.
            namespace: The namespace of the document.
            doc_id: The unique identifier of the document.

        Raises:
            NotImplementedError: This method must be implemented by a subclass.
        """
        raise NotImplementedError

