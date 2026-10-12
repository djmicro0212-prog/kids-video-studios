# Daily Claude task: queue today's videos in Metricool for approval

(This is the instruction text for the daily Claude scheduled task. Replace OWNER/REPO with your GitHub repository.)

---

Queue today's kids' videos in Metricool as drafts for me to approve.

1. Fetch https://api.github.com/repos/OWNER/REPO/releases/latest and find the asset named `manifest.json`.
   Read it from its `browser_download_url`. If the manifest's `date` is not today's date (Europe/London),
   stop and tell me the daily video run didn't produce videos today, with a link to
   https://github.com/OWNER/REPO/actions so I can see why.
2. In Metricool, use brand blogId 7382760 (check with getBrandSettings that YouTube is connected; if not,
   stop and tell me to connect YouTube in Metricool).
3. For each video in the manifest, create ONE scheduled post with createScheduledPost:
   - date / publicationDate: today at the video's `post_time`, timezone Europe/London
     (if that time has already passed, use one hour from now)
   - providers: [{"network": "youtube"}]
   - text: the video's `description`
   - media: [the video's `url`]
   - draft: true   (so nothing goes live until I approve it in Metricool)
   - youtubeData: {"title": <title>, "type": "short", "privacy": "public", "tags": <tags>,
     "category": "EDUCATION" for learning videos else "FILM_ANIMATION",
     "madeForKids": <posting.made_for_kids>, "isAiGeneratedContent": <posting.ai_generated_disclosure>}
4. Do not post anything that isn't in the manifest, and never set draft to false.
5. Send me a short message listing each video's title, format, length and planned time, with the Metricool
   planner links, and remind me to watch and approve them.
