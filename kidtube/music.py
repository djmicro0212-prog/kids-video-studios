"""Music through fal.ai: sung songs (with our own lyrics) and soft instrumental beds."""
import os
import time

import requests

QUEUE = "https://queue.fal.run/{model}"


def _headers():
    key = os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY is not set")
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def _run(model, payload, timeout_s=900):
    r = requests.post(QUEUE.format(model=model), headers=_headers(), json=payload, timeout=60)
    r.raise_for_status()
    job = r.json()
    status_url, response_url = job["status_url"], job["response_url"]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        s = requests.get(status_url, headers=_headers(), timeout=60).json()
        if s.get("status") == "COMPLETED":
            res = requests.get(response_url, headers=_headers(), timeout=60)
            res.raise_for_status()
            return res.json()
        if s.get("status") in ("FAILED", "ERROR"):
            raise RuntimeError(f"fal {model} failed: {s}")
        time.sleep(5)
    raise RuntimeError(f"fal {model} timed out")


def _audio_url(result):
    audio = result.get("audio") or result.get("audio_file") or {}
    url = audio.get("url") if isinstance(audio, dict) else audio
    if not url:
        raise RuntimeError(f"fal response had no audio: {str(result)[:300]}")
    return url


def _download(url, out_path):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    return out_path


def sing(model, style, lyrics_lines, out_path):
    """Generate a sung song. lyrics_lines may include [Verse]/[Chorus] tags."""
    lyrics = "\n".join(lyrics_lines)
    result = _run(model, {"prompt": style, "lyrics_prompt": lyrics})
    return _download(_audio_url(result), out_path)


def instrumental(model, style, out_path):
    # A wordless "hum" lyric keeps vocal models instrumental-sounding; the bed sits quietly under narration.
    result = _run(model, {"prompt": style + ", instrumental, no singing",
                          "lyrics_prompt": "[Instrumental]\n(la la la)\n[Instrumental]"})
    return _download(_audio_url(result), out_path)
