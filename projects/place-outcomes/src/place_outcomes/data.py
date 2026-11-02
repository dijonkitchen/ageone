"""Download each source into a cache with its URL, date, and SHA-256 digest recorded."""

import hashlib
import json
import urllib.request
from datetime import date
from pathlib import Path

from place_outcomes.config import SOURCES, Paths

USER_AGENT = "ageone-place-outcomes (https://github.com/dijonkitchen/ageone)"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(paths: Paths, refresh: bool = False) -> dict[str, dict[str, str]]:
    """Download missing files (Zillow's monthly file always, since it changes monthly) and write the manifest."""
    paths.raw.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, str]] = json.loads(paths.manifest.read_text()) if paths.manifest.exists() else {}
    for name, url in SOURCES.items():
        out = paths.raw / name
        if out.exists() and not (refresh or name == "zhvi.csv"):
            if name not in manifest:  # a file placed by hand still gets its digest recorded
                manifest[name] = {"url": url, "fetched": "unknown", "sha256": digest(out)}
            continue
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        tmp = out.with_suffix(".part")
        with urllib.request.urlopen(request, timeout=600) as response:
            tmp.write_bytes(response.read())
        tmp.replace(out)  # never leave a half-written file where `build` would read it
        manifest[name] = {"url": url, "fetched": date.today().isoformat(), "sha256": digest(out)}
    paths.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest
