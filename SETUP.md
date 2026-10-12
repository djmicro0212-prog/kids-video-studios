# Kids Video Studio: setup guide

Every morning this app writes, illustrates, voices or sings, and edits new kids' videos, then
puts them in Metricool as **drafts**. You watch them on your phone and approve the ones you like;
Metricool posts them to YouTube at the planned times.

```
06:15  GitHub makes today's videos  ->  saves them as a "release" in your GitHub project
07:30  Claude task                   ->  adds each video to Metricool as a draft
You    open Metricool                ->  watch, approve (or delete)  ->  YouTube
```

## What it costs (estimates, October 2026 prices)

| Item | Per video |
|---|---|
| ~9 pictures (Gemini image) | about $0.35 |
| Script + narration voice (Gemini) | a few cents |
| Song or background music (fal.ai) | about $0.05-0.10 |
| **Total** | **about $0.40-0.50** |

At 2 videos a day that is roughly $25-30 a month (about £19-23). GitHub is free for public projects.
Each day's run prints its estimated spend in the GitHub log. Set spending limits on both services.

## 1. Get two API keys

1. **Google Gemini**: go to aistudio.google.com, choose *Get API key*, create one, and turn on
   billing (picture-making isn't in the free tier). Set a monthly budget alert in Google Cloud.
2. **fal.ai** (music): sign up at fal.ai, add about $10 of credit, then *Dashboard > Keys > Add key*.

## 2. Put the app on GitHub

1. Create a free account at github.com.
2. Create a new repository, e.g. `kids-video-studio`, and make it **Public**. Metricool can only fetch
   the videos from a public project. Your API keys stay private (step 3); only the code and finished
   videos are visible.
3. Upload every file from this folder, including the hidden `.github` folder
   (*Add file > Upload files*, drag the whole folder in).

## 3. Add your keys as secrets

Repository *Settings > Secrets and variables > Actions > New repository secret*, twice:

- `GEMINI_API_KEY` = your Gemini key
- `FAL_KEY` = your fal.ai key

Then *Settings > Actions > General > Workflow permissions*: choose **Read and write permissions**, Save.

## 4. Test it

*Actions* tab > **Daily kids videos** > *Run workflow*, set count to `1`, run. After 10-20 minutes a
new release appears on the repository's main page with the video. Watch it before going further.
If it fails, open the run, copy the red error and send it to Claude.

## 5. Connect YouTube to Metricool

Metricool is connected to Claude, but no YouTube channel is linked inside Metricool yet:
https://app.metricool.com/brands/connections?blogId=7382760

## 6. Turn on the daily Claude task

Tell Claude your repository name (e.g. `yourname/kids-video-studio`) and it will set up the daily
scheduled task from `CLAUDE_DAILY_TASK.md`.

## Changing things

Edit `config.yaml` on GitHub (pencil icon):

- `videos_per_day`: 1-6 (cost scales with it)
- `formats`: remove any you don't want (song, story, learning, bedtime)
- `art_style`, `narrator_voice`, `music` styles: change the look and sound
- `posting.times`: the UK times videos go live

## Staying on the right side of YouTube

- Approve only videos you've actually watched; delete any that look odd (AI pictures sometimes have
  strange hands or faces).
- Videos are marked *Made for Kids*, which YouTube legally requires for children's content
  (comments off, lower ad rates).
- The formats rotate and the app remembers past titles to avoid repeats, but YouTube's
  "inauthentic content" policy targets templated, mass-produced channels. Fewer, better videos
  are safer than six a day.

## Free test on your own computer

With Python and ffmpeg installed: `pip install -r requirements.txt` then
`python make_videos.py --dry-run --count 1` makes a placeholder video with no API costs.
