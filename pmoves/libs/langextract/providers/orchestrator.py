"""
LangExtract Orchestrator Provider

Coordinates between PMOVES-BoTZ MCP tools for document processing:
- Docling: Document conversion (PDF, DOCX, HTML → text/markdown)
- VL Sentinel: Vision-language analysis for images
- E2B: Code execution sandbox for extraction scripts
- Cipher Memory: Persistent memory for reasoning patterns

Connects to PMOVES storage via extract-worker for embeddings.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
import requests

from .base import BaseProvider

logger = logging.getLogger(__name__)


class MCPToolClient:
    """HTTP client for calling MCP tools via the gateway or direct endpoints."""

    def __init__(self):
        self.gateway_url = os.environ.get("MCP_GATEWAY_URL", "http://localhost:2091")
        self.docling_url = os.environ.get("DOCLING_URL", "http://pmz-docling-mcp:3020")
        self.e2b_url = os.environ.get("E2B_URL", "http://pmz-e2b-runner:7071")
        self.vl_sentinel_url = os.environ.get("VL_SENTINEL_URL", "http://pmz-vl-sentinel:7072")
        self.extract_worker_url = os.environ.get("EXTRACT_WORKER_URL", "http://extract-worker:8083")
        self.timeout = int(os.environ.get("MCP_TIMEOUT", "120"))

    def convert_document(
        self,
        input_path: str,
        output_format: str = "markdown",
        ocr: bool = True,
        tables: bool = True,
        images: bool = False,
    ) -> Dict[str, Any]:
        """Convert document using Docling MCP.

        Args:
            input_path: Path or URL to the document
            output_format: Output format (markdown, json, html, text)
            ocr: Enable OCR processing
            tables: Enable table extraction
            images: Export images

        Returns:
            Conversion result with content
        """
        try:
            # Call Docling via SSE endpoint
            response = requests.post(
                f"{self.docling_url}/messages",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "convert_document",
                        "arguments": {
                            "input_path": input_path,
                            "output_format": output_format,
                            "ocr": ocr,
                            "tables": tables,
                            "images": images,
                        }
                    },
                    "id": 1,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Docling conversion failed: {e}")
            return {"error": str(e), "content": None}

    def analyze_image(
        self,
        task: str,
        images: List[Dict[str, str]],
        logs: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze images using VL Sentinel.

        Args:
            task: Task description for the analysis
            images: List of image inputs (url or b64)
            logs: Optional log context
            metrics: Optional metrics context

        Returns:
            Analysis guidance
        """
        try:
            response = requests.post(
                f"{self.vl_sentinel_url}/vl/guide",
                json={
                    "task": task,
                    "images": images,
                    "logs": logs,
                    "metrics": metrics,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"VL Sentinel analysis failed: {e}")
            return {"ok": False, "error": str(e)}

    def run_code(
        self,
        code: str,
        language: str = "python",
        timeout: float = 120.0,
        files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Run code in E2B sandbox.

        Args:
            code: Code to execute
            language: Programming language (python, javascript, bash)
            timeout: Execution timeout
            files: Optional files to upload (path -> base64 content)

        Returns:
            Execution result with stdout/stderr
        """
        try:
            response = requests.post(
                f"{self.e2b_url}/sandbox/run",
                json={
                    "code": code,
                    "language": language,
                    "timeout": timeout,
                    "files": files,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"E2B execution failed: {e}")
            return {"error": str(e), "stdout": "", "stderr": ""}

    def ingest_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Ingest chunks into PMOVES storage via extract-worker.

        Args:
            chunks: List of chunk objects with chunk_id, text, namespace

        Returns:
            Ingestion result
        """
        try:
            response = requests.post(
                f"{self.extract_worker_url}/ingest",
                json={"chunks": chunks},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Extract worker ingestion failed: {e}")
            return {"error": str(e), "ingested": 0}


class OrchestratorProvider(BaseProvider):
    """Orchestrator provider that coordinates MCP tools for document processing."""

    def __init__(self):
        self.mcp = MCPToolClient()
        self.auto_ingest = os.environ.get("ORCHESTRATOR_AUTO_INGEST", "false").lower() == "true"
        self.use_docling = os.environ.get("ORCHESTRATOR_USE_DOCLING", "true").lower() == "true"
        self.use_vl = os.environ.get("ORCHESTRATOR_USE_VL", "false").lower() == "true"

        # Import and initialize inner provider for text chunking
        # Try TensorZero first, fall back to RuleProvider
        self.inner_provider = None

        try:
            from .llm import TensorZeroProvider
            self.inner_provider = TensorZeroProvider()
            logger.info("Orchestrator using TensorZero provider")
        except Exception as e:
            logger.warning(f"TensorZero not available: {e}")

        if self.inner_provider is None:
            try:
                from .rule import RuleProvider
                self.inner_provider = RuleProvider()
                logger.info("Orchestrator using Rule provider")
            except Exception as e:
                logger.error(f"Failed to initialize any provider: {e}")
                raise RuntimeError("No text extraction provider available")

    def _process_with_docling(
        self,
        file_path: str,
        output_format: str = "text",
    ) -> Optional[str]:
        """Process a document file with Docling.

        Returns extracted text or None if processing fails.
        """
        if not self.use_docling:
            return None

        result = self.mcp.convert_document(
            input_path=file_path,
            output_format=output_format,
            ocr=True,
            tables=True,
        )

        if result.get("error"):
            logger.warning(f"Docling processing failed: {result['error']}")
            return None

        # Extract text content from result
        content = result.get("content")
        if isinstance(content, list) and content:
            return content[0].get("text", "")
        return None

    def _analyze_images_with_vl(
        self,
        images: List[Dict[str, str]],
        context: str,
    ) -> Optional[str]:
        """Analyze images using VL Sentinel.

        Returns analysis or None if processing fails.
        """
        if not self.use_vl or not images:
            return None

        result = self.mcp.analyze_image(
            task=f"Extract text and describe content for document processing. Context: {context}",
            images=images,
        )

        if result.get("ok"):
            return result.get("guidance")
        return None

    def extract_text(
        self,
        document: str,
        namespace: str = "pmoves",
        doc_id: str = "doc",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract and chunk text, optionally ingesting to PMOVES storage.

        If the document looks like a file path, it will be processed with Docling first.
        Otherwise, it goes directly to the inner provider for chunking.
        """
        text_to_chunk = document

        # Check if document is a file path
        if document.startswith("/") or document.startswith("http"):
            docling_text = self._process_with_docling(document)
            if docling_text:
                text_to_chunk = docling_text
                logger.info(f"Docling extracted {len(docling_text)} chars from {document}")

        # Chunk with inner provider
        result = self.inner_provider.extract_text(
            text_to_chunk, namespace, doc_id, metadata
        )

        # Auto-ingest if configured
        if self.auto_ingest and result.get("chunks"):
            ingest_result = self.mcp.ingest_chunks(result["chunks"])
            result["ingested"] = ingest_result.get("ingested", 0)
            if ingest_result.get("error"):
                result.setdefault("errors", []).append({
                    "message": f"Ingestion failed: {ingest_result['error']}",
                    "service": "extract-worker",
                })

        return result

    def extract_xml(
        self,
        xml: str,
        namespace: str = "pmoves",
        doc_id: str = "doc",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract and chunk XML content.

        XML is passed directly to the inner provider for chunking.
        """
        result = self.inner_provider.extract_xml(xml, namespace, doc_id, metadata)

        # Auto-ingest if configured
        if self.auto_ingest and result.get("chunks"):
            ingest_result = self.mcp.ingest_chunks(result["chunks"])
            result["ingested"] = ingest_result.get("ingested", 0)
            if ingest_result.get("error"):
                result.setdefault("errors", []).append({
                    "message": f"Ingestion failed: {ingest_result['error']}",
                    "service": "extract-worker",
                })

        return result

    def process_document(
        self,
        file_path: str,
        namespace: str = "pmoves",
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        output_format: str = "text",
    ) -> Dict[str, Any]:
        """Full document processing pipeline.

        1. Convert with Docling (PDF, DOCX, HTML, etc.)
        2. Optionally analyze images with VL Sentinel
        3. Chunk text with inner provider
        4. Optionally ingest to PMOVES storage

        Args:
            file_path: Path to the document file
            namespace: PMOVES namespace for chunks
            doc_id: Document ID (defaults to filename)
            metadata: Additional metadata
            output_format: Docling output format

        Returns:
            Processing result with chunks and any errors
        """
        if doc_id is None:
            doc_id = file_path.split("/")[-1].split(".")[0]

        # Step 1: Convert with Docling
        converted_text = self._process_with_docling(file_path, output_format)
        if not converted_text:
            return {
                "chunks": [],
                "errors": [{"message": f"Document conversion failed for {file_path}"}],
            }

        # Step 2: Chunk text
        result = self.inner_provider.extract_text(
            converted_text, namespace, doc_id, metadata
        )

        # Step 3: Auto-ingest if configured
        if self.auto_ingest and result.get("chunks"):
            ingest_result = self.mcp.ingest_chunks(result["chunks"])
            result["ingested"] = ingest_result.get("ingested", 0)
            if ingest_result.get("error"):
                result.setdefault("errors", []).append({
                    "message": f"Ingestion failed: {ingest_result['error']}",
                    "service": "extract-worker",
                })

        return result
