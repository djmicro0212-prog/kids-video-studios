"""Writes an original, kid-safe script for one video."""
import random

SAFETY = """
Rules (all must hold):
- For ages 2-6. Warm, gentle, happy. Nothing scary, violent, gross, dangerous to copy, or sad without comfort.
- 100% ORIGINAL: no existing characters, brands, shows, songs, celebrities or real people. Do not reuse lyrics of any
  existing song or nursery rhyme; invent new words and a new idea.
- Teach or model something small and good (sharing, counting, colours, kindness, brushing teeth, animals, weather).
- Simple vocabulary, short sentences, lots of repetition, present tense.
- Give it a real story with a beginning, a gentle problem and a happy ending, so every video is different.
- image_prompt describes ONE clear moment: who, doing what, where. No words or letters in the picture.
"""

FORMAT_BRIEFS = {
    "song": """FORMAT: an original sung nursery song.
Write 8 scenes. Each scene has 2-4 short singable lyric lines (5-8 syllables each, AABB or ABCB rhyme)
in "lyrics", and a "section" of "Verse" or "Chorus". Use the SAME chorus at least three times.
Total lyrics should take {seconds} seconds to sing (about 1 line per 2.5 seconds). Leave "narration" empty.""",
    "story": """FORMAT: a short narrated animated story.
Write 8-10 scenes. Each scene has 1-3 sentences of "narration" read aloud. Total narration about {words} words.
Include a little repeated catchphrase kids can join in with.""",
    "learning": """FORMAT: a fun learning video (pick ONE topic: a few letters, counting 1-10, colours, shapes,
opposites, or animal sounds) told through a tiny story with a friendly guide character.
Write 8-10 scenes, each with "narration" (about {words} words in total). Ask the viewer to join in
("Can you say it with me?") and repeat each new word twice.""",
    "bedtime": """FORMAT: a calm bedtime story. Slow, soothing, cosy, ends with everyone falling asleep.
Write 8 scenes with gentle "narration" (about {words} words in total). Night-time colours, soft light.""",
}

SCHEMA = """
Return JSON only, in exactly this shape:
{
  "title": "YouTube title, under 70 characters, fun and clear, no clickbait, no ALL CAPS",
  "description": "2-3 friendly sentences for parents saying what the child will enjoy or learn",
  "tags": ["8 to 12 short search tags"],
  "characters": [{"name": "Name", "look": "very specific visual description: species, colours, clothing, size"}],
  "setting": "one sentence describing the world",
  "scenes": [
    {"section": "Verse|Chorus|Scene", "narration": "...", "lyrics": ["..."], "image_prompt": "...", "caption": "short on-screen line (max 8 words)"}
  ]
}
"""


def build_prompt(fmt, seconds, recent_titles, channel):
    words = int(seconds * 2.0)  # slow toddler-friendly reading pace
    brief = FORMAT_BRIEFS[fmt].format(seconds=seconds, words=words)
    themes = ["farm animals", "the ocean", "space", "a rainy day", "a garden", "a bakery", "trains", "the jungle",
              "a snowy day", "the seaside", "a birthday", "bath time", "a forest picnic", "dinosaurs (friendly)",
              "bugs and butterflies", "a fire station visit", "the moon and stars", "a playground", "the market",
              "autumn leaves", "a music band of animals", "a hot air balloon", "a lost sock", "a little boat"]
    nudge = random.sample(themes, 3)
    recent = "\n".join(f"- {t}" for t in recent_titles[-40:]) or "- (none yet)"
    return f"""You write original videos for a faceless kids' YouTube channel called "{channel}".
{brief}
{SAFETY}
Fresh ideas to consider (or invent your own): {', '.join(nudge)}.
Do NOT repeat the idea or characters of these recent videos:
{recent}
{SCHEMA}"""


def check(script, fmt):
    scenes = script.get("scenes") or []
    if len(scenes) < 5:
        raise ValueError("script has too few scenes")
    for s in scenes:
        if not s.get("image_prompt"):
            raise ValueError("scene missing image_prompt")
        if fmt == "song" and not s.get("lyrics"):
            raise ValueError("song scene missing lyrics")
        if fmt != "song" and not s.get("narration"):
            raise ValueError("scene missing narration")
    if not script.get("title"):
        raise ValueError("missing title")
    return script


def write_script(generate_json, model, fmt, seconds, recent_titles, channel):
    prompt = build_prompt(fmt, seconds, recent_titles, channel)
    err = None
    for _ in range(3):
        try:
            return check(generate_json(model, prompt), fmt)
        except Exception as e:  # malformed JSON or missing fields - ask again
            err = e
    raise RuntimeError(f"could not get a valid script: {err}")
