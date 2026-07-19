#!/usr/bin/env python3
"""
generate_feed.py

Scans a folder of session subfolders containing .m4a files and generates a
podcast RSS feed (feed.xml) using itunes:season / itunes:episode tags, so
Apple Podcasts groups episodes by session correctly.

Expected layout:
    episodes/
      session-01/
        01-some-topic.m4a
        02-another-topic.m4a
      session-02/
        01-topic.m4a
        ...

Optional manifest.csv (relpath,title,description) gives clean titles instead
of deriving them from filenames.

Usage:
    python3 generate_feed.py \
        --audio-dir episodes \
        --base-url https://YOURUSERNAME.github.io/YOURREPO/episodes \
        --title "My NotebookLM Overviews" \
        --author "Your Name" \
        --description "Private feed of NotebookLM Audio Overviews" \
        --manifest manifest.csv \
        --output feed.xml
"""

import argparse
import csv
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import quote
from xml.sax.saxutils import escape

try:
    from mutagen.mp4 import MP4
except ImportError:
    sys.exit("Missing dependency. Run: pip install mutagen --break-system-packages")

SESSION_RE = re.compile(r"session[-_ ]?(\d+)", re.IGNORECASE)
# Matches: PREFIX-NN-Title.m4a  or  PREFIX-NN-NN-Title.m4a
# (e.g. OPRA-01-Clinical_ADME...  or  OPRA-02-01-Smuggling_Dopamine...)
# The LAST number group before the title is treated as the episode number.
FILENAME_RE = re.compile(r"^[A-Za-z]+[-_](\d+)(?:[-_](\d+))?[-_](.+)$")
ANCHOR = datetime(2024, 1, 1, tzinfo=timezone.utc)


def parse_filename(filename):
    """Returns (episode_num_or_None, title) parsed from a filename like
    'OPRA-01-Clinical_ADME_and_Half-Life_for_OPRA.m4a' or
    'OPRA-02-01-Smuggling_Dopamine_Into_the_Parkinsonian_Brain.m4a'."""
    stem = os.path.splitext(filename)[0]
    match = FILENAME_RE.match(stem)
    if not match:
        return None, stem.replace("_", " ").replace("-", " ").strip()
    g1, g2, rest = match.groups()
    episode_num = int(g2) if g2 else int(g1)
    title = rest.replace("_", " ").strip()
    return episode_num, title


def get_duration_seconds(filepath):
    # Try mutagen first (fast, no subprocess).
    try:
        length = MP4(filepath).info.length
        if length and length > 0:
            return int(length)
    except Exception:
        pass

    # Fall back to ffprobe, which tolerates malformed/edge-case MP4 headers
    # that mutagen sometimes can't parse (common with some NotebookLM exports).
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=30,
        )
        duration = float(result.stdout.strip())
        if duration > 0:
            return int(duration)
    except Exception:
        pass

    return 0


def seconds_to_hms(seconds):
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def load_manifest(path):
    manifest = {}
    if not path:
        return manifest
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            manifest[row["relpath"].strip()] = row
    return manifest


def discover_episodes(audio_dir):
    """Returns list of dicts: {relpath, filepath, season, episode, title}."""
    episodes = []
    session_dirs = sorted(
        d for d in os.listdir(audio_dir)
        if os.path.isdir(os.path.join(audio_dir, d))
    )

    if not session_dirs:
        # Flat layout fallback: treat everything as season 1
        files = sorted(f for f in os.listdir(audio_dir) if f.lower().endswith(".m4a"))
        for i, fname in enumerate(files, start=1):
            ep_num, title = parse_filename(fname)
            episodes.append({
                "relpath": fname,
                "filepath": os.path.join(audio_dir, fname),
                "season": 1,
                "episode": ep_num or i,
                "title": title,
            })
        return episodes

    for d in session_dirs:
        match = SESSION_RE.search(d)
        season = int(match.group(1)) if match else 1
        dirpath = os.path.join(audio_dir, d)
        files = sorted(f for f in os.listdir(dirpath) if f.lower().endswith(".m4a"))
        for i, fname in enumerate(files, start=1):
            ep_num, title = parse_filename(fname)
            episodes.append({
                "relpath": f"{d}/{fname}",
                "filepath": os.path.join(dirpath, fname),
                "season": season,
                "episode": ep_num or i,
                "title": title,
            })
    return episodes


def build_item(ep, base_url, manifest):
    row = manifest.get(ep["relpath"])
    title = (row["title"].strip() if row and row.get("title") else None) or ep["title"]
    description = (row.get("description", "").strip() if row else "") or title

    size_bytes = os.path.getsize(ep["filepath"])
    duration = get_duration_seconds(ep["filepath"])
    file_url = f"{base_url.rstrip('/')}/{quote(ep['relpath'])}"

    # Deterministic pubDate: doesn't shift on re-runs as you add sessions.
    pub_dt = ANCHOR + timedelta(days=(ep["season"] - 1) * 30, minutes=ep["episode"])
    pub_date = format_datetime(pub_dt)

    return f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(description)}</description>
      <enclosure url="{escape(file_url)}" length="{size_bytes}" type="audio/x-m4a" />
      <guid isPermaLink="false">{escape(file_url)}</guid>
      <pubDate>{pub_date}</pubDate>
      <itunes:season>{ep['season']}</itunes:season>
      <itunes:episode>{ep['episode']}</itunes:episode>
      <itunes:duration>{seconds_to_hms(duration)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>"""


def main():
    parser = argparse.ArgumentParser(description="Generate a season/episode-organized podcast RSS feed.")
    parser.add_argument("--audio-dir", required=True, help="Folder containing session-XX subfolders of .m4a files")
    parser.add_argument("--base-url", required=True, help="Public base URL for the audio-dir contents (e.g. GitHub Pages episodes folder)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--link", default=None)
    parser.add_argument("--manifest", default=None, help="Optional CSV: relpath,title,description")
    parser.add_argument("--output", default="feed.xml")
    args = parser.parse_args()

    link = args.link or args.base_url
    manifest = load_manifest(args.manifest)
    episodes = discover_episodes(args.audio_dir)

    if not episodes:
        sys.exit(f"No .m4a files found under {args.audio_dir}")

    # Feed order: newest session/episode first, matches typical podcast app expectation.
    episodes.sort(key=lambda e: (e["season"], e["episode"]), reverse=True)

    items = [build_item(ep, args.base_url, manifest) for ep in episodes]
    build_date = format_datetime(datetime.now(timezone.utc))

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(args.title)}</title>
    <link>{escape(link)}</link>
    <description>{escape(args.description)}</description>
    <language>en-us</language>
    <itunes:author>{escape(args.author)}</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="Education" />
    <itunes:type>episodic</itunes:type>
    <lastBuildDate>{build_date}</lastBuildDate>
    <atom:link href="{escape(link)}/feed.xml" rel="self" type="application/rss+xml" />
{chr(10).join(items)}
  </channel>
</rss>
"""

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(rss)

    seasons = sorted(set(e["season"] for e in episodes))
    print(f"Wrote {args.output}: {len(episodes)} episode(s) across {len(seasons)} session(s) {seasons}.")

    zero_duration = [e["relpath"] for e in episodes if get_duration_seconds(e["filepath"]) == 0]
    if zero_duration:
        print(f"\nWarning: could not read duration for {len(zero_duration)} file(s) "
              f"(mutagen and ffprobe both failed) — check these aren't corrupted:")
        for rp in zero_duration:
            print(f"  - {rp}")


if __name__ == "__main__":
    main()