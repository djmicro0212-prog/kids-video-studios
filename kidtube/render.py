"""Turns pictures + audio into the finished vertical video with ffmpeg."""
import os
import subprocess
import textwrap

FONT_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "assets", "font.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
MAX_SECONDS = 178  # YouTube Shorts limit is 3 minutes; keep a small margin


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:6])}...\n{p.stderr[-1500:]}")
    return p


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout
    return float(out.strip())


def font():
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return os.path.abspath(f)
    raise RuntimeError("no font found for captions")


MOVES = [
    # (zoom expression, x expression, y expression)
    ("min(zoom+0.0007,1.15)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),                  # slow push in
    ("if(eq(on,0),1.15,max(zoom-0.0007,1.0))", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),  # gentle pull out
    ("1.12", "(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"),                           # pan left to right
    ("1.12", "(iw-iw/zoom)*(1-on/{frames})", "ih/2-(ih/zoom/2)"),                       # pan right to left
    ("min(zoom+0.0006,1.12)", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*0.3"),                 # push in, upper area
]


def caption_png(text, w, h, out_path):
    """Big, centred, outlined caption on a transparent layer (one line per lyric line)."""
    from PIL import Image, ImageDraw, ImageFont
    size = int(w * 0.064)
    fnt = ImageFont.truetype(font(), size)
    lines = []
    for part in text.split("\n"):
        lines += textwrap.wrap(part, 22)
    lines = lines[:5]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gap = int(size * 1.25)
    y = h - int(h * 0.12) - gap * len(lines)
    for line in lines:
        tw = d.textlength(line, font=fnt)
        d.text(((w - tw) / 2, y), line, font=fnt, fill="white", stroke_width=7, stroke_fill=(58, 42, 106))
        y += gap
    img.save(out_path)
    return out_path


def scene_clip(image, seconds, caption, out_path, cfg, move_index, workdir):
    w, h, fps = cfg["width"], cfg["height"], cfg["fps"]
    frames = max(1, int(round(seconds * fps)))
    z, x, y = MOVES[move_index % len(MOVES)]
    x, y = x.format(frames=frames), y.format(frames=frames)
    fade = min(0.35, seconds / 4)
    vf = (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
        f"fade=t=in:st=0:d={fade},fade=t=out:st={seconds - fade:.3f}:d={fade}"
    )
    inputs = ["-loop", "1", "-i", image]
    if cfg.get("captions") and caption:
        png = os.path.join(workdir, os.path.basename(out_path) + ".caption.png")
        caption_png(caption, w, h, png)
        inputs += ["-loop", "1", "-i", png]
        graph = f"[0:v]{vf}[bg];[1:v]format=rgba,fade=t=in:st=0:d={fade}:alpha=1,fade=t=out:st={seconds - fade:.3f}:d={fade}:alpha=1[cap];[bg][cap]overlay=0:0[v]"
    else:
        graph = f"[0:v]{vf}[v]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", graph, "-map", "[v]", "-t", f"{seconds:.3f}",
         "-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out_path])
    return out_path


def join_clips(clips, out_path, workdir):
    lst = os.path.join(workdir, "clips.txt")
    with open(lst, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_path])
    return out_path


def concat_narration(wavs, gap, out_path, workdir):
    """Joins narration wavs with a short pause after each. Returns (path, [scene durations])."""
    padded, lengths = [], []
    for i, wav in enumerate(wavs):
        p = os.path.join(workdir, f"pad_{i}.wav")
        run(["ffmpeg", "-y", "-i", wav, "-af", f"apad=pad_dur={gap}", "-ar", "44100", "-ac", "2", p])
        padded.append(p)
        lengths.append(duration(p))
    lst = os.path.join(workdir, "narr.txt")
    with open(lst, "w") as f:
        for p in padded:
            f.write(f"file '{os.path.abspath(p)}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "pcm_s16le", out_path])
    return out_path, lengths


def mix_with_bed(voice, bed, bed_volume, total, out_path):
    run(["ffmpeg", "-y", "-i", voice, "-stream_loop", "-1", "-i", bed, "-filter_complex",
         f"[1:a]volume={bed_volume},afade=t=in:d=1,afade=t=out:st={max(0, total-2.5):.2f}:d=2.5[b];"
         f"[0:a][b]amix=inputs=2:duration=first:dropout_transition=0,"
         f"loudnorm=I=-16:TP=-1.5:LRA=11[a]",
         "-map", "[a]", "-t", f"{total:.3f}", "-ar", "44100", out_path])
    return out_path


def prepare_song(song, out_path):
    total = min(duration(song), MAX_SECONDS)
    run(["ffmpeg", "-y", "-i", song, "-t", f"{total:.3f}", "-af",
         f"afade=t=out:st={max(0, total-2):.2f}:d=2,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", out_path])
    return out_path, total


def song_scene_lengths(scenes, total):
    """Splits the song length across scenes in proportion to how much each scene sings."""
    weights = [max(1, sum(len(l) for l in s.get("lyrics", []))) for s in scenes]
    tot = sum(weights)
    return [total * wgt / tot for wgt in weights]


def mux(video, audio, out_path):
    run(["ffmpeg", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path])
    return out_path
