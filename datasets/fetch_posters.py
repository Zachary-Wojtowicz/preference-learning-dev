#!/usr/bin/env python3
"""Fetch movie poster URLs from TMDB for the experiment interface.

Uses the TMDB API to search for movies by title and year, then saves
poster URLs to a JSON lookup file. The web interface uses these to
display poster images on option cards.

Prerequisites:
    1. Get a free TMDB API key: https://www.themoviedb.org/settings/api
    2. Set it as an environment variable or pass via --api-key

Usage:
    export TMDB_API_KEY="your_key_here"
    python datasets/fetch_posters.py \
        --input-csv datasets/movies_100/movies_100.csv \
        --output datasets/movies_100/poster_urls.json

    # Or with symlink:
    python datasets/fetch_posters.py \
        --input-csv datasets/movies_100/movielens-32m-enriched-qwen3emb-100.csv \
        --output datasets/movies_100/poster_urls.json

Output:
    JSON mapping: { "movie_id": "https://image.tmdb.org/t/p/w300/...", ... }
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse


TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w300"  # w300 is good for cards


def parse_title_year(title_str):
    """Parse 'Toy Story (1995)' → ('Toy Story', 1995)."""
    match = re.match(r"^(.+?)\s*\((\d{4})\)\s*$", title_str)
    if match:
        return match.group(1).strip(), int(match.group(2))
    return title_str.strip(), None


def search_tmdb(title, year, api_key):
    """Search TMDB for a movie by title and year. Returns poster_path or None."""
    params = {
        "api_key": api_key,
        "query": title,
        "language": "en-US",
        "page": 1,
    }
    if year:
        params["year"] = str(year)

    url = TMDB_SEARCH_URL + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = data.get("results", [])
        if results:
            # Take the first result (highest relevance)
            poster = results[0].get("poster_path")
            return poster
    except Exception as e:
        print(f"    Error searching '{title}': {e}")

    return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input-csv", required=True,
                        help="Path to movies CSV with title column")
    parser.add_argument("--output", required=True,
                        help="Path to output JSON (movie_id → poster_url)")
    parser.add_argument("--api-key", default=None,
                        help="TMDB API key (or set TMDB_API_KEY env var)")
    parser.add_argument("--id-column", default="movie_id")
    parser.add_argument("--title-column", default="title")
    parser.add_argument("--delay", type=float, default=0.25,
                        help="Seconds between API calls (default: 0.25)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("TMDB_API_KEY", "")
    if not api_key:
        print("ERROR: No TMDB API key provided.")
        print("  Get one free at: https://www.themoviedb.org/settings/api")
        print("  Then: export TMDB_API_KEY='your_key'")
        sys.exit(1)

    # Load existing results if any
    existing = {}
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing poster URLs from {args.output}")

    # Load movies
    with open(args.input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        movies = list(reader)

    print(f"Loaded {len(movies)} movies from {args.input_csv}")

    # Fetch posters
    results = dict(existing)
    fetched = 0
    skipped = 0
    failed = 0

    for i, row in enumerate(movies):
        mid = str(row[args.id_column]).strip()
        title_raw = row[args.title_column]

        if mid in results:
            skipped += 1
            continue

        title, year = parse_title_year(title_raw)
        poster_path = search_tmdb(title, year, api_key)

        if poster_path:
            results[mid] = TMDB_IMAGE_BASE + poster_path
            fetched += 1
            print(f"  [{i+1}/{len(movies)}] {title_raw} -> {poster_path}")
        else:
            # Try without year
            if year:
                poster_path = search_tmdb(title, None, api_key)
                if poster_path:
                    results[mid] = TMDB_IMAGE_BASE + poster_path
                    fetched += 1
                    print(f"  [{i+1}/{len(movies)}] {title_raw} -> {poster_path} (no year)")
                else:
                    results[mid] = None
                    failed += 1
                    print(f"  [{i+1}/{len(movies)}] {title_raw} -> NOT FOUND")
            else:
                results[mid] = None
                failed += 1
                print(f"  [{i+1}/{len(movies)}] {title_raw} -> NOT FOUND")

        time.sleep(args.delay)

    # Save
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    found = sum(1 for v in results.values() if v)
    print(f"\nWrote {args.output}")
    print(f"  Found:   {found}")
    print(f"  Missing: {sum(1 for v in results.values() if not v)}")
    print(f"  Fetched: {fetched} (skipped {skipped} cached)")


if __name__ == "__main__":
    main()
