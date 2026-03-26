"""
URL Ingestion Plugin
====================

This plugin ingests web content from URLs using a powerful web scraping
and crawling service that handles JavaScript rendering, anti-bot mechanisms, and more.

Features:
- Accepts a single URL or a text file containing URLs (one per line)
- Recursively crawls linked pages with configurable depth and scope
- Extracts clean markdown content from web pages
- Supports configurable chunking strategies using LangChain text splitters
- Preserves metadata including source URL, title, and content type
- Can use local self-hosted crawling service

Usage (API Example):
plugin_name: url_ingest
plugin_params: {
"url": "https://www.example.com/",
"limit": 100, # optional: max pages to crawl (default: 100)
"max_discovery_depth": 2, # optional: crawl depth (default: 2)
"crawl_entire_domain": true, # optional: follow sibling/parent URLs (default: true)
"chunk_size": 1000, # optional
"chunk_overlap": 200, # optional
"splitter_type": "RecursiveCharacterTextSplitter", # optional
"api_url": "http://host.docker.internal:3002", # optional: Crawling service API URL
"api_key": "your-api-key", # optional: only needed for cloud service
}

TIPS:
- For best coverage, start from a high-level path (e.g., https://www.dbizi.eus/es/)
- The crawler will follow links from that starting point up to max_discovery_depth
- Use 'limit' to control the maximum number of pages crawled
- Set crawl_entire_domain=true to allow crawling sibling pages (recommended)

Environment Variables:
FIRECRAWL_API_URL: Base URL for crawling service API (default: https://api.firecrawl.dev)
FIRECRAWL_API_KEY: API key for crawling service (not needed for self-hosted instances)
Environment Toggle:
Set PLUGIN_URL_INGEST=DISABLE to disable auto-registration.

Compatible with: firecrawl-py >= 4.8.0
"""

from __future__ import annotations

import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

try:
	from firecrawl import Firecrawl
	from langchain_text_splitters import (
		RecursiveCharacterTextSplitter,
		CharacterTextSplitter,
		TokenTextSplitter,
	)
	_DEPENDENCIES_AVAILABLE = True
except ImportError:
	_DEPENDENCIES_AVAILABLE = False

from .base import IngestPlugin, PluginRegistry


