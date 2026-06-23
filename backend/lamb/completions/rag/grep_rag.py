"""
Grep RAG — Complementary Grep-Based Search Layer

A RAG processor that uses a small/nano LLM to drive iterative grep/egrep/ripgrep
searches across all files in the assistant's knowledge bases. Works alongside
any embedding-based RAG processor in two modes:

- **hybrid**: Run both grep AND the underlying RAG in parallel, merge results.
- **primary**: Grep runs first. If no matches found → fall back to underlying RAG.

The nano model chooses the search tool (grep/egrep/ripgrep), proposes regex patterns,
evaluates result quality, and decides when enough content has been found.
"""

import asyncio
import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

import requests

from lamb.lamb_classes import Assistant
from lamb.completions.org_config_resolver import OrganizationConfigResolver
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="RAG")

# ── Configuration defaults ──────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "grep_mode": "hybrid",         # "hybrid" | "primary"
    "grep_fallback_rag": "simple_rag",  # Underlying RAG to complement or fall back to
    "grep_max_tries": 5,           # Max search iterations (1 LLM call per try)
    "grep_context_lines": 3,       # Lines of context before/after each match
    "grep_max_total_chars": 8000,  # Max total characters sent to main LLM
}

# ── Nano model prompts ──────────────────────────────────────────────────────

NANO_SYSTEM_PROMPT = """You are a search assistant. Your job is to help find relevant
information across a collection of knowledge base documents.

Given a user's question and the results of previous searches, respond with ONE of:

Option 1 — Propose a new search:
TOOL: <grep|egrep|ripgrep>
PATTERN: <regex pattern>
FLAGS: <-i -C N>
REASON: <brief explanation of what you're looking for>

Option 2 — Declare done:
DONE: <brief explanation of why enough content has been found>

Rules:
1. On the first try, propose the most natural search for the question.
2. If a search finds content, READ the matched context preview in the history.
   If the found text CONTAINS the information the user asked for → respond DONE.
   Do NOT keep searching for "more details" when the answer is already present.
   The main LLM will extract the answer from what you found.
3. If previous searches found NOTHING, try synonyms, related terms, broader/
   narrower terms, fix spelling, or TRANSLATE to the document's language —
   this is the main reason retries exist.
4. LANGUAGE AWARENESS: If the user's question is in a different language than
   the documents, TRANSLATE your search terms into the document's language.
   Include terms in BOTH languages using | alternation when unsure.
   Example: user asks "What are the prices?" in English but documents are in
   Spanish → pattern: "precios|prices|tarifas|fees|costos|costs"
5. Choose the right tool:
   - grep: simple word/phrase searches
   - egrep: when you need alternation (|), grouping (), or word boundaries (\\b)
   - ripgrep: for large multi-file searches where speed matters
6. Regex tips for egrep:
   - Use | for alternatives: "late|missing|overdue"
   - Use () for grouping: "grad(e|ing)"
   - Use \\b for word boundaries: "\\bexam\\b"
7. Maximum one pattern per response. Keep it SIMPLE but include translations
   when the user's language differs from the documents'.
8. The search runs recursively (-r) across ALL files by default."""


NANO_USER_PROMPT_TEMPLATE = """Question: {question}
{doc_language}
Search history:
{history}

What should I search for next?"""


# ── Main processor ──────────────────────────────────────────────────────────

