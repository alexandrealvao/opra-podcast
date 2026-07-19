# OPRA Exam Prep Podcast Feed

Turns NotebookLM Audio Overview `.m4a` exports into a private podcast feed
you can subscribe to in Apple Podcasts.

Audio files are **not stored in this repo** — they stay on your Mac and are
served over a temporary Cloudflare tunnel while you download episodes to
your phone. Only `feed.xml` and the cover artwork live on GitHub Pages.

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
  cover.jpg                   ← podcast artwork, committed and pushed
  feed.xml                    ← generated, committed and pushed
  generate_feed.py
  check_artwork.py
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
- Episode titles in the feed are automatically prefixed, e.g.
  `S2E13 - Antianginal Drugs and the Starving Heart`

---

## One-time setup

```bash
pip3 install mutagen Pillow --break-system-packages
brew install ffmpeg        # provides ffprobe, used as a duration fallback
brew install cloudflared    # for the local tunnel
```

---

## Podcast artwork

Apple Podcasts requires:
- Square image, minimum 1400×1400px (up to 3000×3000 recommended)
- JPEG or PNG
- RGB color space (not CMYK)

Check an image before using it:
```bash
python3 check_artwork.py path/to/image.jpg
```

The cover lives in the repo root (`cover.jpg`) and is served by GitHub
Pages — permanently, unlike the tunnel URL, since it's small and doesn't
hit any size limits. It's passed to the generator via `--image-url` (see
below) and applies to the whole show, not per-episode.

**A note on sourcing images:** don't use a logo or graphic pulled from
another organization's website/channel, or a paid stock asset you haven't
licensed — even for a private feed, it's their branding/product, not
neutral art. Safer options: something you made yourself (including via an
AI image generator, avoiding any real brand names/logos in the prompt), or
genuinely free-license icon sites like Flaticon.

---

## Adding a new season/episodes in the future

### 1. Drop the files in
Create `episodes/session-NN/` and copy the `.m4a` files in, following the
naming convention above.

*(Optional)* Override any auto-generated titles by adding rows to
`manifest.csv`:
```csv
relpath,title,description
session-03/OPRA-03-01-Some_Topic.m4a,Custom Title Here,Optional longer description
```

### 2. Start a fresh tunnel
```bash
cd episodes && python3 -m http.server 8080 &
cloudflared tunnel --url http://localhost:8080
```
This prints a new public URL, e.g. `https://random-words-1234.trycloudflare.com`.

⚠️ **Every time the tunnel restarts, this URL changes completely** — it is
*not* the same as any URL you've used before, including in a previous
session. The feed has to be regenerated with the new URL every single time
you start a new tunnel, or every episode (old and new) will fail to load
in Podcasts, since `--base-url` applies to the whole feed, not just the
new episodes.

### 3. Regenerate the feed with the new tunnel URL
```bash
python3 generate_feed.py \
  --audio-dir episodes \
  --base-url https://YOUR-NEW-TUNNEL-URL.trycloudflare.com \
  --title "OPRA Exam Prep" \
  --author "Alex" \
  --description "NotebookLM Audio Overviews for OPRA exam prep" \
  --image-url "https://alexandrealvao.github.io/opra-podcasst/cover.jpg" \
  --manifest manifest.csv \
  --output feed.xml
```
Watch the console output — it prints how many episodes/sessions it found,
and warns if any file's duration couldn't be read (possible corruption).

### 4. Push the feed
```bash
git add feed.xml manifest.csv
git commit -m "Add session-NN"
git push
```
(`episodes/` stays git-ignored — only `feed.xml`/`manifest.csv` go up.)

### 5. Refresh in Apple Podcasts
- Mac: select the show → File → Check for New Episodes
- iPhone/iPad: pull to refresh on the show's episode list

### 6. Download every new episode to your MacBook first — as soon as possible
**Do this before doing anything else, and before stopping the tunnel.**
The MacBook is what iPhone/iPad sync relies on — if an episode isn't fully
downloaded on the Mac while the tunnel is still live, it can't be pulled
onto other devices later once the tunnel is gone. Downloading promptly
avoids losing access to an episode entirely if the tunnel URL changes
again before you get to it (a laptop sleep, a wifi drop, anything that
kills `cloudflared`).

Once episodes show as fully downloaded on the Mac, sync/download to
iPhone as normal.

### 7. Verify offline, then stop the tunnel
- Turn on **Airplane Mode** on the iPhone and confirm a few episodes play
  from different points in the list (not just the newest one)
- Once confirmed, it's safe to stop the tunnel:
  ```bash
  # Ctrl+C the cloudflared process, then:
  kill %1   # stops the python http.server background job
  ```

---

## Troubleshooting

**`Missing dependency` error running the script**
→ `pip3 install mutagen Pillow --break-system-packages`

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
→ Usually a stale feed vs. tunnel URL mismatch, or the tunnel wasn't
running when Podcasts tried to fetch. Confirm the tunnel is up and
`feed.xml`'s `--base-url` matches the **current** tunnel URL, then
force-refresh in Podcasts.

**Cover artwork doesn't update after a refresh**
→ Apple caches artwork aggressively. Try a normal refresh first; if it
doesn't pick up the new image, remove the subscription and re-add it via
the same feed URL to force a completely fresh fetch.

**Tunnel URL changed and old episodes stopped loading**
→ Expected — see step 2 above. Regenerate and push `feed.xml` with the
current tunnel URL any time the tunnel restarts, even if you're not adding
new episodes.

**Want a permanent hosting solution instead of the tunnel**
→ Point `--base-url` at an S3/Cloudflare R2 bucket with public read access
instead of the tunnel URL. No uptime requirement, no changing URLs, and
sidesteps GitHub's file size and repo size limits entirely.