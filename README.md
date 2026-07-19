# OPRA Exam Prep Podcast Feed
 
Turns NotebookLM Audio Overview `.m4a` exports into a private podcast feed
you can subscribe to in Apple Podcasts.
 
Audio files are **not stored in this repo** — they stay on your Mac and are
served over a temporary tunnel while you download episodes to your phone.
Only `feed.xml` (the RSS feed itself) lives on GitHub Pages.
 
---
 
## Repo structure
 
```
opra-podcastt/
  episodes/                  ← NOT committed to git (see .gitignore)
    session-01/
      OPRA-01-Some_Topic.m4a
      OPRA-02-Another_Topic.m4a
      ...
    session-02/
      OPRA-02-01-Some_Topic.m4a
      OPRA-02-02-Another_Topic.m4a
      ...
  manifest.csv                ← optional, only for title overrides
  feed.xml                    ← generated, committed and pushed
  generate_feed.py
  README.md
```
 
**Filename conventions the script understands:**
- `PREFIX-NN-Title.m4a` (e.g. `OPRA-01-Clinical_ADME.m4a`) → episode 01
- `PREFIX-NN-NN-Title.m4a` (e.g. `OPRA-02-01-Some_Topic.m4a`) → the *last*
  number before the title is the episode number (the first is treated as a
  redundant session marker and ignored)
- Underscores in the title become spaces; hyphens inside words (e.g.
  `Beta-Lactam`) are preserved
- The season number always comes from the **folder name** (`session-01` →
  season 1), not the filename
New session → new folder named `session-NN`, files inside numbered
sequentially (numeric prefix doesn't need to be zero-padded, but keeping it
consistent makes the folder easier to scan).
 
---
 
## One-time setup
 
```bash
pip3 install mutagen --break-system-packages
brew install ffmpeg        # provides ffprobe, used as a duration fallback
brew install cloudflared    # for the local tunnel
```
 
---
 
## Every time you add a new session
 
### 1. Drop the files in
Create `episodes/session-NN/` and copy the `.m4a` files in, following the
naming convention above.
 
*(Optional)* If you want to override any auto-generated titles, add rows to
`manifest.csv`:
```csv
relpath,title,description
session-03/OPRA-03-01-Some_Topic.m4a,Custom Title Here,Optional longer description
```
 
### 2. Regenerate the feed
```bash
python3 generate_feed.py \
  --audio-dir episodes \
  --base-url https://YOUR-CURRENT-TUNNEL-URL.trycloudflare.com \
  --title "OPRA Exam Prep" \
  --author "Alex" \
  --description "NotebookLM Audio Overviews for OPRA exam prep" \
  --manifest manifest.csv \
  --output feed.xml
```
Watch the console output — it prints how many episodes/sessions it found,
and warns if any file's duration couldn't be read (possible corruption).
 
Episode titles are automatically prefixed with season/episode, e.g.
`S2E13 - Antianginal Drugs and the Starving Heart`.
 
### 3. Start serving the audio locally
```bash
cd episodes && python3 -m http.server 8080 &
cloudflared tunnel --url http://localhost:8080
```
This prints a public URL like `https://random-words-1234.trycloudflare.com`.
 
**This URL changes every time you restart the tunnel** — if it's different
from what you used in step 2, re-run step 2 with the new URL before
continuing.
 
### 4. Push the feed
```bash
git add feed.xml manifest.csv
git commit -m "Add session-NN"
git push
```
(`episodes/` is git-ignored — only `feed.xml` needs to go up.)
 
### 5. Subscribe / refresh in Apple Podcasts
Feed URL: `https://YOURUSERNAME.github.io/opra-podcasst/feed.xml`
 
- **First time:**
  - Mac: File → Add a Show by URL...
  - iPhone/iPad: Library tab → `•••` → Follow a Show by URL
- **Already subscribed:** select the show → Check for New Episodes (Mac) or
  pull to refresh (iPhone)
### 6. Download episodes to your phone, then verify offline
- In Podcasts, download each new episode (tap the download icon, or set the
  show to auto-download)
- Turn on **Airplane Mode** and confirm a few episodes play from different
  points in the list
- Once confirmed, it's safe to stop the tunnel:
```bash
  # Ctrl+C the cloudflared process, then:
  kill %1   # stops the python http.server background job
```
 
---
 
## Troubleshooting
 
**`Missing dependency` error running the script**
→ `pip3 install mutagen --break-system-packages`
 
**Episode duration shows `00:00:00`**
→ Make sure `ffmpeg`/`ffprobe` is installed (`brew install ffmpeg`); the
script falls back to it automatically when mutagen can't read a file.
 
**`git push` fails with "File ... exceeds GitHub's file size limit of
100.00 MB"**
→ Not applicable to `episodes/` anymore since audio isn't tracked in git.
If it recurs for some other file, that file needs Git LFS or shouldn't be
committed.
 
**Episode plays fine via `curl`/browser but Apple Podcasts says
"temporarily unavailable"**
→ Usually a stale feed vs. tunnel URL mismatch, or the tunnel wasn't running
when Podcasts tried to fetch. Confirm the tunnel is up and `feed.xml`'s
`--base-url` matches the current tunnel URL, then force-refresh in Podcasts.
 
**Tunnel URL changed after a restart**
→ Expected — `trycloudflare.com` URLs are not stable across restarts.
Regenerate `feed.xml` with the new URL (step 2) before downloading more
episodes. A **named** Cloudflare Tunnel (tied to a domain you own) avoids
this if it becomes annoying.
 
**Want a permanent hosting solution instead of the tunnel**
→ Point `--base-url` at an S3/Cloudflare R2 bucket with public read access
instead of the tunnel URL. No uptime requirement, no changing URLs, and
sidesteps GitHub's file size and repo size limits entirely.