async def rag_processor(
    messages: List[Dict[str, Any]],
    assistant: Assistant = None,
    request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Grep RAG processor — nano LLM drives iterative grep across KB documents.

    Args:
        messages: Conversation messages
        assistant: Assistant object with metadata config
        request: Original request dict

    Returns:
        Dict with "context" (formatted grep results) and "sources" (metadata)
    """
    logger.info("Using grep_rag processor with assistant: %s",
                assistant.name if assistant else "None")

    if not assistant:
        return {"context": "", "sources": []}

    # Parse config from assistant metadata
    config = _parse_config(assistant)
    mode = config.get("grep_mode", "hybrid")
    fallback_rag = config.get("grep_fallback_rag", "simple_rag")
    max_tries = int(config.get("grep_max_tries", 5))
    context_lines = int(config.get("grep_context_lines", 3))
    max_total_chars = int(config.get("grep_max_total_chars", 8000))

    # Extract the user's question
    user_question = _extract_user_question(messages)
    if not user_question:
        return {"context": "", "sources": []}

    logger.info("Grep RAG mode=%s fallback=%s question='%s...'",
                mode, fallback_rag, user_question[:80])

    # Resolve KB documents (file content + metadata for citations)
    documents = await _resolve_kb_documents(assistant)
    if not documents:
        logger.warning("No KB documents found for assistant %s", assistant.id)
        return await _run_fallback_rag(messages, assistant, request, fallback_rag)

    logger.info("Resolved %d documents for grep search", len(documents))

    # Run the grep search loop
    grep_result = await _run_grep_search(
        user_question=user_question,
        documents=documents,
        max_tries=max_tries,
        context_lines=context_lines,
        max_total_chars=max_total_chars,
        assistant_owner=assistant.owner,
    )

    if mode == "primary":
        # Grep first, fall back to RAG only if zero matches
        if grep_result["matches"]:
            logger.info("Primary mode: grep found %d matches, using grep results",
                        len(grep_result["matches"]))
            return _build_grep_response(grep_result["matches"], documents, max_total_chars)
        else:
            logger.info("Primary mode: grep found no matches, falling back to %s",
                        fallback_rag)
            return await _run_fallback_rag(messages, assistant, request, fallback_rag)

    elif mode == "hybrid":
        # Run RAG in parallel with grep (grep already completed above)
        # Hybrid always uses simple_rag as the companion — grep handles precision,
        # simple semantic coverage is all that's needed alongside it.
        logger.info("Hybrid mode: running simple_rag in parallel")
        rag_context = await _run_fallback_rag(messages, assistant, request, "simple_rag")

        if grep_result["matches"]:
            grep_response = _build_grep_response(
                grep_result["matches"], documents, max_total_chars
            )
            return _merge_contexts(grep_response, rag_context, max_total_chars)
        else:
            # No grep matches, just return RAG results
            logger.info("Hybrid mode: grep found no matches, using RAG only")
            return rag_context

    else:
        logger.warning("Unknown grep_mode '%s', falling back to %s", mode, fallback_rag)
        return await _run_fallback_rag(messages, assistant, request, fallback_rag)


# ── Config parsing ──────────────────────────────────────────────────────────

def _parse_config(assistant: Assistant) -> Dict[str, Any]:
    """Parse grep_rag configuration from assistant metadata."""
    config = dict(DEFAULT_CONFIG)
    try:
        if assistant.metadata and assistant.metadata.strip():
            metadata = json.loads(assistant.metadata)
            for key in DEFAULT_CONFIG:
                if key in metadata:
                    config[key] = metadata[key]
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("Failed to parse assistant metadata: %s", e)
    return config


# ── Question extraction ─────────────────────────────────────────────────────

def _extract_user_question(messages: List[Dict[str, Any]]) -> str:
    """Extract the last user message from the conversation."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multimodal: extract text parts
                text_parts = [
                    item.get("text", "") for item in content
                    if item.get("type") == "text"
                ]
                return " ".join(text_parts)
            return content
    return ""


# ── KB document resolution ──────────────────────────────────────────────────

async def _resolve_kb_documents(assistant: Assistant) -> List[Dict[str, Any]]:
    """
    Get all KB documents with their content and source metadata.

    For each KB collection attached to the assistant:
    1. List file registries via KB server API
    2. Fetch document content via KB server
    3. Return list of {file_path, content, metadata}

    Returns:
        List of document dicts with keys: file_path, content, metadata
    """
    if not hasattr(assistant, 'RAG_collections') or not assistant.RAG_collections:
        return []

    # Get KB server configuration
    KB_SERVER_URL = None
    KB_API_KEY = None

    try:
        config_resolver = OrganizationConfigResolver(assistant.owner)
        kb_config = config_resolver.get_knowledge_base_config()
        if kb_config:
            KB_SERVER_URL = kb_config.get("server_url")
            KB_API_KEY = kb_config.get("api_token")
    except Exception as e:
        logger.warning("Error getting org KB config: %s", e)

    if not KB_SERVER_URL:
        import config as app_config
        KB_SERVER_URL = os.getenv('LAMB_KB_SERVER')
        KB_API_KEY = os.getenv('LAMB_KB_SERVER_TOKEN') or getattr(
            app_config, 'LAMB_BEARER_TOKEN', ''
        )

    if not KB_SERVER_URL:
        logger.error("No KB server URL configured")
        return []

    headers = {
        "Authorization": f"Bearer {KB_API_KEY}",
        "Content-Type": "application/json",
    }

    # Parse collection IDs
    collections = [
        cid.strip() for cid in assistant.RAG_collections.split(',') if cid.strip()
    ]

    documents = []

    for collection_id in collections:
        try:
            # Get file list for this collection
            files_url = f"{KB_SERVER_URL}/collections/{collection_id}/files"
            resp = requests.get(files_url, headers=headers, timeout=30)

            if resp.status_code != 200:
                logger.warning(
                    "Failed to list files for collection %s: %s",
                    collection_id, resp.status_code
                )
                continue

            file_entries = resp.json()

            # Also query all chunks for full text
            query_url = f"{KB_SERVER_URL}/collections/{collection_id}/query"
            query_payload = {
                "query_text": "",  # Empty query to get all? Use top_k instead
                "top_k": 500,      # Get up to 500 chunks
                "threshold": 0.0,
                "plugin_params": {},
            }

            # Build a document map: file → full text
            # For each file entry, we try to get its content
            for entry in file_entries:
                try:
                    # Try to get markdown content URL from processing_stats
                    md_url = None
                    stats = entry.get("processing_stats", {})
                    if isinstance(stats, dict):
                        output_files = stats.get("output_files", {})
                        md_url = output_files.get("markdown_url")

                    # If we have a markdown URL, fetch the full text
                    content = ""
                    if md_url:
                        content = await _fetch_text_content(md_url, headers)
                    elif entry.get("file_url"):
                        content = await _fetch_text_content(
                            entry.get("file_url"), headers
                        )
                    elif entry.get("markdown_preview"):
                        # Use the preview as fallback
                        content = entry.get("markdown_preview", "")

                    if content:
                        documents.append({
                            "file_path": entry.get("file_path", ""),
                            "original_filename": entry.get("original_filename", ""),
                            "content": content,
                            "metadata": entry,  # Full file registry entry
                            "collection_id": collection_id,
                        })
                except Exception as e:
                    logger.debug("Error processing file entry: %s", e)
                    continue

        except Exception as e:
            logger.warning("Error processing collection %s: %s", collection_id, e)
            continue

    return documents


async def _fetch_text_content(url: str, headers: Dict[str, str]) -> str:
    """Fetch text content from a URL. Handles absolute, relative, and localhost URLs."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)

        # If URL points to localhost (frontend dev server :5173, backend :9099,
        # or any other port), the Docker container can't reach it via localhost.
        # Rewrite to use the KB server's internal Docker hostname instead.
        if parsed.hostname in ("localhost", "127.0.0.1", "host.docker.internal"):
            # Try reading from local filesystem first (dev without Docker)
            url_path = parsed.path.lstrip("/")
            for candidate in _local_file_candidates(url_path):
                if os.path.isfile(candidate):
                    try:
                        with open(candidate, "r", encoding="utf-8") as f:
                            content = f.read()
                        if content and _is_text_content(content):
                            logger.debug("Read content from local file: %s", candidate)
                            return content
                    except (UnicodeDecodeError, OSError):
                        continue

            # Fallback: rewrite to KB server (kb:9090 inside Docker)
            kb_base = os.getenv("LAMB_KB_SERVER", "http://kb:9090")
            url = kb_base.rstrip("/") + parsed.path
            logger.debug("Rewrote localhost URL → KB server: %s", url)

        # If URL is relative (starts with /), it's relative to KB server
        elif url.startswith("/"):
            kb_base = os.getenv("LAMB_KB_SERVER", "")
            if kb_base:
                url = kb_base.rstrip("/") + url

        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            content = resp.text
            if len(content) > 0 and _is_text_content(content):
                return content
            else:
                logger.debug("Skipping non-text content from %s", url)
        else:
            logger.debug("Failed to fetch %s: %s", url, resp.status_code)
        return ""
    except Exception as e:
        logger.debug("Error fetching %s: %s", url, e)
        return ""


def _is_text_content(content: str) -> bool:
    """Heuristic check if string looks like text (not binary)."""
    if not content:
        return False
    # Check for null bytes (binary indicator)
    if '\x00' in content[:1000]:
        return False
    # Check printable ratio
    sample = content[:2000]
    printable = sum(1 for c in sample if c.isprintable() or c in '\n\r\t')
    return printable / max(len(sample), 1) > 0.8


def _local_file_candidates(url_path: str) -> list:
    """Generate candidate filesystem paths for a URL path like 'static/1/dbizi/xxx.txt'."""
    candidates = []
    # 1. Relative to CWD
    candidates.append(url_path)
    # 2. Project root (when LAMB_PROJECT_PATH is mounted)
    project_path = os.getenv("LAMB_PROJECT_PATH", "")
    if project_path:
        candidates.append(os.path.join(project_path, url_path))
        # Also try kb-server as sibling
        candidates.append(os.path.join(
            project_path, "lamb-kb-server-stable", "backend", url_path
        ))
    # 3. Backend's own static/ directory
    backend_static = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "static")
    candidates.append(os.path.join(backend_static, url_path))
    # 4. Production Docker layout (/app)
    if url_path.startswith("static/"):
        candidates.append(os.path.join("/app", url_path))
    return candidates


# ── Language detection ──────────────────────────────────────────────────────

# Common words unique to each language (high-frequency, low-overlap)
_LANG_MARKERS = {
    "Spanish": [
        "que", "los", "las", "del", "una", "por", "para", "como", "está",
        "más", "pero", "entre", "desde", "hasta", "porque", "cuando",
        "también", "muy", "todo", "ción", "idad", "ente", "aron", "iendo",
    ],
    "English": [
        "the", "and", "that", "have", "for", "not", "with", "this",
        "but", "from", "they", "been", "would", "there", "their",
        "about", "which", "after", "could", "should", "tion", "ing ",
    ],
    "Catalan": [
        "amb", "dels", "una", "com", "més", "també", "tots", "cada",
        "sense", "sobre", "entre", "després", "contra", "segons",
        "mitjançant", "llarg", "següent", "forma", "qualsevol",
    ],
    "Basque": [
        "eta", "ere", "duten", "ditu", "arte", "dira", "baten",
        "izan", "egin", "dago", "dutenak", "beraz", "orduan",
        "bidez", "zehar", "gainean", "artean", "aurka",
    ],
    "French": [
        "que", "les", "des", "est", "pas", "dans", "nous", "aux",
        "sont", "avec", "fait", "leur", "être", "avoir", "cette",
        "comme", "plus", "bien", "ment", "tion", "eurs",
    ],
}


def _detect_document_language(documents: List[Dict[str, Any]]) -> str:
    """
    Detect the dominant language of the KB documents by sampling text
    and counting language-specific marker words.

    Returns a human-readable string like "Spanish" or empty string if
    documents are too short or detection is ambiguous.
    """
    if not documents:
        return ""

    # Concatenate a sample from all documents (up to ~5000 chars)
    sample_parts = []
    total_chars = 0
    for doc in documents:
        content = doc.get("content", "")
        if content:
            sample_parts.append(content[:2000])
            total_chars += len(content[:2000])
            if total_chars >= 5000:
                break

    if not sample_parts:
        return ""

    sample = " ".join(sample_parts).lower()

    # Count marker words for each language
    scores = {}
    for lang, markers in _LANG_MARKERS.items():
        score = 0
        for marker in markers:
            score += sample.count(marker.lower())
        scores[lang] = score

    # Pick the language with the highest score, but require a minimum threshold
    if not scores:
        return ""

    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]

    # Require at least some marker hits to be confident
    if best_score < 3:
        return ""

    return best_lang


def _detect_question_language(question: str) -> str:
    """
    Detect the language of the user's question using the same marker-word
    approach. Returns language name or empty string.
    """
    if not question or len(question) < 10:
        return ""

    sample = question.lower()
    scores = {}
    for lang, markers in _LANG_MARKERS.items():
        score = 0
        for marker in markers:
            score += sample.count(marker.lower())
        scores[lang] = score

    if not scores:
        return ""

    best_lang = max(scores, key=scores.get)
    if scores[best_lang] < 1:
        return ""

    return best_lang


# ── Grep search loop ────────────────────────────────────────────────────────

async def _run_grep_search(
    user_question: str,
    documents: List[Dict[str, Any]],
    max_tries: int,
    context_lines: int,
    max_total_chars: int,
    assistant_owner: str,
) -> Dict[str, Any]:
    """
    Run the iterative grep search loop driven by the nano model.

    Returns:
        Dict with "matches" (list of match dicts) and "tries" (list of try records)
    """
    from lamb.completions.small_fast_model_helper import (
        invoke_small_fast_model,
        is_small_fast_model_configured,
    )

    all_matches = []
    tries = []
    already_tried = set()  # Track (tool, pattern) to avoid duplicates

    # Detect document language so the nano model can translate search terms
    doc_lang = _detect_document_language(documents)
    if doc_lang:
        logger.info("Detected document language: %s", doc_lang)

    for attempt in range(1, max_tries + 1):
        # Build history for the nano model
        history = _build_search_history(tries, all_matches)

        # Ask the nano model what to search
        nano_response = await _ask_nano_model(
            user_question=user_question,
            history=history,
            assistant_owner=assistant_owner,
            doc_language=doc_lang,
        )

        if not nano_response:
            logger.warning("Nano model returned no response on try %d", attempt)
            break

        if nano_response.get("done"):
            logger.info(
                "Nano model declared DONE on try %d: %s",
                attempt, nano_response.get("reason", "")
            )
            tries.append({
                "attempt": attempt,
                "done": True,
                "reason": nano_response.get("reason", ""),
            })
            break

        # Execute the search
        tool = nano_response.get("tool", "grep")
        pattern = nano_response.get("pattern", "")
        reason = nano_response.get("reason", "")

        if not pattern:
            logger.warning("Nano model returned empty pattern on try %d", attempt)
            tries.append({
                "attempt": attempt,
                "tool": tool,
                "pattern": "",
                "matches": 0,
                "error": "Empty pattern",
            })
            continue

        # Skip duplicate patterns
        dedup_key = (tool, pattern)
        if dedup_key in already_tried:
            logger.debug("Skipping duplicate pattern: %s %s", tool, pattern)
            tries.append({
                "attempt": attempt,
                "tool": tool,
                "pattern": pattern,
                "matches": 0,
                "reason": reason,
                "skipped": True,
            })
            continue

        already_tried.add(dedup_key)

        # Run the search across all documents
        logger.info(
            "Grep try %d/%d: %s '%s' — %s",
            attempt, max_tries, tool, pattern, reason
        )

        matches = _search_across_documents(
            documents=documents,
            pattern=pattern,
            tool=tool,
            context_lines=context_lines,
        )

        tries.append({
            "attempt": attempt,
            "tool": tool,
            "pattern": pattern,
            "matches": len(matches),
            "reason": reason,
        })

        if matches:
            all_matches.extend(matches)
            logger.info("Try %d: found %d matches", attempt, len(matches))
        else:
            logger.info("Try %d: no matches found", attempt)

    # Deduplicate matches
    deduped = _deduplicate_matches(all_matches, context_lines)

    return {
        "matches": deduped,
        "tries": tries,
    }


def _build_search_history(
    tries: List[Dict[str, Any]],
    matches: List[Dict[str, Any]],
) -> str:
    """Build a human-readable search history for the nano model."""
    if not tries:
        return "(No searches yet)"

    lines = []
    for t in tries:
        if t.get("done"):
            lines.append(f"Try {t['attempt']}: DONE — {t.get('reason', '')}")
        elif t.get("skipped"):
            lines.append(
                f"Try {t['attempt']}: SKIPPED (duplicate) — "
                f"{t.get('tool','')} '{t.get('pattern','')}'"
            )
        elif t.get("error"):
            lines.append(
                f"Try {t['attempt']}: ERROR — {t.get('error','')}"
            )
        else:
            lines.append(
                f"Try {t['attempt']}: {t.get('tool','')} '{t.get('pattern','')}' "
                f"— {t.get('matches', 0)} matches — {t.get('reason', '')}"
            )

    # Add a preview of current matches
    if matches:
        lines.append(f"\nCurrently found {len(matches)} matches across all attempts.")
        lines.append("Preview of found content:")
        preview_chars = 0
        for m in matches[:5]:
            snippet = m.get("context", "")[:300]
            lines.append(f"  [{m.get('source','?')}]: {snippet}...")
            preview_chars += len(snippet)
            if preview_chars > 1200:
                lines.append("  ... (more matches)")
                break

        # If we have a decent amount of content, nudge the nano model to consider stopping
        if len(matches) >= 3:
            lines.append(
                f"\nYou have found {len(matches)} relevant sections. "
                f"If this content answers the user's question, respond with DONE. "
                f"Only keep searching if the answer is clearly incomplete."
            )
        elif len(matches) >= 1:
            lines.append(
                "\nSome content was found. If it sufficiently answers the question, "
                "respond with DONE. Otherwise propose a more targeted search."
            )

    return "\n".join(lines)


async def _ask_nano_model(
    user_question: str,
    history: str,
    assistant_owner: str,
    doc_language: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Ask the nano model what to search for next.

    Args:
        user_question: The user's question
        history: Formatted search history from previous tries
        assistant_owner: Email of the assistant owner (for org config)
        doc_language: Detected language of the KB documents (e.g. "Spanish")

    Returns parsed response dict or None on failure.
    """
    from lamb.completions.small_fast_model_helper import (
        invoke_small_fast_model,
        is_small_fast_model_configured,
    )

    if not is_small_fast_model_configured(assistant_owner):
        # Fallback: do a single grep with the user's question keywords
        logger.info("No small-fast-model configured, using fallback keyword search")
        keywords = _extract_keywords(user_question)
        return {
            "done": False,
            "tool": "grep",
            "pattern": "|".join(re.escape(k) for k in keywords[:5]),
            "reason": "Fallback keyword search (no nano model configured)",
        }

    # Build language context line for the prompt
    lang_line = ""
    if doc_language:
        question_lang = _detect_question_language(user_question)
        if question_lang and question_lang != doc_language:
            lang_line = (
                f"Documents are in {doc_language}. "
                f"User asked in {question_lang}. "
                f"Include search terms in BOTH languages using | alternation.\n"
            )
        else:
            lang_line = f"Documents are in {doc_language}.\n"

    user_prompt = NANO_USER_PROMPT_TEMPLATE.format(
        question=user_question,
        doc_language=lang_line,
        history=history,
    )

    messages = [
        {"role": "system", "content": NANO_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await invoke_small_fast_model(
            messages=messages,
            assistant_owner=assistant_owner,
            stream=False,
        )

        # Extract text from response
        text = _extract_response_text(response)
        if not text:
            return None

        logger.debug("Nano model response: %s", text[:200])
        return _parse_nano_response(text)

    except Exception as e:
        logger.error("Error invoking nano model: %s", e)
        return None


def _extract_response_text(response: Any) -> str:
    """Extract text content from various LLM response formats."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        # OpenAI format
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        # Anthropic format
        content = response.get("content", [])
        if isinstance(content, list):
            return "".join(
                c.get("text", "") for c in content if c.get("type") == "text"
            )
    return ""


def _parse_nano_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse the nano model's structured response."""
    text = text.strip()

    # Check for DONE — accept multiple formats:
    #   "DONE: reason" / "DONE - reason" / "DONE"
    #   "I'm DONE" / "We are DONE"
    #   First-line "DONE" anywhere followed by reason
    done_patterns = [
        r"^DONE\b[:\-]?\s*(.*)",           # "DONE", "DONE: reason", "DONE - reason"
        r"\bDONE\b[:\-]?\s*(.*)",           # "I'm DONE", "We are DONE: ..."
    ]

    for pattern in done_patterns:
        m = re.match(pattern, text, re.IGNORECASE)
        if m:
            reason = m.group(1).strip() if m.group(1) else ""
            logger.info("Nano model declared DONE: %s", reason if reason else "(no reason)")
            return {"done": True, "reason": reason}

    # If the first line says DONE but the parser above didn't catch it
    first_line = text.split("\n")[0].strip()
    if re.match(r".*\bDONE\b", first_line, re.IGNORECASE):
        # Extract anything after DONE on that line
        done_idx = first_line.upper().find("DONE")
        reason = first_line[done_idx + 4:].strip().lstrip(":-").strip()
        logger.info("Nano model declared DONE (first-line match): %s", reason if reason else "(no reason)")
        return {"done": True, "reason": reason}

    # Parse structured TOOL/PATTERN/FLAGS/REASON response
    result = {"done": False}
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if line.upper().startswith("TOOL:"):
            result["tool"] = line[5:].strip().lower()
        elif line.upper().startswith("PATTERN:"):
            result["pattern"] = line[8:].strip()
        elif line.upper().startswith("FLAGS:"):
            result["flags"] = line[6:].strip()
        elif line.upper().startswith("REASON:"):
            result["reason"] = line[7:].strip()

    # Fallback: try to extract pattern from simpler formats
    if not result.get("pattern"):
        # Look for a quoted pattern or regex-like content
        quoted = re.findall(r'["\'](.+?)["\']', text)
        if quoted:
            result["pattern"] = quoted[0]
            # Assume grep as default tool
            if not result.get("tool"):
                result["tool"] = "grep"
            return result

        # Try to find pattern after common labels
        for label in ["pattern:", "PATTERN:", "regex:", "REGEX:"]:
            idx = text.lower().find(label.lower())
            if idx >= 0:
                result["pattern"] = text[idx + len(label):].split("\n")[0].strip()
                break

    if not result.get("pattern"):
        logger.debug("Could not parse pattern from nano response: %s", text[:200])
        return None

    if not result.get("tool"):
        result["tool"] = "grep"

    return result


def _extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """Extract meaningful keywords from user question for fallback search."""
    # Simple keyword extraction: split, remove short/common words, take unique
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "in", "on", "at", "to", "for", "of", "with", "by", "from",
        "and", "or", "but", "not", "no", "yes", "what", "how", "when",
        "where", "who", "why", "which", "do", "does", "did", "can",
        "could", "will", "would", "should", "may", "might", "this",
        "that", "these", "those", "it", "its", "i", "me", "my", "we",
        "our", "you", "your", "he", "she", "they", "them",
    }
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    keywords = []
    seen = set()
    for w in words:
        if w not in stop_words and w not in seen:
            keywords.append(w)
            seen.add(w)
            if len(keywords) >= max_keywords:
                break
    return keywords


# ── In-memory search engine ─────────────────────────────────────────────────

def _search_across_documents(
    documents: List[Dict[str, Any]],
    pattern: str,
    tool: str,
    context_lines: int,
) -> List[Dict[str, Any]]:
    """
    Run regex search across all documents.

    Args:
        documents: List of document dicts with 'content', 'file_path', 'original_filename'
        pattern: Regex pattern from nano model
        tool: "grep", "egrep", or "ripgrep" (all use Python re internally)
        context_lines: Lines of context before/after each match

    Returns:
        List of match dicts
    """
    # Compile regex (case-insensitive by default, matching grep -i behavior)
    try:
        compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        logger.debug("Invalid regex pattern '%s': %s", pattern, e)
        return []

    all_matches = []

    for doc in documents:
        content = doc.get("content", "")
        if not content:
            continue

        lines = content.split("\n")
        source_label = doc.get("original_filename") or doc.get("file_path", "unknown")

        for i, line in enumerate(lines):
            if compiled.search(line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)

                all_matches.append({
                    "file_path": doc.get("file_path", ""),
                    "source": source_label,
                    "line_num": i + 1,
                    "matched_line": line.strip(),
                    "context": "\n".join(lines[start:end]),
                    "context_start": start,
                    "context_end": end,
                    "metadata": doc.get("metadata", {}),
                    "collection_id": doc.get("collection_id", ""),
                })

    return all_matches


# ── Deduplication ───────────────────────────────────────────────────────────

def _deduplicate_matches(
    matches: List[Dict[str, Any]],
    context_lines: int,
) -> List[Dict[str, Any]]:
    """Deduplicate matches, merging overlapping context ranges per file."""
    if not matches:
        return []

    # Group by file_path
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for match in matches:
        fp = match.get("file_path", "__unknown__")
        by_file.setdefault(fp, []).append(match)

    merged = []
    for file_path, file_matches in by_file.items():
        # Sort by context_start
        file_matches.sort(key=lambda m: m.get("context_start", 0))

        file_merged = [dict(file_matches[0])]
        for match in file_matches[1:]:
            last = file_merged[-1]
            # If this match's context overlaps with the last, merge
            if match["context_start"] <= last["context_end"] + context_lines:
                # Merge by extending context range
                last["context_end"] = max(last["context_end"], match["context_end"])
                # Rebuild context from the merged range (approximate)
                last["matched_line"] = (
                    last.get("matched_line", "")
                    + " | "
                    + match.get("matched_line", "")
                )
            else:
                file_merged.append(dict(match))

        merged.extend(file_merged)

    return merged


# ── Context formatting ──────────────────────────────────────────────────────

def _build_grep_response(
    matches: List[Dict[str, Any]],
    documents: List[Dict[str, Any]],
    max_total_chars: int,
) -> Dict[str, Any]:
    """Build the final response dict from grep matches."""
    # Build file_path → metadata map for source resolution
    docs_map = {d["file_path"]: d for d in documents}

    blocks = []
    sources = []
    total_chars = 0
    seen_sources = set()

    for match in matches:
        meta = match.get("metadata", {})
        fp = match.get("file_path", "")

        # Resolve best source label
        source_label = _best_source_label(meta, match.get("source", "Unknown"))
        source_url = _best_source_url(meta)

        header = f"### {source_label}"
        if source_url:
            header += f" ({source_url})"

        body = match.get("context", "").strip()
        block = f"{header}\n{body}"

        if total_chars + len(block) > max_total_chars:
            break

        blocks.append(block)
        total_chars += len(block)

        # Track sources
        source_key = source_url or source_label
        if source_key not in seen_sources:
            sources.append({
                "title": source_label,
                "url": source_url,
            })
            seen_sources.add(source_key)

    context = "\n\n".join(blocks) if blocks else ""

    return {
        "context": context,
        "sources": sources,
    }


def _best_source_label(metadata: Dict[str, Any], fallback: str) -> str:
    """Resolve the best human-readable source label from metadata."""
    # Try various metadata fields in order of preference
    if isinstance(metadata, dict):
        # URL-ingested documents often have page_url
        if metadata.get("page_url"):
            return fallback  # fallback usually has filename
        # Check for original filename
        if metadata.get("original_filename"):
            return metadata["original_filename"]
        # Check processing stats
        stats = metadata.get("processing_stats", {})
        if isinstance(stats, dict):
            output_files = stats.get("output_files", {})
            if output_files:
                return fallback

    return fallback


def _best_source_url(metadata: Dict[str, Any]) -> str:
    """Resolve the best source URL for citation."""
    if isinstance(metadata, dict):
        stats = metadata.get("processing_stats", {})
        if isinstance(stats, dict):
            output_files = stats.get("output_files", {})
            # Prefer markdown URL
            if output_files.get("markdown_url"):
                return output_files["markdown_url"]
            if output_files.get("original_file_url"):
                return output_files["original_file_url"]

        # Fall back to file_url
        if metadata.get("file_url"):
            return metadata["file_url"]

    return ""


# ── RAG fallback ────────────────────────────────────────────────────────────

async def _run_fallback_rag(
    messages: List[Dict[str, Any]],
    assistant: Assistant,
    request: Optional[Dict[str, Any]],
    fallback_rag: str,
) -> Dict[str, Any]:
    """Run the specified fallback RAG processor."""
    import importlib

    try:
        module = importlib.import_module(
            f"lamb.completions.rag.{fallback_rag}"
        )
        rag_func = getattr(module, "rag_processor")

        if asyncio.iscoroutinefunction(rag_func):
            return await rag_func(
                messages=messages, assistant=assistant, request=request
            )
        else:
            return rag_func(
                messages=messages, assistant=assistant, request=request
            )
    except Exception as e:
        logger.error("Error running fallback RAG '%s': %s", fallback_rag, e)
        return {"context": "", "sources": []}


# ── Context merging ─────────────────────────────────────────────────────────

def _merge_contexts(
    grep_response: Dict[str, Any],
    rag_response: Dict[str, Any],
    max_total_chars: int,
) -> Dict[str, Any]:
    """Merge grep results with embedding RAG results."""
    rag_context = rag_response.get("context", "") if isinstance(rag_response, dict) else ""
    grep_context = grep_response.get("context", "") if isinstance(grep_response, dict) else ""

    rag_sources = rag_response.get("sources", []) if isinstance(rag_response, dict) else []
    grep_sources = grep_response.get("sources", []) if isinstance(grep_response, dict) else []

    # Combine contexts with a clear separator
    parts = []
    total = 0

    if rag_context:
        parts.append(rag_context)
        total += len(rag_context)

    if grep_context:
        remaining = max_total_chars - total
        if remaining > 200:  # Only add grep if there's meaningful space
            if parts:
                parts.append("\n\n---\n\n## Exact Keyword Matches\n\n")
                total += len(parts[-1])
            if len(grep_context) > remaining:
                grep_context = grep_context[:remaining] + "\n\n[... results truncated ...]"
            parts.append(grep_context)

    # Merge sources, deduplicating by URL
    merged_sources = list(rag_sources)
    seen_urls = {s.get("url", "") for s in rag_sources if s.get("url")}
    for s in grep_sources:
        if s.get("url") and s["url"] not in seen_urls:
            merged_sources.append(s)
            seen_urls.add(s["url"])

    return {
        "context": "".join(parts),
        "sources": merged_sources,
    }
