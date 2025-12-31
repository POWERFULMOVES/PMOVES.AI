#!/usr/bin/env python3
"""
PMOVES • Consciousness Taxonomy Harvester (Archon-based)

Replaces the Selenium-based harvester with NATS event-driven crawling via Archon.
Uses Crawl4AI + Playwright through the Archon service for distributed web harvesting.

Architecture:
    consciousness_harvester.py
        ↓
    NATS: archon.crawl.request.v1
        ↓
    Archon (port 8091) → Crawl4AI + Playwright
        ↓
    NATS: archon.crawl.result.v1
        ↓
    Process markdown/HTML → Extract taxonomy
        ↓
    Store in Supabase + Neo4j + Hi-RAG

Usage:
    python tools/consciousness_harvester.py --url "https://example.com/theories" --output pmoves/data/consciousness/
    python tools/consciousness_harvester.py --urls-file urls.txt --output pmoves/data/consciousness/

Prerequisites:
    - Archon service running (port 8091)
    - NATS message bus running
    - Optional: Hi-RAG v2 for geometry publishing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    import nats
    from nats.aio.client import Client as NATS
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    nats = None
    NATS = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
ARCHON_URL = os.environ.get("ARCHON_URL", "http://localhost:8091")
NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
HIRAG_V2_URL = os.environ.get("HIRAG_V2_URL", "http://localhost:8086")

# NATS subjects
CRAWL_REQUEST_SUBJECT = "archon.crawl.request.v1"
CRAWL_RESULT_SUBJECT = "archon.crawl.result.v1"


@dataclass
class CrawlResult:
    """Result from Archon crawl operation."""

    url: str
    success: bool
    markdown: str = ""
    html: str = ""
    links: List[Dict[str, str]] = field(default_factory=list)
    title: str = ""
    error: Optional[str] = None
    crawled_at: str = ""


@dataclass
class TheoryEntry:
    """Extracted theory from crawled content."""

    name: str
    category: str
    subcategory: str = ""
    description: str = ""
    proponents: List[str] = field(default_factory=list)
    source_url: str = ""
    extracted_at: str = ""


class ConsciousnessHarvester:
    """
    Harvest consciousness taxonomy using Archon's Crawl4AI integration.

    Replaces Selenium-based harvesting with distributed, event-driven crawling.
    """

    def __init__(self, use_nats: bool = True):
        """
        Initialize the harvester.

        Args:
            use_nats: If True, use NATS messaging. If False, use HTTP API directly.
        """
        self.use_nats = use_nats and NATS_AVAILABLE
        self.nc: Optional[NATS] = None
        self.http_client = httpx.AsyncClient(timeout=120.0)
        self.pending_results: Dict[str, asyncio.Future] = {}
        logger.info(f"ConsciousnessHarvester initialized (NATS: {self.use_nats})")

    async def connect(self):
        """Connect to NATS message bus."""
        if not self.use_nats:
            return

        self.nc = await nats.connect(NATS_URL)
        await self.nc.subscribe(CRAWL_RESULT_SUBJECT, cb=self._handle_crawl_result)
        logger.info(f"Connected to NATS at {NATS_URL}")

    async def close(self):
        """Close connections."""
        await self.http_client.aclose()
        if self.nc:
            await self.nc.drain()
            logger.info("NATS connection closed")

    async def _handle_crawl_result(self, msg):
        """Handle incoming crawl results from Archon."""
        try:
            data = json.loads(msg.data.decode())
            request_id = data.get("request_id")

            if request_id in self.pending_results:
                result = CrawlResult(
                    url=data.get("url", ""),
                    success=data.get("success", False),
                    markdown=data.get("markdown", ""),
                    html=data.get("html", ""),
                    links=data.get("links", []),
                    title=data.get("title", ""),
                    error=data.get("error"),
                    crawled_at=data.get("crawled_at", datetime.now(timezone.utc).isoformat() + "Z"),
                )
                self.pending_results[request_id].set_result(result)
                logger.debug(f"Received crawl result for {request_id}")

        except Exception as e:
            logger.error(f"Error handling crawl result: {e}")

    async def crawl_url_nats(self, url: str, timeout: float = 60.0) -> CrawlResult:
        """
        Request a crawl via NATS messaging.

        Args:
            url: URL to crawl
            timeout: Timeout in seconds

        Returns:
            CrawlResult with markdown/HTML content
        """
        request_id = str(uuid.uuid4())
        request = {
            "request_id": request_id,
            "url": url,
            "options": {
                "extract_markdown": True,
                "extract_links": True,
                "wait_for_selector": "body",
            },
        }

        future = asyncio.get_event_loop().create_future()
        self.pending_results[request_id] = future

        try:
            await self.nc.publish(CRAWL_REQUEST_SUBJECT, json.dumps(request).encode())
            logger.info(f"Sent crawl request for {url} (id: {request_id})")

            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            logger.error(f"Crawl timeout for {url}")
            return CrawlResult(url=url, success=False, error="Timeout")

        finally:
            self.pending_results.pop(request_id, None)

    async def crawl_url_http(self, url: str) -> CrawlResult:
        """
        Request a crawl via HTTP API directly.

        Args:
            url: URL to crawl

        Returns:
            CrawlResult with markdown/HTML content
        """
        try:
            response = await self.http_client.post(
                f"{ARCHON_URL}/archon/crawl",
                json={
                    "url": url,
                    "options": {
                        "extract_markdown": True,
                        "extract_links": True,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

            return CrawlResult(
                url=url,
                success=True,
                markdown=data.get("markdown", ""),
                html=data.get("html", ""),
                links=data.get("links", []),
                title=data.get("title", ""),
                crawled_at=datetime.now(timezone.utc).isoformat() + "Z",
            )

        except httpx.HTTPError as e:
            logger.error(f"HTTP crawl failed for {url}: {e}")
            return CrawlResult(url=url, success=False, error=str(e))

    async def crawl_url(self, url: str) -> CrawlResult:
        """
        Crawl a URL using the configured method (NATS or HTTP).

        Args:
            url: URL to crawl

        Returns:
            CrawlResult with extracted content
        """
        if self.use_nats and self.nc:
            return await self.crawl_url_nats(url)
        else:
            return await self.crawl_url_http(url)

    def extract_theories(self, result: CrawlResult) -> List[TheoryEntry]:
        """
        Extract theory entries from crawled content.

        Uses heuristics to identify theory names, descriptions, and proponents
        from markdown/HTML content.

        Args:
            result: CrawlResult with markdown content

        Returns:
            List of extracted TheoryEntry objects
        """
        theories: List[TheoryEntry] = []
        content = result.markdown or result.html

        if not content:
            return theories

        # Extract category from URL or title
        category = self._infer_category(result.url, result.title)

        # Pattern: "## Theory Name" or "### Theory Name"
        heading_pattern = r"#{2,3}\s+(.+?)(?:\n|$)"
        headings = re.findall(heading_pattern, content)

        for heading in headings:
            theory_name = heading.strip()

            # Skip navigation/meta headings
            if self._is_meta_heading(theory_name):
                continue

            # Extract description (text after heading until next heading)
            desc_pattern = rf"#{2,3}\s+{re.escape(theory_name)}\s*\n([\s\S]*?)(?=\n#{2,3}\s|\Z)"
            desc_match = re.search(desc_pattern, content)
            description = ""
            if desc_match:
                description = desc_match.group(1).strip()
                description = self._clean_description(description)

            # Extract proponents from description
            proponents = self._extract_proponents(description)

            if theory_name and len(theory_name) > 3:
                theories.append(
                    TheoryEntry(
                        name=theory_name,
                        category=category,
                        description=description[:1000],  # Truncate long descriptions
                        proponents=proponents,
                        source_url=result.url,
                        extracted_at=datetime.now(timezone.utc).isoformat() + "Z",
                    )
                )

        logger.info(f"Extracted {len(theories)} theories from {result.url}")
        return theories

    def _infer_category(self, url: str, title: str) -> str:
        """Infer theory category from URL or title."""
        combined = f"{url} {title}".lower()

        categories = [
            ("quantum", "quantum"),
            ("computational", "computational"),
            ("information", "information"),
            ("integrated", "integrated-information"),
            ("global workspace", "global-workspace"),
            ("higher-order", "higher-order"),
            ("phenomenal", "phenomenal"),
            ("panpsychism", "panpsychism"),
            ("dualism", "dualism"),
            ("emergence", "emergence"),
            ("embodied", "embodied"),
            ("enactive", "enactive"),
        ]

        for keyword, category in categories:
            if keyword in combined:
                return category

        return "consciousness-general"

    def _is_meta_heading(self, heading: str) -> bool:
        """Check if heading is navigation/meta rather than theory."""
        meta_keywords = [
            "contents", "navigation", "references", "see also",
            "external links", "further reading", "notes",
            "bibliography", "index", "menu", "sidebar"
        ]
        heading_lower = heading.lower()
        return any(kw in heading_lower for kw in meta_keywords)

    def _clean_description(self, text: str) -> str:
        """Clean extracted description text."""
        # Remove markdown links but keep text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove excess whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_proponents(self, description: str) -> List[str]:
        """Extract proponent names from description text."""
        proponents = []

        # Common patterns for citing proponents
        patterns = [
            r"proposed by ([A-Z][a-z]+ [A-Z][a-z]+)",
            r"developed by ([A-Z][a-z]+ [A-Z][a-z]+)",
            r"([A-Z][a-z]+ [A-Z][a-z]+)'s theory",
            r"according to ([A-Z][a-z]+ [A-Z][a-z]+)",
            r"([A-Z][a-z]+ [A-Z][a-z]+) argues",
            r"([A-Z][a-z]+ [A-Z][a-z]+) proposes",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, description)
            proponents.extend(matches)

        # Deduplicate while preserving order
        seen = set()
        unique_proponents = []
        for p in proponents:
            if p not in seen:
                seen.add(p)
                unique_proponents.append(p)

        return unique_proponents[:5]  # Limit to 5 proponents

    async def harvest_urls(
        self, urls: List[str], output_dir: Path
    ) -> Dict[str, Any]:
        """
        Harvest theories from multiple URLs.

        Args:
            urls: List of URLs to crawl
            output_dir: Directory to save extracted theories

        Returns:
            Summary of harvest results
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        all_theories: List[TheoryEntry] = []
        results_summary = {
            "total_urls": len(urls),
            "successful": 0,
            "failed": 0,
            "theories_extracted": 0,
            "errors": [],
        }

        for url in urls:
            logger.info(f"Crawling: {url}")
            result = await self.crawl_url(url)

            if result.success:
                theories = self.extract_theories(result)
                all_theories.extend(theories)
                results_summary["successful"] += 1
                results_summary["theories_extracted"] += len(theories)
            else:
                results_summary["failed"] += 1
                results_summary["errors"].append({
                    "url": url,
                    "error": result.error,
                })

        # Save extracted theories
        theories_path = output_dir / "harvested-theories.json"
        theories_data = [
            {
                "name": t.name,
                "category": t.category,
                "subcategory": t.subcategory,
                "description": t.description,
                "proponents": t.proponents,
                "source_url": t.source_url,
                "extracted_at": t.extracted_at,
            }
            for t in all_theories
        ]
        theories_path.write_text(
            json.dumps(theories_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Saved {len(all_theories)} theories to {theories_path}")

        # Save summary
        summary_path = output_dir / "harvest-summary.json"
        results_summary["harvested_at"] = datetime.now(timezone.utc).isoformat() + "Z"
        summary_path.write_text(
            json.dumps(results_summary, indent=2),
            encoding="utf-8",
        )

        return results_summary

    async def harvest_and_publish(
        self, urls: List[str], output_dir: Path, publish_to_hirag: bool = False
    ) -> Dict[str, Any]:
        """
        Harvest theories and optionally publish to Hi-RAG v2.

        Args:
            urls: List of URLs to crawl
            output_dir: Directory to save extracted theories
            publish_to_hirag: If True, publish CGP packets to Hi-RAG v2

        Returns:
            Summary including publishing results
        """
        summary = await self.harvest_urls(urls, output_dir)

        if publish_to_hirag:
            # Import CGP mapper for publishing
            try:
                from pmoves.services.consciousness_service.cgp_mapper import CGPMapper

                mapper = CGPMapper()
                theories_path = output_dir / "harvested-theories.json"
                theories = json.loads(theories_path.read_text())

                publish_results = await mapper.batch_publish(theories)
                summary["publishing"] = {
                    "total": len(publish_results),
                    "successful": sum(1 for r in publish_results if r["status"] == "success"),
                }

                await mapper.close()

            except ImportError:
                logger.warning("CGP mapper not available, skipping Hi-RAG publishing")

        return summary


async def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Single URL to harvest")
    parser.add_argument("--urls-file", type=Path, help="File containing URLs (one per line)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pmoves/data/consciousness/harvested"),
        help="Output directory",
    )
    parser.add_argument("--use-http", action="store_true", help="Use HTTP API instead of NATS")
    parser.add_argument("--publish", action="store_true", help="Publish to Hi-RAG v2")
    args = parser.parse_args(argv)

    urls = []
    if args.url:
        urls.append(args.url)
    elif args.urls_file and args.urls_file.exists():
        urls = [
            line.strip()
            for line in args.urls_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

    if not urls:
        print("[error] No URLs provided. Use --url or --urls-file", file=sys.stderr)
        return 1

    harvester = ConsciousnessHarvester(use_nats=not args.use_http)

    try:
        if harvester.use_nats:
            await harvester.connect()

        summary = await harvester.harvest_and_publish(
            urls, args.output, publish_to_hirag=args.publish
        )

        print(f"\n[done] Harvest complete:")
        print(f"  URLs processed: {summary['total_urls']}")
        print(f"  Successful: {summary['successful']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Theories extracted: {summary['theories_extracted']}")
        print(f"  Output: {args.output}")

        return 0

    finally:
        await harvester.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
