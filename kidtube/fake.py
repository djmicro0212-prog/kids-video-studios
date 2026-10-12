"""Offline stand-ins for the paid services, used by --dry-run to test the whole pipeline for free."""
import random
import subprocess

from PIL import Image, ImageDraw


def generate_json(model, prompt):
    fmt = "song" if "sung nursery song" in prompt else "story"
    scenes = []
    for i in range(8):
        if fmt == "song":
            scenes.append({"section": "Chorus" if i % 2 else "Verse",
                           "lyrics": [f"Hop little bunny, hop hop hop", f"Line two of part {i+1}, stop stop stop"],
                           "narration": "", "image_prompt": f"bunny scene {i+1}", "caption": ""})
        else:
            scenes.append({"section": "Scene", "narration": f"This is part {i+1} of the test story. The bunny smiles.",
                           "lyrics": [], "image_prompt": f"bunny scene {i+1}", "caption": ""})
    return {"title": f"Test {fmt.title()} - Bunny Hops Home", "description": "A dry-run test video.",
            "tags": ["test"], "characters": [{"name": "Bun", "look": "a small white bunny"}],
            "setting": "a meadow", "scenes": scenes}


def generate_image(model, prompt, out_path, reference_paths=(), aspect="9:16"):
    rnd = random.Random(prompt)
    img = Image.new("RGB", (768, 1344), tuple(rnd.randint(150, 240) for _ in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(12):
        x, y, r = rnd.randint(0, 768), rnd.randint(0, 1344), rnd.randint(30, 160)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(rnd.randint(60, 255) for _ in range(3)))
    d.text((40, 60), prompt[:40], fill=(30, 30, 30))
    img.save(out_path)
    return out_path


def _tone(out_path, seconds, freq):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
                    "-ar", "44100", "-ac", "2", out_path], capture_output=True, check=True)
    return out_path


def speak(model, text, voice, out_wav, style=None):
    return _tone(out_wav, max(2, len(text.split()) / 2.2), 440)


def sing(model, style, lyrics_lines, out_path):
    return _tone(out_path, 75, 523)


def instrumental(model, style, out_path):
    return _tone(out_path, 30, 262)