def _is_valid_url(url: str) -> bool:
    """Validate if a string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def _extract_urls_from_file(file_path: str) -> List[str]:
    """Extract URLs from a text file (one per line)."""
    urls: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and _is_valid_url(line):
                    urls.append(line)
    except Exception as e:
        print(f"WARNING: [url_ingest] Failed to read URLs from file: {str(e)}")
    return urls


@PluginRegistry.register
class URLIngestPlugin(IngestPlugin):
	"""Ingest web content from URLs using web crawling.
	This plugin leverages powerful web scraping capabilities to crawl
	websites, extract clean markdown content, and chunk it for ingestion into the
	knowledge base.
	
	Supports progress reporting for multi-URL ingestion.
	"""

	name = "url_ingest"
	kind = "remote-ingest"
	description = "Ingest web content from URLs with configurable chunking"
	supported_file_types = {"txt"}  # Supports text files containing URLs
	supports_progress = True  # This plugin supports progress callbacks

	def get_parameters(self) -> Dict[str, Dict[str, Any]]:
		"""Get the parameters accepted by this plugin."""
		return {
			"url": {
				"type": "string",
				"description": "Target URL to crawl. Start from a high-level path for better coverage (e.g., https://example.com/section/ instead of https://example.com/section/page). If omitted, reads URLs from uploaded text file.",
				"required": False,
			},
			"max_discovery_depth": {
				"type": "integer",
				"description": "Maximum discovery depth for recursive crawling (0 = only root page)",
				"required": False,
				"default": 2,
			},
			"limit": {
				"type": "integer",
				"description": "Maximum number of pages to crawl (default: 100)",
				"default": 100,
				"required": False,
			},
			"crawl_entire_domain": {
				"type": "boolean",
				"description": "Allow crawler to follow sibling/parent URLs, not just child paths (default: true)",
				"default": True,
				"required": False,
			},

			"chunk_size": {
				"type": "integer",
				"description": "Size of each chunk for text splitting",
				"default": 1000,
				"required": False,
			},
			"chunk_overlap": {
				"type": "integer",
				"description": "Number of characters to overlap between chunks",
				"default": 200,
				"required": False,
			},
			"splitter_type": {
				"type": "string",
				"description": "Type of LangChain splitter to use",
				"enum": ["RecursiveCharacterTextSplitter", "CharacterTextSplitter", "TokenTextSplitter"],
				"default": "RecursiveCharacterTextSplitter",
				"required": False,
			},
			"api_url": {
				"type": "string",
				"description": "Crawling service API URL (default: from FIRECRAWL_API_URL env or https://api.firecrawl.dev)",
				"required": False,
			},
			"api_key": {
				"type": "string",
				"description": "Crawling service API key (default: from FIRECRAWL_API_KEY env, not needed for self-hosted)",
				"required": False,
			},
			"exclude_paths": {
				"type": "array",
				"description": "URL path regex patterns to exclude from crawling (e.g., ['blog/.*', 'archive/.*'])",
				"required": False,
			},
			"include_paths": {
				"type": "array",
				"description": "URL path regex patterns to include in crawling (e.g., ['docs/.*', 'api/.*'])",
				"required": False,
			},
			"timeout": {
				"type": "integer",
				"description": "Maximum seconds to wait for the entire crawl job to complete",
				"required": False,
				"default": 300,
			},
			"description": {
				"type": "long-string",
				"description": "Optional description for the ingested content",
				"required": False,
			},
			"citation": {
				"type": "long-string",
				"description": "Optional citation for the ingested content",
				"required": False,
			}
		}

	def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
		"""Ingest web content from URL(s) using Firecrawl.
		Args:
			file_path: Path to optional text file containing URLs
			**kwargs: Plugin parameters (url, limit, etc.)
			         May include 'progress_callback' for progress reporting
		Returns:
			List of document chunks with metadata
		"""
		if not _DEPENDENCIES_AVAILABLE:
			raise ImportError(
				"Required dependencies not installed. Install with: "
				"pip install firecrawl-py langchain-text-splitters"
			)

		# Extract parameters
		target_url: Optional[str] = kwargs.get("url")
		limit: int = int(kwargs.get("limit", 100))
		max_discovery_depth: Optional[int] = kwargs.get("max_discovery_depth", 2)
		crawl_entire_domain: bool = kwargs.get("crawl_entire_domain", True)
		allow_subdomains: bool = kwargs.get("allow_subdomains", False)
		ignore_query_parameters: bool = kwargs.get("ignore_query_parameters", False)
		chunk_size: int = int(kwargs.get("chunk_size", 1000))
		chunk_overlap: int = int(kwargs.get("chunk_overlap", 200))
		splitter_type: str = kwargs.get("splitter_type", "RecursiveCharacterTextSplitter")
		api_url: Optional[str] = kwargs.get("api_url") or os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
		api_key: Optional[str] = kwargs.get("api_key") or os.getenv("FIRECRAWL_API_KEY")
		exclude_paths: Optional[List[str]] = kwargs.get("exclude_paths")
		include_paths: Optional[List[str]] = kwargs.get("include_paths")
		description: Optional[str] = kwargs.get("description")
		citation: Optional[str] = kwargs.get("citation")
		file_url: str = kwargs.get("file_url", "")
		job_timeout: Optional[int] = kwargs.get("timeout", 300)

		# Collect URLs to process
		urls: List[str] = []
		if target_url:
			if not _is_valid_url(target_url):
				raise ValueError(f"Invalid URL provided: {target_url}")
			urls.append(target_url)
		else:
			urls.extend(_extract_urls_from_file(file_path))

		if not urls:
			raise ValueError(
				"No valid URL provided. Specify 'url' parameter or upload a text file with URLs."
			)
		
		# Report initial progress
		self.report_progress(kwargs, 0, len(urls), f"Starting crawl of {len(urls)} URL(s)...")

		# Initialize text splitter
		splitter_params = {
			"chunk_size": chunk_size,
			"chunk_overlap": chunk_overlap
		}
		try:
			if splitter_type == "RecursiveCharacterTextSplitter":
				text_splitter = RecursiveCharacterTextSplitter(**splitter_params)
			elif splitter_type == "CharacterTextSplitter":
				text_splitter = CharacterTextSplitter(separator='\n', **splitter_params)
			elif splitter_type == "TokenTextSplitter":
				text_splitter = TokenTextSplitter(**splitter_params)
			else:
				raise ValueError(f"Unsupported splitter type: {splitter_type}")
		except Exception as e:
			raise ValueError(f"Failed to initialize text splitter: {str(e)}")

		# Initialize crawling client
		print(f"INFO: [url_ingest] Initializing crawler with API URL: {api_url}")
		try:
			# For self-hosted instances, use a dummy API key if none provided
			if not api_key and api_url != "https://api.firecrawl.dev":
				api_key = "dummy-key-for-self-hosted"
			firecrawl = Firecrawl(api_key=api_key, api_url=api_url)
		except Exception as e:
			raise ValueError(f"Failed to initialize crawler client: {str(e)}")

		all_chunks: List[Dict[str, Any]] = []

		for url_idx, url in enumerate(urls):
			print(f"INFO: [url_ingest] Processing URL: {url}")
			self.report_progress(kwargs, url_idx, len(urls), f"Crawling {url}...")
			try:
				# Prepare crawl options for v2 API
				crawl_options = {
					"limit": limit,
					"scrape_options": {
						"formats": ["markdown", "html"]
					}
				}
				
				# Add v2 API parameters
				if max_discovery_depth is not None:
					crawl_options["max_discovery_depth"] = int(max_discovery_depth)
				
				crawl_options["crawl_entire_domain"] = crawl_entire_domain
				crawl_options["allow_subdomains"] = allow_subdomains
				crawl_options["ignore_query_parameters"] = ignore_query_parameters
				
				if exclude_paths:
					crawl_options["exclude_paths"] = exclude_paths
				if include_paths:
					crawl_options["include_paths"] = include_paths

				# Crawl the website
				print(f"INFO: [url_ingest] Starting crawl with limit={limit}, max_discovery_depth={max_discovery_depth}, crawl_entire_domain={crawl_entire_domain}")
				if job_timeout is not None:
					crawl_result = firecrawl.crawl(url, **crawl_options, timeout=int(job_timeout))
				else:
					crawl_result = firecrawl.crawl(url, **crawl_options)
				if not crawl_result or not hasattr(crawl_result, 'data'):
					print(f"WARNING: [url_ingest] No data returned from crawl for {url}")
					continue

				documents = crawl_result.data
				print(f"INFO: [url_ingest] Crawled {len(documents)} pages from {url}")

				# Log the URLs that were crawled for debugging
				if documents:
					print(f"INFO: [url_ingest] Pages crawled:")
					for i, doc in enumerate(documents[:10]):  # Show first 10
						page_url = "unknown"
						if hasattr(doc, 'metadata'):
							md = doc.metadata
							if hasattr(md, 'sourceURL'):
								page_url = md.sourceURL
							elif hasattr(md, 'source_url'):
								page_url = md.source_url
							elif isinstance(md, dict):
								page_url = md.get('sourceURL') or md.get('source_url') or 'unknown'
						print(f"  [{i+1}] {page_url}")
					if len(documents) > 10:
						print(f"  ... and {len(documents) - 10} more pages")

				# Process each document
				for doc in documents:
					# Get markdown content
					content = doc.markdown if hasattr(doc, 'markdown') else ""
					if not content:
						print(f"WARNING: [url_ingest] No markdown content in document from {url}")
						continue

					# Get metadata in a robust way (support dict and Pydantic objects)
					md_obj = getattr(doc, 'metadata', None)
					md_dict = None
					if hasattr(doc, 'metadata_dict') and isinstance(getattr(doc, 'metadata_dict'), dict):
						md_dict = getattr(doc, 'metadata_dict')
					elif md_obj is not None:
						if hasattr(md_obj, 'model_dump'):
							try:
								md_dict = md_obj.model_dump()
							except Exception:
								md_dict = None
						if md_dict is None and hasattr(md_obj, 'dict'):
							try:
								md_dict = md_obj.dict()
							except Exception:
								md_dict = None
						if md_dict is None and isinstance(md_obj, dict):
							md_dict = md_obj

					def _mget(keys: list, default=None):
						"""Try to get a metadata field from dict or object using multiple keys."""
						for k in keys:
							if md_dict and isinstance(md_dict, dict) and k in md_dict:
								return md_dict.get(k)
							if md_obj is not None and hasattr(md_obj, k):
								try:
									return getattr(md_obj, k)
								except Exception:
									pass
						return default
					
					# Chunk the content
					chunks = text_splitter.split_text(content)
					# Prepare base metadata
					base_metadata = {
						"ingestion_plugin": self.name,
						"source_url": url,
						"page_url": _mget(["sourceURL", "source_url", "url"], url),
						"title": _mget(["title"], ""),
						"language": _mget(["language"], ""),
						"limit": limit,
						"max_discovery_depth": max_discovery_depth,
						"crawl_entire_domain": crawl_entire_domain,
						"chunking_strategy": f"langchain_{splitter_type.lower()}",
						"chunk_size": chunk_size,
						"chunk_overlap": chunk_overlap,
						"file_url": file_url,
						"retrieval_timestamp": datetime.utcnow().isoformat(),
						"plugin_version": "2.0.0",
						"crawler_api_url": api_url,
					}
					if description:
						base_metadata["description"] = description
					if citation:
						base_metadata["citation"] = citation
					# Add additional metadata from crawler
					og_title = _mget(["ogTitle"])
					if og_title:
						base_metadata["og_title"] = og_title
					og_desc = _mget(["ogDescription"])
					if og_desc:
						base_metadata["og_description"] = og_desc
					status_code = _mget(["statusCode"])
					if status_code is not None:
						base_metadata["status_code"] = status_code

					# Create chunks with metadata
					for idx, chunk_text in enumerate(chunks):
						chunk_metadata = base_metadata.copy()
						chunk_metadata.update({
							"chunk_index": idx,
							"chunk_count": len(chunks),
						})
						# Filter out None values from metadata (ChromaDB doesn't accept them)
						chunk_metadata = {k: v for k, v in chunk_metadata.items() if v is not None}
						all_chunks.append({
							"text": chunk_text,
							"metadata": chunk_metadata,
						})

			except Exception as e:
				print(f"ERROR: [url_ingest] Failed to process {url}: {str(e)}")
				import traceback
				traceback.print_exc()
				self.report_progress(kwargs, url_idx + 1, len(urls), f"Failed to crawl {url}: {str(e)[:50]}")
				continue

		if not all_chunks:
			raise ValueError("No content could be extracted from the provided URL(s).")

		# Report completion
		self.report_progress(kwargs, len(urls), len(urls), f"Completed: {len(all_chunks)} chunks from {len(urls)} URL(s)")
		print(f"INFO: [url_ingest] Successfully created {len(all_chunks)} chunks from {len(urls)} URL(s)")
		return all_chunks