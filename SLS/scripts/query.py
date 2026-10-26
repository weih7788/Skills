#!/usr/bin/env python3
"""Read-only SLS MCP query; redact log messages only when requested."""

import argparse
import json
import os
import re
import select
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


PROJECT = {
    "beta": "k8s-log-onedata-beta",
    "prod": "k8s-log-onedata-prod",
}
LOGSTORE = "cube-robot-with-user"
CREDENTIALS = ("ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET")
REDACTION_SECRETS = []


def credentials_from_file(path):
    with open(path, encoding="utf-8") as source:
        content = source.read()
    values = {}
    for key in CREDENTIALS:
        match = re.search(r'^' + key + r'\s*=\s*"([^"]+)"\s*$', content, re.M)
        if not match:
            raise ValueError("Credential field missing: " + key)
        values[key] = match.group(1)
    return values


def sanitize(value, secrets):
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r'(?i)https?://[^\s"\\]+', '[URL]', value)
    value = re.sub(
        r'(?i)(["\x27](?:password|passwd|pwd|client_secret|access_key_secret)["\x27]\s*:\s*["\x27])([^"\x27]*)(["\x27])',
        r'\1[REDACTED]\3',
        value,
    )
    value = re.sub(
        r'(?i)\b((?:password|passwd|pwd|client_secret|access_key_secret)\s*=\s*)[^\s,;]+',
        r'\1[REDACTED]',
        value,
    )
    value = re.sub(r'(?i)(access_token|token|signature|authorization)([=:\\" ]+)[^,;\s"\\}]+', r'\1\2[REDACTED]', value)
    value = re.sub(r'\b1[3-9]\d{9}\b', '[PHONE]', value)
    value = re.sub(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', '[EMAIL]', value, flags=re.I)
    return value


def rpc(process, request_id, method, params, timeout):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    process.stdin.flush()
    readable, _, _ = select.select([process.stdout], [], [], timeout)
    if not readable:
        raise TimeoutError("SLS MCP response timed out")
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("SLS MCP proxy closed without response")
    response = json.loads(line)
    if "error" in response:
        raise RuntimeError("SLS MCP error: " + str(response["error"].get("message", "unknown")))
    return response.get("result", {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=PROJECT, required=True)
    parser.add_argument("--logstore", choices=("cube-robot-with-user", "middle-platform-log"), default=LOGSTORE)
    parser.add_argument("--from", dest="from_time", required=True)
    parser.add_argument("--to", dest="to_time", required=True)
    parser.add_argument("--query", required=True, help="Narrow SLS search expression; never use * over a large range")
    parser.add_argument("--lines", type=int, default=10)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--histogram", action="store_true")
    parser.add_argument("--include-message", action="store_true")
    parser.add_argument("--redact", action="store_true", help="Redact sensitive values in returned log messages")
    parser.add_argument("--full-message", action="store_true", help="Print the complete message of one identified log")
    parser.add_argument("--message-time", help="Exact log_time of the identified log")
    parser.add_argument("--message-class", help="Exact class of the identified log")
    parser.add_argument("--message-trace-id", help="Exact trace_id of the identified log")
    parser.add_argument("--credential-file", help="Private file path; credentials are never printed")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.lines <= 20:
        parser.error("--lines must be between 1 and 20")
    if args.query.strip() == "*":
        parser.error("Use a narrower query than *")
    selectors = (args.message_time, args.message_class, args.message_trace_id)
    if args.full_message and (args.histogram or not all(selectors)):
        parser.error("--full-message requires --message-time, --message-class, and --message-trace-id without --histogram")
    if any(selectors) and not args.full_message:
        parser.error("Message selectors require --full-message")

    env = os.environ.copy()
    credential_file = args.credential_file
    if not credential_file and any(not env.get(key) for key in CREDENTIALS):
        local_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "private-credentials.env")
        if os.path.isfile(local_file):
            credential_file = local_file
    if credential_file:
        env.update(credentials_from_file(credential_file))
    if any(not env.get(key) for key in CREDENTIALS):
        parser.error("Provide credentials in environment or --credential-file")
    secrets = [env[key] for key in CREDENTIALS]
    REDACTION_SECRETS[:] = secrets
    process = subprocess.Popen(
        [sys.executable, "-m", "alibabacloud_sls_mcp_proxy"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        env=env,
    )
    try:
        rpc(process, 1, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "sls-skill", "version": "1.0"}}, args.timeout)
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()
        arguments = {"project": PROJECT[args.env], "logstore": args.logstore, "from": args.from_time, "to": args.to_time, "query": args.query}
        if args.histogram:
            tool = "sls_get_log_histogram"
        else:
            tool = "sls_query_logs"
            arguments.update({"lines": args.lines, "reverse": args.reverse})
        response = rpc(process, 2, "tools/call", {"name": tool, "arguments": arguments}, args.timeout)
        if response.get("isError"):
            details = " ".join(part.get("text", "") for part in response.get("content", []) if part.get("type") == "text")
            raise RuntimeError(sanitize(details[:500], secrets))
        print(json.dumps({"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "environment": args.env, "project": PROJECT[args.env], "logstore": args.logstore, "from": args.from_time, "to": args.to_time, "query": args.query}, ensure_ascii=False))
        for part in response.get("content", []):
            if part.get("type") != "text":
                continue
            data = json.loads(part["text"])
            print(json.dumps({key: data.get(key) for key in ("progress", "count", "total_count") if key in data}, ensure_ascii=False))
            if args.histogram:
                print(json.dumps(data.get("histograms", data.get("histogram", [])), ensure_ascii=False))
                continue
            for row in data.get("logs", []):
                if args.full_message and (
                    row.get("log_time") != args.message_time
                    or row.get("class") != args.message_class
                    or row.get("trace_id") != args.message_trace_id
                ):
                    continue
                item = {key: row.get(key) for key in ("log_time", "__time__", "app", "class", "level", "trace_id") if row.get(key) is not None}
                if args.include_message or args.full_message:
                    message = row.get("message", "")
                    for secret in secrets:
                        if secret:
                            message = message.replace(secret, "[REDACTED CONNECTION CREDENTIAL]")
                    if args.redact:
                        message = sanitize(message, secrets)
                    item["message"] = message if args.full_message else message[:2000]
                    item["message_truncated"] = not args.full_message and len(message) > 2000
                print(json.dumps(item, ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        print("SLS query failed: " + sanitize(str(exc), REDACTION_SECRETS), file=sys.stderr)
        sys.exit(1)
