#!/usr/bin/env python3
"""Builds a VPM listing (index.json) and a landing page from GitHub releases.

Each package repository's Release workflow attaches three assets to a release:
<name>-<version>.zip, <name>-<version>.zip.sha256 and package.json. This script reads those
releases, copies each package.json into the listing with "url" (the zip) and "zipSHA256", and
writes index.json plus index.html into the output folder. Only the standard library is used.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def fetch(url, token, accept="application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": "vpm-listing-builder"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def releases(repo, token):
    result = []
    page = 1
    while True:
        try:
            data = json.loads(fetch(f"{API}/repos/{repo}/releases?per_page=100&page={page}", token))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                # A repository that does not exist yet (or is private to this token) simply contributes nothing.
                print(f"skip {repo}: not found", file=sys.stderr)
                return result
            raise
        if not data:
            return result
        result.extend(data)
        page += 1


def collect(repo, token, packages):
    """Adds every release of one repository that carries the expected assets."""
    for release in releases(repo, token):
        tag = release.get("tag_name", "?")
        if release.get("draft"):
            continue
        assets = {asset["name"]: asset for asset in release.get("assets", [])}
        zips = [asset for name, asset in assets.items() if name.endswith(".zip")]
        if "package.json" not in assets or len(zips) != 1:
            print(f"skip {repo}@{tag}: needs package.json and exactly one .zip asset", file=sys.stderr)
            continue
        zip_asset = zips[0]
        package = json.loads(fetch(assets["package.json"]["browser_download_url"], token, "application/octet-stream"))
        name, version = package.get("name"), package.get("version")
        if not name or not version:
            print(f"skip {repo}@{tag}: package.json without name/version", file=sys.stderr)
            continue
        if tag != "v" + version:
            print(f"skip {repo}@{tag}: tag does not match version {version}", file=sys.stderr)
            continue

        package["url"] = zip_asset["browser_download_url"]
        sha_asset = assets.get(zip_asset["name"] + ".sha256")
        if sha_asset:
            package["zipSHA256"] = fetch(sha_asset["browser_download_url"], token, "application/octet-stream").decode().split()[0]
        else:
            package["zipSHA256"] = hashlib.sha256(fetch(package["url"], token, "application/octet-stream")).hexdigest()
        package.setdefault("repo", f"https://github.com/{repo}")
        packages.setdefault(name, {})[version] = package
        print(f"{name} {version} <- {repo}@{tag}")


_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?")


def semver_key(version):
    match = _SEMVER.match(version)
    if not match:
        return (0, 0, 0, 0, version)
    major, minor, patch, pre = match.groups()
    # A pre-release sorts before the release of the same number.
    return (int(major), int(minor), int(patch), 0 if pre else 1, pre or "")


def latest(versions):
    stable = [v for v in versions if "-" not in v]
    pool = stable or list(versions)
    return max(pool, key=semver_key)


def render_html(listing):
    url = listing["url"]
    vcc = "vcc://vpm/addRepo?url=" + urllib.request.quote(url, safe="")
    rows = []
    for name in sorted(listing["packages"]):
        versions = listing["packages"][name]["versions"]
        if not versions:
            continue
        current = versions[latest(versions)]
        rows.append(
            "<tr><td><code>{name}</code><br>{display}</td><td>{version}</td><td>{unity}</td>"
            "<td><a href=\"{repo}\">{repo_short}</a></td></tr>".format(
                name=html.escape(name),
                display=html.escape(current.get("displayName", "")),
                version=html.escape(latest(versions)),
                unity=html.escape(current.get("unity", "")),
                repo=html.escape(current.get("repo", "")),
                repo_short=html.escape(current.get("repo", "").replace("https://github.com/", "")),
            )
        )
    table = "\n".join(rows) or "<tr><td colspan=\"4\">まだ公開されたバージョンはありません。</td></tr>"
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(listing['name'])} の VPM パッケージ</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }}
  .button {{ display: inline-block; padding: .6rem 1.2rem; border-radius: 6px; background: #3b6ef5; color: #fff; text-decoration: none; font-weight: 600; }}
  code {{ background: #eee; padding: .1rem .3rem; border-radius: 3px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border-bottom: 1px solid #ddd; padding: .4rem .5rem; text-align: left; vertical-align: top; }}
</style>
</head>
<body>
<h1>{html.escape(listing['name'])} の VPM パッケージ</h1>
<p>{html.escape(listing.get('description', ''))}</p>
<p><a class="button" href="{html.escape(vcc)}">VCC / ALCOM に追加</a></p>
<p>ボタンが動かないときは、VCC の <b>Settings &gt; Packages &gt; Add Repository</b>（ALCOM は <b>設定 &gt; リポジトリを追加</b>）に次の URL を貼り付けてください。</p>
<p><code>{html.escape(url)}</code></p>
<h2>パッケージ</h2>
<table>
<tr><th>パッケージ</th><th>最新</th><th>Unity</th><th>リポジトリ</th></tr>
{table}
</table>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="sources.json")
    parser.add_argument("--url", required=True, help="public URL of index.json, written into the listing")
    parser.add_argument("--out", default="_site")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    with open(args.sources, encoding="utf-8") as handle:
        sources = json.load(handle)

    packages = {}
    for repo in sources["repositories"]:
        collect(repo, token, packages)

    listing = {
        "name": sources["name"],
        "id": sources["id"],
        "url": args.url,
        "author": sources.get("author", ""),
        "description": sources.get("description", ""),
        "packages": {name: {"versions": dict(sorted(versions.items(), key=lambda item: semver_key(item[0])))}
                     for name, versions in sorted(packages.items())},
    }

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(listing, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as handle:
        handle.write(render_html(listing))
    count = sum(len(v) for v in packages.values())
    print(f"wrote {args.out}/index.json with {len(packages)} packages, {count} versions")


if __name__ == "__main__":
    main()
