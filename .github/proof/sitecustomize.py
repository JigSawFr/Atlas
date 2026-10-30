"""Records or replays every urllib request of a run, for comparing two
versions of the tools on the same answers.

ATLAS_RECORD=<dir>: each answer (or error) is kept, by its method, address
and body, in the order asked: a request asked twice (the GOG catalog by the
weekly and the daily tools, titledb by the build and the prices) keeps both
answers. A refusal (429) or a server error is asked again here, out of the
tools' sight, for at most RETRY_BUDGET seconds a process, so that both
versions get whole answers rather than the old one's bad luck.
ATLAS_REPLAY=<dir>: each request is answered from there, the n-th asking
of a request with its n-th answer (the last one once they run out); an error
is raised again as it came; one never recorded raises a URLError (as an
unreachable service would) and is listed in misses.txt.
"""
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request

_real = urllib.request.urlopen
_record = os.environ.get("ATLAS_RECORD")
_replay = os.environ.get("ATLAS_REPLAY")
RETRY_WAITS = (65, 130, 260)
RETRY_BUDGET = 3600
_waited = 0


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


def _count(directory, key):
    n = 0
    while os.path.exists(os.path.join(directory, f"{key}.{n}")):
        n += 1
    return n


def _raise(status, url):
    if status == 0:
        raise urllib.error.URLError("recorded failure")
    raise urllib.error.HTTPError(url, status, "recorded", {}, io.BytesIO(b""))


def _served(key):
    """How many times this request was answered in this replay (all processes)."""
    path = os.path.join(_replay, "served", key)
    try:
        with open(path, encoding="utf-8") as f:
            n = int(f.read())
    except (OSError, ValueError):
        n = 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n + 1))
    return n


def urlopen(request, *args, **kwargs):
    global _waited
    key, url = _key(request)
    if _replay:
        kept_n = _count(_replay, key)
        if not kept_n:
            with open(os.path.join(_replay, "misses.txt"), "a", encoding="utf-8") as f:
                f.write(url[:300] + "\n")
            raise urllib.error.URLError("not recorded")
        n = min(_served(key), kept_n - 1)
        with open(os.path.join(_replay, f"{key}.{n}"), "rb") as f:
            kept = json.loads(f.read())
        if kept["status"] != 200:
            _raise(kept["status"], url)
        return _Answer(kept["body"].encode("latin-1"), url)
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            with _real(request, *args, **kwargs) as r:
                body = r.read()
            status = 200
            break
        except urllib.error.HTTPError as e:
            body, status = b"", e.code
            retry = e.code == 429 or e.code >= 500
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            body, status, retry = b"", 0, True
        if not retry or attempt == len(RETRY_WAITS) or _waited + RETRY_WAITS[attempt] > RETRY_BUDGET:
            break
        _waited += RETRY_WAITS[attempt]
        time.sleep(RETRY_WAITS[attempt])
    if _record:
        _keep(key, url, status, body)
    if status != 200:
        _raise(status, url)
    return _Answer(body, url)


def _keep(key, url, status, body):
    os.makedirs(_record, exist_ok=True)
    with open(os.path.join(_record, f"{key}.{_count(_record, key)}"), "w", encoding="utf-8") as f:
        json.dump({"url": url[:300], "status": status, "body": body.decode("latin-1")}, f)


if _record or _replay:
    urllib.request.urlopen = urlopen
