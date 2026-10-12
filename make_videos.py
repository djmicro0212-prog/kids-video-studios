"""Kids Video Studio - makes today's videos.

    python make_videos.py               # real run (needs GEMINI_API_KEY and FAL_KEY)
    python make_videos.py --dry-run     # free offline test with placeholder pictures and tones
    python make_videos.py --count 1 --format song
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import shutil
import sys
import traceback

import yaml

from kidtube import render
from kidtube.script_writer import write_script

ROOT = os.path.dirname(os.path.abspath(__file__))

# Rough costs in US dollars, for the run summary
COST = {"image": 0.039, "script": 0.003, "tts_per_scene": 0.002, "song": 0.10, "bed": 0.05}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "video"


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def pick_formats(cfg, history, count, forced=None):
    if forced:
        return [forced] * count
    fmts = cfg["formats"]
    start = len(history["videos"]) % len(fmts)
    return [fmts[(start + i) % len(fmts)] for i in range(count)]


def make_one(cfg, svc, fmt, seconds, history, workdir):
    os.makedirs(workdir, exist_ok=True)
    m = cfg["models"]
    cost = 0.0
    recent = [v["title"] for v in history["videos"]]

    # 1. Script
    script = write_script(svc.generate_json, m["script"], fmt, seconds, recent, cfg["channel_name"])
    cost += COST["script"]
    with open(os.path.join(workdir, "script.json"), "w") as f:
        json.dump(script, f, indent=2)
    print(f"  script: {script['title']} ({len(script['scenes'])} scenes)")

    # 2. Character sheet, then every scene drawn with it as a reference so characters stay consistent
    style = cfg["art_style"].strip()
    cast = "; ".join(f"{c['name']}: {c['look']}" for c in script.get("characters", []))
    sheet = os.path.join(workdir, "characters.png")
    svc.generate_image(m["image"], f"Character reference sheet, each character shown once, full body, plain cream "
                       f"background. Characters: {cast}. Style: {style}", sheet)
    cost += COST["image"]
    images = []
    for i, sc in enumerate(script["scenes"]):
        p = os.path.join(workdir, f"scene_{i:02d}.png")
        prompt = (f"Use the attached character sheet so the characters look exactly the same. "
                  f"Setting: {script.get('setting', '')}. Scene: {sc['image_prompt']}. Characters: {cast}. "
                  f"Style: {style}. Vertical 9:16 composition, keep the bottom fifth simple for captions.")
        svc.generate_image(m["image"], prompt, p, reference_paths=[sheet])
        images.append(p)
        cost += COST["image"]
    print(f"  pictures: {len(images)}")

    # 3. Sound
    audio = os.path.join(workdir, "audio.wav")
    if fmt == "song":
        lines = []
        for sc in script["scenes"]:
            lines.append(f"[{sc.get('section', 'Verse')}]")
            lines.extend(sc["lyrics"])
        raw = os.path.join(workdir, "song_raw.mp3")
        svc.sing(cfg["music"]["model"], cfg["music"]["style_song"], lines, raw)
        cost += COST["song"]
        audio, total = render.prepare_song(raw, audio)
        lengths = render.song_scene_lengths(script["scenes"], total)
        captions = ["\n".join(sc["lyrics"]) for sc in script["scenes"]]
    else:
        voice = cfg["bedtime_voice"] if fmt == "bedtime" else cfg["narrator_voice"]
        tone = ("Whisper softly and very slowly, like a calm bedtime story" if fmt == "bedtime"
                else "Read warmly and cheerfully, slowly and clearly, like a kind storyteller for toddlers")
        wavs = []
        for i, sc in enumerate(script["scenes"]):
            w = os.path.join(workdir, f"voice_{i:02d}.wav")
            svc.speak(m["tts"], sc["narration"], voice, w, style=tone)
            wavs.append(w)
            cost += COST["tts_per_scene"]
        narr, lengths = render.concat_narration(wavs, 0.7, os.path.join(workdir, "narration.wav"), workdir)
        total = min(sum(lengths), render.MAX_SECONDS)
        bed_style = cfg["music"]["style_bedtime_bed"] if fmt == "bedtime" else cfg["music"]["style_bed"]
        bed = os.path.join(workdir, "bed.mp3")
        svc.instrumental(cfg["music"]["model"], bed_style, bed)
        cost += COST["bed"]
        render.mix_with_bed(narr, bed, cfg["music"]["bed_volume"], total, audio)
        captions = [sc.get("narration", "") if len(sc.get("narration", "")) < 90 else sc.get("caption", "")
                    for sc in script["scenes"]]
    print(f"  sound: {total:.0f}s")

    # 4. Picture track and final video
    clips = []
    for i, (img, secs, cap) in enumerate(zip(images, lengths, captions)):
        clips.append(render.scene_clip(img, secs, cap, os.path.join(workdir, f"clip_{i:02d}.mp4"),
                                       cfg, i, workdir))
    silent = render.join_clips(clips, os.path.join(workdir, "silent.mp4"), workdir)
    name = f"{slug(script['title'])}.mp4"
    final = render.mux(silent, audio, os.path.join(workdir, name))
    cover = os.path.join(workdir, f"{slug(script['title'])}.png")
    shutil.copy(images[0], cover)

    tags = script.get("tags", [])[:12]
    hashtags = " ".join("#" + re.sub(r"\W", "", t.title()) for t in tags[:3])
    description = (f"{script.get('description', '')}\n\nNew videos every day on {cfg['channel_name']}!\n"
                   f"Original songs and stories, made with AI-assisted animation.\n\n{hashtags} #Shorts")
    return {
        "format": fmt, "title": script["title"][:100], "description": description, "tags": tags,
        "file": final, "cover": cover, "seconds": round(render.duration(final), 1), "est_cost_usd": round(cost, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="free offline test with placeholders")
    ap.add_argument("--count", type=int)
    ap.add_argument("--format", choices=["song", "story", "learning", "bedtime"])
    ap.add_argument("--out", default=os.path.join(ROOT, "output"))
    args = ap.parse_args()

    with open(os.path.join(ROOT, "config.yaml")) as f:
        cfg = yaml.safe_load(f)
    if args.dry_run:
        from kidtube import fake as svc
        from kidtube import fake as music_svc
    else:
        from kidtube import gemini as svc
        from kidtube import music as music_svc
    svc_all = type("S", (), {})()
    svc_all.generate_json = svc.generate_json
    svc_all.generate_image = svc.generate_image
    svc_all.speak = svc.speak
    svc_all.sing = music_svc.sing
    svc_all.instrumental = music_svc.instrumental

    history_path = os.path.join(ROOT, "history.json")
    history = load(history_path, {"videos": []})
    count = max(1, min(6, args.count or cfg["videos_per_day"]))
    today = dt.date.today().isoformat()
    day_dir = os.path.join(args.out, today)
    os.makedirs(day_dir, exist_ok=True)

    made = []
    for i, fmt in enumerate(pick_formats(cfg, history, count, args.format)):
        seconds = random.randint(*cfg["target_seconds"])
        print(f"Video {i+1}/{count}: {fmt}, aiming for ~{seconds}s")
        try:
            v = make_one(cfg, svc_all, fmt, seconds, history, os.path.join(day_dir, f"work_{i+1}"))
            dest = os.path.join(day_dir, f"{i+1}-{os.path.basename(v['file'])}")
            shutil.move(v["file"], dest)
            cover = os.path.join(day_dir, f"{i+1}-{os.path.basename(v['cover'])}")
            shutil.move(v["cover"], cover)
            v["file"], v["cover"] = os.path.basename(dest), os.path.basename(cover)
            made.append(v)
            if not args.dry_run:
                history["videos"].append({"date": today, "title": v["title"], "format": fmt})
            print(f"  done: {v['file']} ({v['seconds']}s, ~${v['est_cost_usd']})")
        except Exception:
            print(f"  FAILED video {i+1}:\n{traceback.format_exc()}", file=sys.stderr)

    manifest = {"date": today, "posting": cfg["posting"], "videos": made}
    base = os.environ.get("ASSET_BASE_URL", "").rstrip("/")
    for v, t in zip(made, cfg["posting"]["times"]):
        v["post_time"] = t
        if base:
            v["url"], v["cover_url"] = f"{base}/{v['file']}", f"{base}/{v['cover']}"
    with open(os.path.join(day_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    if not args.dry_run:
        history["videos"] = history["videos"][-500:]
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)
    print(f"\nMade {len(made)}/{count} videos in {day_dir}. "
          f"Estimated spend: ${sum(v['est_cost_usd'] for v in made):.2f}")
    sys.exit(0 if made else 1)


if __name__ == "__main__":
    main()
