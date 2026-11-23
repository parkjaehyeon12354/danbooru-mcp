"""Danbooru MCP server (stdio, Python stdlib only).

Sends the TLS ClientHello split into two TLS records so SNI-based ISP blocking
doesn't recognise the host. Nothing is written to disk; images are returned
inline to the model.

Optional env: DANBOORU_LOGIN, DANBOORU_API_KEY (raise tag/rate limits).
Self-check:  python danbooru_mcp.py --test
"""
import base64, json, os, socket, ssl, sys, time
from urllib.parse import urlencode, urlsplit

API = "danbooru.donmai.us"
UA = "danbooru-mcp/1.0"
POST_FIELDS = "id,rating,score,fav_count,image_width,image_height,file_ext,created_at,source,tag_string_artist,tag_string_copyright,tag_string_character,tag_string_general,tag_string_meta,file_url,large_file_url,preview_file_url"


# ---------- HTTP over split-ClientHello TLS ----------

def _dechunk(body):
    out, i = b"", 0
    while True:
        j = body.index(b"\r\n", i)
        n = int(body[i:j].split(b";")[0], 16)
        if n == 0:
            return out
        out += body[j + 2:j + 2 + n]
        i = j + 2 + n + 2


def _split_hello(hello, at=2):
    """One TLS handshake record -> two records (same bytes, split payload)."""
    hdr, body = hello[:3], hello[5:]
    return (hdr + at.to_bytes(2, "big") + body[:at],
            hdr + (len(body) - at).to_bytes(2, "big") + body[at:])


def http_get(url, timeout=30):
    """GET url -> (status, headers dict, body bytes)."""
    u = urlsplit(url)
    host, path = u.hostname, (u.path or "/") + ("?" + u.query if u.query else "")
    inc, out = ssl.MemoryBIO(), ssl.MemoryBIO()
    tls = ssl.create_default_context().wrap_bio(inc, out, server_hostname=host)
    with socket.create_connection((host, 443), timeout=timeout) as s:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            tls.do_handshake()
        except ssl.SSLWantReadError:
            pass
        r1, r2 = _split_hello(out.read())
        s.send(r1)
        time.sleep(0.05)  # ponytail: fixed gap so the two records leave as separate packets
        s.sendall(r2)
        while True:
            try:
                tls.do_handshake()
                break
            except ssl.SSLWantReadError:
                if out.pending:
                    s.sendall(out.read())
                d = s.recv(65536)
                if not d:
                    raise ConnectionError(f"{host}: connection closed during TLS handshake")
                inc.write(d)
        if out.pending:
            s.sendall(out.read())
        tls.write((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {UA}\r\n"
                   "Accept: */*\r\nConnection: close\r\n\r\n").encode())
        s.sendall(out.read())
        buf = b""
        while True:
            try:
                c = tls.read(65536)
                if not c:
                    break
                buf += c
                continue
            except ssl.SSLWantReadError:
                pass
            except ssl.SSLZeroReturnError:
                break
            d = s.recv(65536)
            if not d:
                break
            inc.write(d)
    head, _, body = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split()[1])
    headers = {k.strip().lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:])}
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = _dechunk(body)
    return status, headers, body


def api(path, **params):
    if os.environ.get("DANBOORU_LOGIN") and os.environ.get("DANBOORU_API_KEY"):
        params.update(login=os.environ["DANBOORU_LOGIN"], api_key=os.environ["DANBOORU_API_KEY"])
    status, _, body = http_get(f"https://{API}{path}?{urlencode(params)}")
    if status != 200:
        raise RuntimeError(f"Danbooru HTTP {status}: {body[:300].decode(errors='replace')}")
    return json.loads(body)


# ---------- tools ----------

def _slim(p):
    return {k: p.get(k) for k in POST_FIELDS.split(",")} | {"post_url": f"https://{API}/posts/{p.get('id')}"}


def search_posts(tags="", limit=20, page=1):
    posts = api("/posts.json", tags=tags, limit=max(1, min(int(limit), 200)), page=page, only=POST_FIELDS)
    return [_slim(p) for p in posts]


def get_post(post_id):
    return _slim(api(f"/posts/{int(post_id)}.json", only=POST_FIELDS))


def count_posts(tags):
    return api("/counts/posts.json", tags=tags)["counts"]["posts"]


def autocomplete_tags(query, limit=10):
    res = api("/autocomplete.json", **{"search[query]": query, "search[type]": "tag_query", "limit": limit})
    return [{k: r.get(k) for k in ("value", "label", "post_count", "category", "antecedent")} for r in res]


