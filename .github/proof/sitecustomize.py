"""Records or replays every urllib request of a run, for comparing two
versions of the tools on the same answers.

ATLAS_RECORD=<dir>: each answer (or HTTP error) is kept, by its method,
address and body. ATLAS_REPLAY=<dir>: each request is answered from there;
one never recorded raises a URLError (as an unreachable service would).
"""
import hashlib
import io
import json
import os
import urllib.error
import urllib.request

_real = urllib.request.urlopen
_record = os.environ.get("ATLAS_RECORD")
_replay = os.environ.get("ATLAS_REPLAY")


def _key(request):
    if isinstance(request, str):
        url, data, method = request, None, "GET"
    else:
        url, data, method = request.full_url, request.data, request.get_method()
    h = hashlib.sha256()
    h.update(method.encode() + b" " + url.encode() + b"\n" + (data or b""))
    return h.hexdigest(), url


class _Answer(io.BytesIO):
    def __init__(self, body, url):
        super().__init__(body)
        self.url = url
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def urlopen(request, *args, **kwargs):
    key, url = _key(request)
    if _replay:
        path = os.path.join(_replay, key)
        if not os.path.exists(path):
            with open(os.path.join(_replay, "misses.txt"), "a", encoding="utf-8") as f:
                f.write(url[:300] + "\n")
            raise urllib.error.URLError("not recorded")
        with open(path, "rb") as f:
            kept = json.loads(f.read())
        if kept["status"] != 200:
            raise urllib.error.HTTPError(url, kept["status"], "recorded", {}, io.BytesIO(b""))
        return _Answer(kept["body"].encode("latin-1"), url)
    try:
        with _real(request, *args, **kwargs) as r:
            body = r.read()
        status = 200
    except urllib.error.HTTPError as e:
        body, status = b"", e.code
        if _record and e.code in (404,):
            _keep(key, url, status, body)
        raise
    if _record:
        _keep(key, url, status, body)
    return _Answer(body, url)


def _keep(key, url, status, body):
    os.makedirs(_record, exist_ok=True)
    with open(os.path.join(_record, key), "w", encoding="utf-8") as f:
        json.dump({"url": url[:300], "status": status, "body": body.decode("latin-1")}, f)


if _record or _replay:
    urllib.request.urlopen = urlopen
