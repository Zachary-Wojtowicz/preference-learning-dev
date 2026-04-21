"""
discover_servers.py — Auto-discover running vLLM servers on localhost.

Probes a range of ports for OpenAI-compatible /v1/models endpoints,
classifies each as 'embed' or 'instruct' based on model name, and
returns comma-separated URLs ready for --base-url.

Usage as a library:
    from discover_servers import discover
    urls = discover(server_type="instruct")  # "http://localhost:8004/v1,..."

Usage as a CLI:
    python discover_servers.py                    # show all servers
    python discover_servers.py --type instruct    # print instruct URLs only
    python discover_servers.py --type embed       # print embed URLs only

Usage in shell command substitution:
    --base-url $(python discover_servers.py --type instruct)
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

# Port range to scan
PORT_MIN = 8000
PORT_MAX = 8020
TIMEOUT = 1.0  # seconds per probe

# Keywords that identify embedding models (case-insensitive)
EMBED_KEYWORDS = ["embedding", "embed", "gte-"]


def probe_port(port, timeout=TIMEOUT):
    """Probe a single port for a vLLM server.

    Returns (port, model_id, server_type) or None if no server found.
    """
    url = f"http://localhost:{port}/v1/models"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            if not models:
                return None
            model_id = models[0].get("id", "unknown")

            # Classify based on model name
            model_lower = model_id.lower()
            if any(kw in model_lower for kw in EMBED_KEYWORDS):
                server_type = "embed"
            else:
                server_type = "instruct"

            return (port, model_id, server_type)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None


def discover(server_type=None, port_min=PORT_MIN, port_max=PORT_MAX,
             timeout=TIMEOUT):
    """Discover running vLLM servers and return comma-separated base URLs.

    Args:
        server_type: "embed", "instruct", or None (return all)
        port_min: start of port range to scan
        port_max: end of port range to scan (inclusive)
        timeout: seconds to wait per port probe

    Returns:
        Comma-separated string of base URLs, e.g.
        "http://localhost:8004/v1,http://localhost:8005/v1"
        Returns empty string if no servers found.
    """
    servers = discover_all(port_min, port_max, timeout)
    if server_type:
        servers = [s for s in servers if s[2] == server_type]
    return ",".join(f"http://localhost:{port}/v1" for port, _, _ in servers)


def discover_all(port_min=PORT_MIN, port_max=PORT_MAX, timeout=TIMEOUT):
    """Discover all running vLLM servers.

    Returns list of (port, model_id, server_type) tuples.
    """
    servers = []
    for port in range(port_min, port_max + 1):
        result = probe_port(port, timeout)
        if result:
            servers.append(result)
    return servers


def require(server_type, port_min=PORT_MIN, port_max=PORT_MAX, timeout=TIMEOUT):
    """Discover servers of a given type, raising an error if none found.

    Returns comma-separated base URLs.
    """
    urls = discover(server_type, port_min, port_max, timeout)
    if not urls:
        all_servers = discover_all(port_min, port_max, timeout)
        if all_servers:
            available = ", ".join(
                f"{model} ({stype}) on :{port}"
                for port, model, stype in all_servers
            )
            raise RuntimeError(
                f"No {server_type} servers found, but found: {available}"
            )
        else:
            raise RuntimeError(
                f"No vLLM servers found on ports {port_min}-{port_max}. "
                f"Run './serve.sh up' first."
            )
    return urls


# --- CLI ---

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--type", choices=["embed", "instruct"],
                   help="Filter by server type")
    p.add_argument("--port-min", type=int, default=PORT_MIN)
    p.add_argument("--port-max", type=int, default=PORT_MAX)
    p.add_argument("--quiet", "-q", action="store_true",
                   help="Print only the comma-separated URLs (for shell substitution)")
    args = p.parse_args()

    servers = discover_all(args.port_min, args.port_max)

    if not servers:
        if not args.quiet:
            print("No vLLM servers found.", file=sys.stderr)
        sys.exit(1)

    if args.type:
        filtered = [s for s in servers if s[2] == args.type]
    else:
        filtered = servers

    if args.quiet:
        urls = ",".join(f"http://localhost:{port}/v1" for port, _, _ in filtered)
        print(urls)
    else:
        print(f"Found {len(servers)} server(s):\n")
        for port, model, stype in servers:
            marker = " ←" if (not args.type or stype == args.type) else ""
            print(f"  :{port}  {stype:10s}  {model}{marker}")
        if args.type:
            urls = ",".join(f"http://localhost:{port}/v1"
                            for port, _, stype in servers if stype == args.type)
            print(f"\n{args.type} URLs: {urls}")


if __name__ == "__main__":
    main()
