#!/usr/bin/env python3
"""
LAMB Database Stress Test - SQLite Capacity Testing

This script stress-tests the LAMB backend by sending concurrent requests
to the assistant chat endpoint, forcing SQLite write contention.

Usage:
    python stress_test_db.py --vus 50 --requests 100
    python stress_test_db.py --vus 100 --duration 60 --output results.json

Environment variables required:
    API_BASE_URL    - LAMB API base URL (e.g., http://localhost:9099)
    JWT_TOKEN       - User authentication token
    ASSISTANT_ID    - Assistant ID to test against
"""

import os
import sys
import json
import time
import statistics
import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import asyncio
import requests
from urllib.parse import urlparse


def load_env_file(path: str) -> bool:
    """Load environment variables from a .env file. Returns True if loaded."""
    if not path or not os.path.isfile(path):
        return False

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    return True


class DatabaseStressTest:
    """Stress test LAMB database with concurrent requests."""
    
    def __init__(
        self,
        env_file: str = None,
        api_base_url: str = None,
        endpoint_path: str = None,
        auth_token: str = None,
        disable_auth: bool = False,
        check_server: bool = True,
        response_body_max_chars: int = None,
        prompt: str = 'Hello',
    ):
        """Initialize test configuration from environment variables.

        The `prompt` parameter sets the user message sent in each request. Default: "Hello".
        """
        if env_file:
            load_env_file(env_file)
        self._try_default_envs()
        self.api_base_url = api_base_url or os.getenv('MOCK_OPENAI_BASE_URL') or os.getenv('API_BASE_URL')
        self.endpoint_path = endpoint_path
        self.jwt_token = auth_token if auth_token is not None else os.getenv('JWT_TOKEN')
        self.assistant_id = os.getenv('ASSISTANT_ID')
        self.disable_auth = disable_auth
        # Whether to perform a server readiness check before running
        self.check_server = check_server and (os.getenv('NO_SERVER_CHECK', 'false').lower() not in ('1','true','yes'))
        # How many characters of the response body to store per request (None means no limit)
        env_max = os.getenv('RESPONSE_BODY_MAX_CHARS')
        if response_body_max_chars is not None:
            self.response_body_max_chars = response_body_max_chars
        elif env_max:
            try:
                self.response_body_max_chars = int(env_max)
            except Exception:
                self.response_body_max_chars = 10000
        else:
            self.response_body_max_chars = 10000

        # prompt (message content) to send with each request; default 'Hello'
        env_prompt = os.getenv('STRESS_PROMPT')
        self.prompt = prompt if prompt is not None else (env_prompt or 'Hello')

        self._validate_config()

    def _build_endpoint(self) -> str:
        """Build endpoint URL, optionally overriding the path."""
        if self.endpoint_path:
            if '{assistant_id}' in self.endpoint_path:
                path = self.endpoint_path.format(assistant_id=self.assistant_id)
            else:
                path = self.endpoint_path
            return f"{self.api_base_url.rstrip('/')}/{path.lstrip('/')}"

        return f"{self.api_base_url}/creator/assistant/{self.assistant_id}/chat/completions"

    def _try_default_envs(self):
        """Try loading common .env locations if variables are missing."""
        if os.getenv('API_BASE_URL') and os.getenv('JWT_TOKEN') and os.getenv('ASSISTANT_ID'):
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(script_dir, '.env'),
            os.path.join(script_dir, '..', '..', 'backend', '.env'),
            os.path.join(script_dir, '..', '..', 'lamb-kb-server-stable', 'backend', '.env'),
        ]

        for path in candidates:
            if load_env_file(os.path.abspath(path)):
                if os.getenv('API_BASE_URL') and os.getenv('JWT_TOKEN') and os.getenv('ASSISTANT_ID'):
                    return

    def _validate_config(self):
        """Validate required environment variables and URL format."""
        missing = []
        if not self.api_base_url:
            missing.append('API_BASE_URL')
        if not self.jwt_token and not self.disable_auth:
            missing.append('JWT_TOKEN')
        if not self.assistant_id:
            missing.append('ASSISTANT_ID')

        if missing:
            print("Error: Missing required environment variables:")
            for name in missing:
                print(f"  - {name}")
            print("\nSet them before running, e.g.:")
            print("  API_BASE_URL=http://localhost:9099")
            print("  JWT_TOKEN=...")
            print("  ASSISTANT_ID=1")
            sys.exit(1)

        parsed = urlparse(self.api_base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            print("Error: API_BASE_URL must include a valid scheme and host, e.g. http://localhost:9099")
            sys.exit(1)

    def check_server_ready(self, attempts: int = 3, timeout: int = 5, wait_between: float = 1.0, verbose: bool = False) -> bool:
        """Check server readiness by probing the base URL and the assistant endpoint.
        Returns True if the server responds (even with 4xx/405), False otherwise.
        """
        if not self.api_base_url:
            if verbose:
                print("Server check skipped: API base URL is not set")
            return False

        endpoints = [self.api_base_url.rstrip('/')]
        try:
            endpoints.append(self._build_endpoint())
        except Exception:
            pass

        for attempt in range(1, attempts + 1):
            if verbose:
                print(f"  Checking server (attempt {attempt}/{attempts})...")
            for url in endpoints:
                try:
                    # lightweight probe: OPTIONS or HEAD; accept 2xx-4xx as 'server up'
                    try:
                        resp = requests.options(url, timeout=timeout)
                    except Exception:
                        resp = None
                    if resp is not None and resp.status_code < 500:
                        if verbose:
                            print(f"    {url} -> {resp.status_code}")
                        return True
                    try:
                        resp = requests.head(url, timeout=timeout)
                    except Exception:
                        resp = None
                    if resp is not None and resp.status_code < 500:
                        if verbose:
                            print(f"    {url} -> {resp.status_code}")
                        return True
                    # final fallback: try GET
                    resp = requests.get(url, timeout=timeout)
                    if resp.status_code < 500:
                        if verbose:
                            print(f"    {url} -> {resp.status_code}")
                        return True
                except requests.RequestException:
                    # try next endpoint
                    continue
            time.sleep(wait_between)
        return False

    def _fetch_embedding_model(self, timeout: int = 10) -> str:
        """Fetch embedding model via configured endpoints. Returns empty string if unavailable."""
        candidates = []
        config_url = os.getenv('EMBEDDINGS_CONFIG_URL') or os.getenv('KB_EMBEDDINGS_CONFIG_URL')
        if config_url:
            token = (
                os.getenv('EMBEDDINGS_CONFIG_TOKEN')
                or os.getenv('KB_EMBEDDINGS_CONFIG_TOKEN')
                or os.getenv('KB_API_KEY')
                or os.getenv('KB_SERVER_API_KEY')
                or self.jwt_token
            )
            candidates.append((config_url, token))

        if self.api_base_url:
            proxy_url = f"{self.api_base_url}/creator/admin/org-admin/settings/kb/embeddings-config"
            candidates.append((proxy_url, self.jwt_token))

        for url, token in candidates:
            try:
                headers = {}
                if token:
                    headers['Authorization'] = f"Bearer {token}"
                response = requests.get(url, headers=headers, timeout=timeout)
                if not response.ok:
                    continue
                data = response.json()
                if isinstance(data, dict):
                    if isinstance(data.get('embeddings_model'), dict):
                        model = data['embeddings_model'].get('model')
                        if model:
                            return model
                    if isinstance(data.get('embeddings'), dict):
                        model = data['embeddings'].get('model')
                        if model:
                            return model
                    model = data.get('model')
                    if model:
                        return model
            except Exception:
                continue
        return ''
    
    def _make_request(self, session: requests.Session, timeout: int = 120) -> Dict[str, Any]:
        """
        Send a single request to the assistant chat endpoint.
        
        Returns dict with:
            - status_code: HTTP status
            - latency_ms: Request duration in milliseconds
            - success: True if 2xx response
            - error: Error message or None
            - timestamp: ISO timestamp
        """
        endpoint = self._build_endpoint()
        headers = {
            'Content-Type': 'application/json'
        }
        if not self.disable_auth and self.jwt_token:
            headers['Authorization'] = f'Bearer {self.jwt_token}'
        payload = {
            'messages': [{'role': 'user', 'content': self.prompt}],
            'stream': False
        }
        
        start = time.time()
        
        try:
            response = session.post(endpoint, json=payload, headers=headers, timeout=timeout)
            latency_ms = (time.time() - start) * 1000
            
            model = None
            # capture response body (text) when available, but truncate to avoid huge files
            response_text = None
            response_truncated = False
            content_type = response.headers.get('Content-Type', '')
            is_text = content_type.lower().startswith('application/json') or content_type.lower().startswith('text/')
            if is_text:
                try:
                    text = response.text
                    if self.response_body_max_chars and len(text) > self.response_body_max_chars:
                        response_text = text[:self.response_body_max_chars]
                        response_truncated = True
                    else:
                        response_text = text
                except Exception:
                    response_text = None

            if content_type.lower().startswith('application/json'):
                try:
                    payload_json = response.json()
                    if isinstance(payload_json, dict):
                        model = payload_json.get('model')
                except Exception:
                    model = None

            return {
                'status_code': response.status_code,
                'latency_ms': latency_ms,
                'success': 200 <= response.status_code < 300,
                'error': None,
                'model': model,
                'response_text': response_text,
                'response_truncated': response_truncated,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except requests.Timeout:
            latency_ms = (time.time() - start) * 1000
            return {
                'status_code': 0,
                'latency_ms': latency_ms,
                'success': False,
                'error': 'Timeout',
                'model': None,
                'response_text': None,
                'response_truncated': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return {
                'status_code': 0,
                'latency_ms': latency_ms,
                'success': False,
                'error': str(e),
                'model': None,
                'response_text': None,
                'response_truncated': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    # ------------------ Async (aiohttp) helpers ------------------
    async def _make_request_async(self, session: "aiohttp.ClientSession", timeout: int = 120) -> Dict[str, Any]:
        """Async equivalent of _make_request using aiohttp."""
        endpoint = self._build_endpoint()
        headers = {
            'Content-Type': 'application/json'
        }
        if not self.disable_auth and self.jwt_token:
            headers['Authorization'] = f'Bearer {self.jwt_token}'
        payload = {
            'messages': [{'role': 'user', 'content': self.prompt}],
            'stream': False
        }

        start = time.time()
        try:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                latency_ms = (time.time() - start) * 1000

                model = None
                response_text = None
                response_truncated = False
                content_type = response.headers.get('Content-Type', '')
                is_text = content_type.lower().startswith('application/json') or content_type.lower().startswith('text/')
                if is_text:
                    try:
                        text = await response.text()
                        if self.response_body_max_chars and len(text) > self.response_body_max_chars:
                            response_text = text[:self.response_body_max_chars]
                            response_truncated = True
                        else:
                            response_text = text
                    except Exception:
                        response_text = None

                if content_type.lower().startswith('application/json'):
                    try:
                        payload_json = await response.json()
                        if isinstance(payload_json, dict):
                            model = payload_json.get('model')
                    except Exception:
                        model = None

                return {
                    'status_code': response.status,
                    'latency_ms': latency_ms,
                    'success': 200 <= response.status < 300,
                    'error': None,
                    'model': model,
                    'response_text': response_text,
                    'response_truncated': response_truncated,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start) * 1000
            return {
                'status_code': 0,
                'latency_ms': latency_ms,
                'success': False,
                'error': 'Timeout',
                'model': None,
                'response_text': None,
                'response_truncated': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return {
                'status_code': 0,
                'latency_ms': latency_ms,
                'success': False,
                'error': str(e),
                'model': None,
                'response_text': None,
                'response_truncated': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    async def run_test_async(self, vus: int, total_requests: int = None, duration: int = None, timeout: int = 120, csv_file: str = None, responses_file: str = None, verbose: bool = False) -> List[Dict]:
        """Async-runner: spawns `vus` worker coroutines that reuse a shared aiohttp ClientSession.

        Workers loop until `total_requests` is reached or `duration` expires. Results are
        appended to the same output format as the sync runner.
        """
        import math
        results: List[Dict[str, Any]] = []
        embedding_model = self._fetch_embedding_model()

        # prepare output files (same semantics as sync runner)
        responses_handle = None
        csv_writer = None
        csv_handle = None
        if csv_file:
            try:
                mode = 'a' if os.path.exists(csv_file) else 'w'
                csv_handle = open(csv_file, mode, newline='', encoding='utf-8')
                csv_writer = csv.writer(csv_handle)
                if mode == 'w':
                    csv_writer.writerow(['index', 'assistant_id', 'model', 'embedding_model', 'total_requests', 'vus', 'max_time', 'total_time', 'success_pct', 'error'])
                    csv_handle.flush()
            except Exception as e:
                print(f"Warning: Could not open CSV file {csv_file}: {e}")
                csv_handle = None
                csv_writer = None
        if responses_file:
            try:
                mode = 'a' if os.path.exists(responses_file) else 'w'
                responses_handle = open(responses_file, mode, encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not open responses file {responses_file}: {e}")
                responses_handle = None

        start_time = time.time()
        stop_time = start_time + duration if duration else None
        counter = 0
        counter_lock = asyncio.Lock()

        # lazy import so script can run in sync mode without aiohttp installed
        try:
            import aiohttp
        except ImportError:
            print("Error: aiohttp is required for async mode. Install with: pip install aiohttp")
            sys.exit(1)

        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        connector = aiohttp.TCPConnector(limit=0)
        async with aiohttp.ClientSession(timeout=timeout_obj, connector=connector) as session:

            async def worker(worker_id: int):
                nonlocal counter
                while True:
                    # termination checks
                    if stop_time and time.time() > stop_time:
                        return
                    async with counter_lock:
                        if total_requests is not None and counter >= total_requests:
                            return
                        counter += 1
                        req_num = counter
                    # perform request using the shared session
                    res = await self._make_request_async(session, timeout)
                    results.append(res)

                    # write per-request JSONL if requested
                    if responses_handle:
                        try:
                            responses_handle.write(json.dumps(res, default=str) + '\n')
                            responses_handle.flush()
                            try:
                                os.fsync(responses_handle.fileno())
                            except Exception:
                                pass
                        except Exception as e:
                            if verbose:
                                print(f"Warning: Could not write to responses file: {e}")

                    # exit early if request-count reached
                    if total_requests is not None and counter >= total_requests:
                        return

            # start worker coroutines
            tasks = [asyncio.create_task(worker(i)) for i in range(vus)]
            await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # finalize CSV summary if requested
        if csv_writer:
            try:
                stats_summary = self.analyze_results(results)
                if total_requests is not None:
                    total_req_val = total_requests
                else:
                    total_req_val = f"duration:{int(duration)}" if duration else 'N/A'
                try:
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        lines = sum(1 for _ in f)
                    next_index = lines if lines >= 1 else 1
                except Exception:
                    next_index = 1
                errors = stats_summary.get('errors', {})
                error_summary = '; '.join([f"{k}({v})" for k, v in errors.items()]) if errors else ''
                success_pct = (stats_summary['successful'] / stats_summary['total_requests'] * 100) if stats_summary['total_requests'] else 0.0
                model_values = [r.get('model') for r in results if r.get('model')]
                model_summary = Counter(model_values).most_common(1)[0][0] if model_values else ''
                csv_writer.writerow([
                    next_index,
                    self.assistant_id,
                    model_summary,
                    embedding_model,
                    total_req_val,
                    vus,
                    int(timeout) if timeout is not None else '',
                    f"{total_time:.2f}",
                    f"{success_pct:.2f}",
                    error_summary
                ])
                csv_handle.flush()
                try:
                    os.fsync(csv_handle.fileno())
                except Exception:
                    pass
            except Exception as e:
                print(f"Warning: Could not write summary to CSV: {e}")
            try:
                csv_handle.close()
            except Exception:
                pass

        if responses_handle:
            try:
                responses_handle.close()
            except Exception:
                pass

        return results
    
    def run_test(self, vus: int, total_requests: int = None, duration: int = None, timeout: int = 120, csv_file: str = None, responses_file: str = None, verbose: bool = False, use_async: bool = True) -> List[Dict]:
        """
        Run stress test with specified concurrency.

        Notes:
        - Default behaviour is **async** (`aiohttp`) runner for better connection reuse and scalability.
        - Pass `use_async=False` (CLI `--sync`) to run the legacy threaded `requests` runner.

        Args:
            vus: Virtual users (concurrent threads/coroutines)
            total_requests: Total requests to send (or None for duration-based)
            duration: Test duration in seconds (or None for request-based)
            timeout: Request timeout in seconds
            csv_file: Path to CSV file to write results progressively (optional)
            responses_file: Path to JSON Lines file where each request response will be appended
            verbose: Print detailed logs
            use_async: When True (default), run the aiohttp-based async runner

        Returns:
            List of request results
        """
        # delegate to async runner when requested (async is default)
        if use_async:
            return asyncio.run(self.run_test_async(vus, total_requests, duration, timeout, csv_file, responses_file, verbose))

        print(f"\n{'='*70}")
        print("DATABASE STRESS TEST - STARTING")
        print(f"{'='*70}")
        print(f"\nConfiguration:")
        print(f"  API URL:      {self.api_base_url}")
        print(f"  Assistant ID: {self.assistant_id}")
        print(f"  VUs:          {vus} concurrent users")
        if total_requests:
            print(f"  Requests:     {total_requests} total")
        if duration:
            print(f"  Duration:     {duration} seconds")
        if timeout:
            print(f"  Timeout:      {timeout} seconds")
        if csv_file:
            print(f"  CSV output:   {csv_file}")
        if responses_file:
            print(f"  Responses:     {responses_file}")
        print()

        # Check server readiness if enabled
        if self.check_server:
            print("Checking server readiness...")
            if not self.check_server_ready(verbose=verbose):
                print("Error: Server does not appear to be ready. Aborting test.")
                sys.exit(1)
        
        results = []
        embedding_model = self._fetch_embedding_model()
        csv_handle = None
        csv_writer = None
        responses_handle = None
        if csv_file:
            try:
                mode = 'a' if os.path.exists(csv_file) else 'w'
                csv_handle = open(csv_file, mode, newline='', encoding='utf-8')
                csv_writer = csv.writer(csv_handle)
                # write header only when creating new file
                if mode == 'w':
                    csv_writer.writerow(['index', 'assistant_id', 'model', 'embedding_model', 'total_requests', 'vus', 'max_time', 'total_time', 'success_pct', 'error'])
                    csv_handle.flush()
                    try:
                        os.fsync(csv_handle.fileno())
                    except Exception:
                        pass
            except Exception as e:
                print(f"Warning: Could not open CSV file {csv_file}: {e}")
                csv_handle = None
                csv_writer = None

        if responses_file:
            try:
                mode = 'a' if os.path.exists(responses_file) else 'w'
                responses_handle = open(responses_file, mode, encoding='utf-8')
                # JSON Lines file - no header necessary
            except Exception as e:
                print(f"Warning: Could not open responses file {responses_file}: {e}")
                responses_handle = None
        start_time = time.time()
        request_count = 0
        
        with ThreadPoolExecutor(max_workers=vus) as executor:
            futures = {}
            
            while True:
                elapsed = time.time() - start_time
                
                # Check termination conditions
                if duration and elapsed > duration:
                    break
                if total_requests and request_count >= total_requests:
                    break
                
                # Submit requests up to VU limit
                while len(futures) < vus:
                    if not total_requests or request_count < total_requests:
                        session = requests.Session()
                        future = executor.submit(self._make_request, session, timeout)
                        futures[future] = time.time()
                        request_count += 1
                
                # Collect completed requests
                completed = []
                try:
                    for future in as_completed(futures.keys(), timeout=1):
                        result = future.result()
                        results.append(result)
                        completed.append(future)

                        # write each response to the responses file (JSONL) if enabled
                        if responses_handle:
                            try:
                                responses_handle.write(json.dumps(result, default=str) + '\n')
                                responses_handle.flush()
                                try:
                                    os.fsync(responses_handle.fileno())
                                except Exception:
                                    pass
                            except Exception as e:
                                if verbose:
                                    print(f"Warning: Could not write to responses file: {e}")

                        # per-request CSV writing removed; summary row will be written at end of test

                        if verbose and len(results) % 10 == 0:
                            print(f"  [+] Completed {len(results)} requests")
                except TimeoutError:
                    pass
                
                for future in completed:
                    del futures[future]
                
                time.sleep(0.01)  # Small delay to avoid overwhelming
            
            # Wait for remaining
            if futures:
                print(f"\nWaiting for {len(futures)} pending requests...")
                for future in as_completed(futures.keys()):
                    result = future.result()
                    results.append(result)
                    # write each response to the responses file (JSONL) if enabled
                    if responses_handle:
                        try:
                            responses_handle.write(json.dumps(result, default=str) + '\n')
                            responses_handle.flush()
                            try:
                                os.fsync(responses_handle.fileno())
                            except Exception:
                                pass
                        except Exception as e:
                            if verbose:
                                print(f"Warning: Could not write to responses file: {e}")
            # compute total time after all requests completed
            total_time = time.time() - start_time
        if csv_writer:
            try:
                stats_summary = self.analyze_results(results)
                # total_requests or duration label
                if total_requests is not None:
                    total_req_val = total_requests
                else:
                    total_req_val = f"duration:{int(duration)}" if duration else 'N/A'

                # compute next index based on existing file lines (header + data rows)
                try:
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        lines = sum(1 for _ in f)
                    next_index = lines if lines >= 1 else 1
                except Exception:
                    next_index = 1

                # summarize errors
                errors = stats_summary.get('errors', {})
                if errors:
                    error_summary = '; '.join([f"{k}({v})" for k, v in errors.items()])
                else:
                    error_summary = ''

                success_pct = (stats_summary['successful'] / stats_summary['total_requests'] * 100) if stats_summary['total_requests'] else 0.0

                model_values = [r.get('model') for r in results if r.get('model')]
                model_summary = ''
                if model_values:
                    model_summary = Counter(model_values).most_common(1)[0][0]

                csv_writer.writerow([
                    next_index,
                    self.assistant_id,
                    model_summary,
                    embedding_model,
                    total_req_val,
                    vus,
                    int(timeout) if timeout is not None else '',
                    f"{total_time:.2f}",
                    f"{success_pct:.2f}",
                    error_summary
                ])
                csv_handle.flush()
                try:
                    os.fsync(csv_handle.fileno())
                except Exception:
                    pass
            except Exception as e:
                print(f"Warning: Could not write summary to CSV: {e}")

            try:
                csv_handle.close()
            except Exception:
                pass

        # close responses file handle if opened
        if responses_handle:
            try:
                responses_handle.close()
            except Exception:
                pass
        return results
    
    def analyze_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Analyze test results."""
        if not results:
            return {'error': 'No results'}
        
        latencies = [r['latency_ms'] for r in results]
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        status_codes = {}
        errors = {}
        for r in results:
            code = r['status_code']
            status_codes[code] = status_codes.get(code, 0) + 1
            
            if r['error']:
                errors[r['error']] = errors.get(r['error'], 0) + 1
        
        return {
            'total_requests': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'error_rate_percent': (len(failed) / len(results)) * 100 if results else 0,
            'status_codes': status_codes,
            'errors': errors,
            'latency_ms': {
                'min': min(latencies),
                'max': max(latencies),
                'mean': statistics.mean(latencies),
                'median': statistics.median(latencies),
                'p95': sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
                'p99': sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
                'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0,
            }
        }
    
    def print_results(self, stats: Dict[str, Any]):
        """Print formatted results."""
        print(f"\n{'='*70}")
        print("RESULTS")
        print(f"{'='*70}\n")
        
        print(f"Requests:     {stats['total_requests']} total")
        print(f"Successful:   {stats['successful']} ({100 - stats['error_rate_percent']:.1f}%)")
        print(f"Failed:       {stats['failed']} ({stats['error_rate_percent']:.1f}%)")
        
        if stats['status_codes']:
            print(f"\nStatus Codes:")
            for code in sorted(stats['status_codes'].keys()):
                count = stats['status_codes'][code]
                pct = (count / stats['total_requests']) * 100
                print(f"  {code}: {count} ({pct:.1f}%)")
        
        if stats['errors']:
            print(f"\nErrors Observed:")
            for error, count in sorted(stats['errors'].items(), key=lambda x: -x[1]):
                pct = (count / stats['total_requests']) * 100
                print(f"  {error}: {count} ({pct:.1f}%)")
        
        lat = stats['latency_ms']
        print(f"\nLatency (milliseconds):")
        print(f"  Min:        {lat['min']:>10.2f}")
        print(f"  Mean:       {lat['mean']:>10.2f}")
        print(f"  Median:     {lat['median']:>10.2f}")
        print(f"  P95:        {lat['p95']:>10.2f}")
        print(f"  P99:        {lat['p99']:>10.2f}")
        print(f"  Max:        {lat['max']:>10.2f}")
        print(f"  Std Dev:    {lat['stdev']:>10.2f}")
        
        print(f"\n{'='*70}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='LAMB Database Stress Test',
        epilog='''Examples:
  python stress_test_db.py --vus 50 --requests 100
  python stress_test_db.py --vus 100 --duration 60 --output results.json
  python stress_test_db.py --vus 200 --requests 500 --verbose
        '''
    )
    
    parser.add_argument('--vus', type=int, required=True, help='Concurrent virtual users')
    parser.add_argument('--requests', type=int, default=None, help='Total requests (or use --duration)')
    parser.add_argument('--duration', type=int, default=None, help='Test duration in seconds')
    parser.add_argument('--timeout', type=int, default=120, help='Request timeout in seconds (default 120)')
    parser.add_argument('--csv', type=str, default=None, help='CSV output file to write results progressively')
    parser.add_argument('--responses', type=str, default=None, help='Write per-request responses as JSON Lines to this file')
    parser.add_argument('--response-max-chars', type=int, default=None, help='Maximum number of characters of response body to save per request (default 10000)')
    parser.add_argument('--output', type=str, default=None, help='JSON output file')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--env-file', type=str, default=None, help='Path to .env file')
    parser.add_argument('--api-base-url', type=str, default=None, help='Override API base URL (e.g. http://localhost:9099)')
    parser.add_argument('--endpoint-path', type=str, default=None, help='Override endpoint path (e.g. /v1/chat/completions)')
    parser.add_argument('--auth-token', type=str, default=None, help='Override auth token (Bearer)')
    parser.add_argument('--no-auth', action='store_true', help='Disable Authorization header')
    parser.add_argument('--no-check', action='store_true', help='Skip server readiness check')
    parser.add_argument('--prompt', type=str, default='Hello', help='Custom prompt/message to send with each request (default: "Hello")')
    parser.add_argument('--async', dest='use_async', action='store_true', help='Use asyncio/aiohttp for concurrency (more efficient, reuses connections) (default)')
    parser.add_argument('--sync', dest='use_async', action='store_false', help='Run the legacy sync/threaded requests runner instead of async')
    parser.set_defaults(use_async=True)
    
    args = parser.parse_args()
    
    if not args.requests and not args.duration:
        print("Error: Specify either --requests or --duration")
        sys.exit(1)
    
    # Run test
    test = DatabaseStressTest(
        env_file=args.env_file,
        api_base_url=args.api_base_url,
        endpoint_path=args.endpoint_path,
        auth_token=args.auth_token,
        disable_auth=args.no_auth,
        check_server=not args.no_check,
        response_body_max_chars=args.response_max_chars,
        prompt=args.prompt
    )

    # perform a quick server readiness check before running the load if enabled
    if test.check_server:
        print("\nChecking server readiness before starting test...")
        if not test.check_server_ready(verbose=args.verbose):
            print("Error: Server does not appear to be ready. Aborting.")
            sys.exit(1)

    results = test.run_test(
        vus=args.vus,
        total_requests=args.requests,
        duration=args.duration,
        timeout=args.timeout,
        csv_file=args.csv,
        responses_file=args.responses,
        verbose=args.verbose,
        use_async=args.use_async
    )
    
    # Analyze
    stats = test.analyze_results(results)
    test.print_results(stats)
    
    # Save results
    if args.output:
        output_data = {
            'metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'api_url': test.api_base_url,
                'assistant_id': test.assistant_id,
                'vus': args.vus,
                'total_requests': args.requests,
                'duration': args.duration,
                'timeout': args.timeout,
            },
            'statistics': stats,
            'raw_results': results
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"Results saved to: {args.output}")
    
    # Exit code
    if stats['error_rate_percent'] > 5:
        print(f"\n⚠️  Warning: High error rate ({stats['error_rate_percent']:.1f}%)")
        sys.exit(1)
    else:
        print("✓ Test completed")
        sys.exit(0)


if __name__ == '__main__':
    main()