def get_image(post_id, size="sample"):
    """Image bytes for a post: size = preview | sample | original."""
    p = get_post(post_id)
    url = {"preview": p["preview_file_url"], "sample": p["large_file_url"], "original": p["file_url"]}[size]
    if not url:
        raise RuntimeError(f"post {post_id} has no {size} image (deleted or restricted)")
    status, headers, body = http_get(url, timeout=60)
    if status != 200:
        raise RuntimeError(f"image HTTP {status}")
    mime = headers.get("content-type", "image/jpeg").split(";")[0]
    if not mime.startswith("image/"):
        raise RuntimeError(f"{size} file is {mime}, not an image (try size='sample')")
    return p, mime, body


TOOLS = [
    {"name": "search_posts",
     "description": "Search Danbooru posts by tags (Danbooru syntax: space-separated, underscores inside tags, "
                    "metatags like rating:g, order:score, -tag). Anonymous accounts may combine at most 2 normal tags; "
                    "metatags don't count. Returns post metadata and image URLs.",
     "inputSchema": {"type": "object", "properties": {
         "tags": {"type": "string", "description": "e.g. 'hatsune_miku rating:g order:score'"},
         "limit": {"type": "integer", "default": 20, "description": "1-200"},
         "page": {"type": "integer", "default": 1}}, "required": ["tags"]}},
    {"name": "get_post",
     "description": "Get one Danbooru post's metadata and tags by id.",
     "inputSchema": {"type": "object", "properties": {"post_id": {"type": "integer"}}, "required": ["post_id"]}},
    {"name": "count_posts",
     "description": "Number of Danbooru posts matching a tag query.",
     "inputSchema": {"type": "object", "properties": {"tags": {"type": "string"}}, "required": ["tags"]}},
    {"name": "autocomplete_tags",
     "description": "Find canonical Danbooru tag names from a partial, misspelled or aliased term.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}},
    {"name": "get_image",
     "description": "Fetch a Danbooru post's image and show it inline (not saved to disk). "
                    "size: preview (small thumbnail), sample (~850px, default), original (full, can be large).",
     "inputSchema": {"type": "object", "properties": {
         "post_id": {"type": "integer"},
         "size": {"type": "string", "enum": ["preview", "sample", "original"], "default": "sample"}},
         "required": ["post_id"]}},
]


def call_tool(name, args):
    if name == "get_image":
        p, mime, data = get_image(args["post_id"], args.get("size", "sample"))
        return [{"type": "text", "text": f"post {p['id']} ({p['post_url']}), {mime}, {len(data) // 1024} KB"},
                {"type": "image", "data": base64.b64encode(data).decode(), "mimeType": mime}]
    fn = {"search_posts": search_posts, "get_post": get_post,
          "count_posts": count_posts, "autocomplete_tags": autocomplete_tags}[name]
    return [{"type": "text", "text": json.dumps(fn(**args), ensure_ascii=False, indent=1)}]


# ---------- MCP stdio (JSON-RPC, one message per line) ----------

def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None  # notification
    if method == "initialize":
        result = {"protocolVersion": msg["params"].get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "danbooru", "version": "1.0.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        p = msg["params"]
        try:
            result = {"content": call_tool(p["name"], p.get("arguments") or {})}
        except Exception as e:
            result = {"content": [{"type": "text", "text": f"Error: {type(e).__name__}: {e}"}], "isError": True}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve():
    for line in sys.stdin.buffer:
        if not line.strip():
            continue
        resp = handle(json.loads(line))
        if resp is not None:
            sys.stdout.buffer.write(json.dumps(resp, ensure_ascii=False).encode() + b"\n")
            sys.stdout.buffer.flush()


def selftest():
    assert _dechunk(b"3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n") == b"abcde"
    r1, r2 = _split_hello(b"\x16\x03\x01\x00\x05HELLO")
    assert (r1, r2) == (b"\x16\x03\x01\x00\x02HE", b"\x16\x03\x01\x00\x03LLO")
    posts = search_posts("hatsune_miku rating:g", limit=2)
    assert posts and all(p["rating"] == "g" for p in posts), posts
    _, mime, data = get_image(posts[0]["id"], "preview")
    assert mime.startswith("image/") and len(data) > 1000
    print("ok:", [p["id"] for p in posts], mime, len(data), "bytes")


if __name__ == "__main__":
    selftest() if "--test" in sys.argv else serve()
