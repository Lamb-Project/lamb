"""
Load test for /v1/chat/completions endpoint.

Tests concurrent requests against the LAMB completion pipeline to verify
the shared HTTP client pool handles load without becoming unresponsive.

Usage:
    python3 load_test_completions.py --users 30 --url http://localhost:9099
"""

import asyncio
import aiohttp
import argparse
import time
import sys
import statistics


async def send_completion(session, url, api_key, model, user_id, results, prompt=None):
    """Send a single completion request and record the result."""
    content = prompt or f"User {user_id}: Say hello in exactly one word."
    if prompt:
        content = f"{prompt} (request {user_id})"
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": content}
        ],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.time()
    try:
        async with session.post(
            f"{url}/v1/chat/completions", json=payload, headers=headers
        ) as response:
            elapsed = time.time() - start
            body = await response.text()

            results.append({
                "user_id": user_id,
                "status": response.status,
                "elapsed": elapsed,
                "success": response.status == 200,
                "body_preview": body[:120] if response.status != 200 else "",
            })

            status_icon = "OK" if response.status == 200 else "FAIL"
            print(f"  User {user_id:3d}  {status_icon}  {response.status}  {elapsed:6.2f}s")

    except asyncio.TimeoutError:
        elapsed = time.time() - start
        results.append({
            "user_id": user_id,
            "status": 0,
            "elapsed": elapsed,
            "success": False,
            "body_preview": "TIMEOUT",
        })
        print(f"  User {user_id:3d}  TIMEOUT          {elapsed:6.2f}s")

    except Exception as e:
        elapsed = time.time() - start
        results.append({
            "user_id": user_id,
            "status": 0,
            "elapsed": elapsed,
            "success": False,
            "body_preview": str(e)[:120],
        })
        print(f"  User {user_id:3d}  ERROR            {elapsed:6.2f}s  {str(e)[:80]}")


async def run_load_test(url, api_key, model, num_users, request_timeout, custom_prompt=None):
    """Run the load test with the specified number of concurrent users."""
    print(f"\n{'='*65}")
    print(f"  LAMB Load Test - /v1/chat/completions")
    print(f"{'='*65}")
    print(f"  URL:              {url}")
    print(f"  Model:            {model}")
    print(f"  Concurrent users: {num_users}")
    print(f"  Request timeout:  {request_timeout}s")
    print(f"{'='*65}\n")

    # First, verify a single request works
    print("Pre-flight check: single request...")
    timeout = aiohttp.ClientTimeout(total=request_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        preflight = []
        await send_completion(session, url, api_key, model, 0, preflight, custom_prompt)
        if not preflight[0]["success"]:
            print(f"\nPre-flight FAILED: {preflight[0]}")
            print("Aborting load test. Fix single-request issues first.")
            return

    print(f"\nPre-flight OK ({preflight[0]['elapsed']:.2f}s). Starting load test...\n")

    # Run concurrent requests
    results = []
    start_all = time.time()

    timeout = aiohttp.ClientTimeout(total=request_timeout)
    connector = aiohttp.TCPConnector(limit=0)  # no connection limit on test client
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [
            send_completion(session, url, api_key, model, i + 1, results, custom_prompt)
            for i in range(num_users)
        ]
        await asyncio.gather(*tasks)

    total_elapsed = time.time() - start_all

    # Summary
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    response_times = [r["elapsed"] for r in results]
    success_times = [r["elapsed"] for r in successes]

    print(f"\n{'='*65}")
    print(f"  RESULTS")
    print(f"{'='*65}")
    print(f"  Total time:       {total_elapsed:.2f}s")
    print(f"  Requests sent:    {len(results)}")
    print(f"  Successful:       {len(successes)}")
    print(f"  Failed:           {len(failures)}")
    print(f"  Success rate:     {len(successes)/len(results)*100:.1f}%")
    print()

    if response_times:
        print(f"  Response times (all):")
        print(f"    Min:            {min(response_times):6.2f}s")
        print(f"    Max:            {max(response_times):6.2f}s")
        print(f"    Mean:           {statistics.mean(response_times):6.2f}s")
        print(f"    Median:         {statistics.median(response_times):6.2f}s")
        if len(response_times) > 1:
            print(f"    Std dev:        {statistics.stdev(response_times):6.2f}s")
        p90 = sorted(response_times)[int(len(response_times) * 0.9)]
        print(f"    P90:            {p90:6.2f}s")

    if success_times:
        print()
        print(f"  Response times (successes only):")
        print(f"    Min:            {min(success_times):6.2f}s")
        print(f"    Max:            {max(success_times):6.2f}s")
        print(f"    Mean:           {statistics.mean(success_times):6.2f}s")
        print(f"    Median:         {statistics.median(success_times):6.2f}s")

    if failures:
        print()
        print(f"  Failures:")
        for f in failures[:10]:
            print(f"    User {f['user_id']:3d}: status={f['status']} - {f['body_preview'][:80]}")
        if len(failures) > 10:
            print(f"    ... and {len(failures) - 10} more")

    print(f"{'='*65}\n")

    # Exit code: 0 if > 90% success, 1 otherwise
    if len(successes) / len(results) < 0.9:
        print("LOAD TEST FAILED (< 90% success rate)")
        sys.exit(1)
    else:
        print("LOAD TEST PASSED")


def main():
    parser = argparse.ArgumentParser(description="Load test LAMB /v1/chat/completions")
    parser.add_argument("--url", default="http://localhost:9099", help="LAMB backend URL")
    parser.add_argument("--api-key", default="0p3n-w3bu!", help="Bearer token")
    parser.add_argument("--model", default="lamb_assistant.58", help="Model/assistant ID")
    parser.add_argument("--users", type=int, default=30, help="Number of concurrent users")
    parser.add_argument("--timeout", type=int, default=180, help="Per-request timeout in seconds")
    parser.add_argument("--prompt", default=None, help="Custom prompt (overrides default short prompt)")
    args = parser.parse_args()

    asyncio.run(run_load_test(args.url, args.api_key, args.model, args.users, args.timeout, args.prompt))


if __name__ == "__main__":
    main()
