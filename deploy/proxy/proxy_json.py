#!/usr/bin/env python3
"""Fixed JSON queries used by the offline proxy installer."""

import base64
import json
import sys
from urllib.parse import quote


def main(args):
    mode = args[0]
    if mode == "urlenc" and len(args) == 2:
        print(quote(args[1], safe=""))
        return
    if mode == "vmess" and len(args) == 6:
        _, name, address, port, identifier, sni = args
        doc = {"v": "2", "ps": name, "add": address, "port": port, "id": identifier,
               "aid": "0", "net": "tcp", "type": "none", "host": "", "path": "",
               "tls": "tls", "sni": sni, "scy": "auto"}
        print("vmess://" + base64.b64encode(json.dumps(doc, separators=(",", ":")).encode()).decode())
        return
    if mode == "lookup" and len(args) == 2:
        print(json.load(sys.stdin).get(args[1], ""))
        return
    if len(args) < 2:
        raise ValueError("invalid query")
    with open(args[1], encoding="utf-8") as source:
        document = json.load(source)
    inbounds = document.get("inbounds", [])
    if not isinstance(inbounds, list):
        raise ValueError("invalid inbounds")
    if mode == "ports" and len(args) == 2:
        print(json.dumps({inbound["type"]: inbound["listen_port"] for inbound in inbounds}, separators=(",", ":")))
    elif mode == "list-ports" and len(args) == 2:
        for inbound in inbounds:
            print(inbound["listen_port"])
    elif mode == "protocols" and len(args) == 2:
        print(",".join(inbound["type"] for inbound in inbounds))
    elif mode == "field" and len(args) == 4 and args[3] in ("port", "credential"):
        inbound = next((entry for entry in inbounds if entry.get("type") == args[2]), None)
        if inbound is None:
            return
        if args[3] == "port":
            print(inbound["listen_port"])
        elif args[2] == "shadowsocks":
            print(inbound["password"])
        else:
            field = "uuid" if args[2] in ("vmess", "vless") else "password"
            print(inbound["users"][0][field])
    else:
        raise ValueError("invalid query")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        print("invalid proxy configuration", file=sys.stderr)
        raise SystemExit(1) from exc
