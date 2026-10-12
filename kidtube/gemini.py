"""Small wrapper around the Google Gemini REST API: text, images and speech."""
import base64
import json
import os
import time
import wave

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return key


def _call(model, body, tries=4):
    url = API.format(model=model)
    last = None
    for attempt in range(tries):
        r = requests.post(url, params={"key": _key()}, json=body, timeout=300)
        if r.status_code == 200:
            return r.json()
        last = f"{r.status_code}: {r.text[:500]}"
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        break
    raise RuntimeError(f"Gemini {model} failed - {last}")


def _parts(resp):
    try:
        return resp["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        reason = resp.get("promptFeedback") or resp.get("candidates", [{}])[0].get("finishReason")
        raise RuntimeError(f"Gemini returned no content ({reason})")


def generate_json(model, prompt, temperature=1.0):
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": temperature},
    }
    text = "".join(p.get("text", "") for p in _parts(_call(model, body)))
    return json.loads(text)


def generate_image(model, prompt, out_path, reference_paths=(), aspect="9:16"):
    parts = []
    for ref in reference_paths:
        with open(ref, "rb") as f:
            parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(f.read()).decode()}})
    parts.append({"text": prompt})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}},
    }
    for p in _parts(_call(model, body)):
        data = p.get("inlineData") or p.get("inline_data")
        if data:
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(data["data"]))
            return out_path
    raise RuntimeError("Gemini image response had no image")


def speak(model, text, voice, out_wav, style="Read warmly and slowly, like a kind storyteller for toddlers"):
    body = {
        "contents": [{"role": "user", "parts": [{"text": f"{style}: {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    for p in _parts(_call(model, body)):
        data = p.get("inlineData") or p.get("inline_data")
        if data:
            pcm = base64.b64decode(data["data"])  # 16-bit mono PCM at 24 kHz
            with wave.open(out_wav, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(pcm)
            return out_wav
    raise RuntimeError("Gemini speech response had no audio")
