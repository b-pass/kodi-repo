#!/usr/bin/env python3
"""Publish the b-pass Kodi add-on repositories.

Builds two Kodi repositories from the add-ons' GitHub repos and pushes them
to this repo's gh-pages branch:
  /     repository.b-pass      latest published release of each add-on
  /dev  repository.b-pass.dev  default branch (main) of each add-on, plus the
                               dev-only add-ons in GITHUB_FOLDERS

Safe to run any time: nothing is pushed if a download fails, or if the
result is identical to what is already published.
"""
import argparse
import functools
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / '_site'
GITHUB_REPOS = [
    'b-pass/plugin.video.byu-tv',
    'b-pass/plugin.video.the-chosen',
    'b-pass/plugin.video.hoopla',
    'b-pass/script.centerstage',
]

# Dev-only add-ons kept in a folder of a bigger repo: (repo, branch, folder).
GITHUB_FOLDERS = [
    ('b-pass/xbmc', 'myth-estuary-omega', 'addons/skin.estuary'),  # skin.myth-estuary
]

# Dev-only files left out of the zips (matched against any path component).
EXCLUDE = {
    '.git', '.github', '.gitignore', '.gitattributes', '__pycache__', '.vscode',
    'CLAUDE.md', 'API_NOTES.md', 'tests', 'tools', 'install-local',
}

# Zip timestamp for local files, so unchanged sources give byte-identical zips.
FIXED_STAMP = (1980, 1, 1, 0, 0, 0)


def warn(msg):
    print(f'  warning: {msg}')


def fetch(url, missing_ok=False):
    """Download url. With missing_ok, a 404 returns None; other errors abort the run."""
    request = urllib.request.Request(url, headers={'User-Agent': 'b-pass-kodi-repo'})
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404 and missing_ok:
            return None
        raise


# Archive readers all return {relative path: (bytes, zip date_time)}, with the
# single top-level folder that archives wrap everything in removed.

def strip_top_dir(files):
    return {name.split('/', 1)[1]: v for name, v in files.items() if '/' in name}


def read_zip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return strip_top_dir({i.filename: (zf.read(i), i.date_time)
                              for i in zf.infolist() if not i.is_dir()})


def read_tarball(data, folder=''):
    """With folder, only the files under that folder, relative to it."""
    prefix = f'{folder}/' if folder else ''
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r|gz') as tar:
        for m in tar:
            name = m.name.partition('/')[2]
            if m.isfile() and name.startswith(prefix) and name != prefix:
                # UTC, so the zips come out the same on any machine.
                files[name[len(prefix):]] = (tar.extractfile(m).read(), time.gmtime(m.mtime)[:6])
    return files


def read_dir(src):
    return {str(p.relative_to(src)): (p.read_bytes(), FIXED_STAMP)
            for p in sorted(src.rglob('*')) if p.is_file()}


def read_release(repo):
    """Files of a repo's latest release: its .zip asset, else the tag's source."""
    data = fetch(f'https://api.github.com/repos/{repo}/releases/latest', missing_ok=True)
    if data is None:
        warn('no published release (or repo missing/private), skipped')
        return None
    release = json.loads(data)
    tag = release['tag_name']
    zips = [a for a in release['assets'] if a['name'].endswith('.zip')]
    if zips:
        print(f'  release {tag}, asset {zips[0]["name"]}')
        files = read_zip(fetch(zips[0]['browser_download_url']))
    else:
        print(f'  release {tag}, no .zip asset, using its source')
        files = read_tarball(fetch(f'https://github.com/{repo}/archive/refs/tags/{tag}.tar.gz'))

    version = addon_version(files)
    if version and tag.lstrip('v') != version:
        warn(f'release {tag} contains addon.xml version {version}; Kodi will see it as {version}')
    return files


def read_dev(repo, branch=None, folder=''):
    """Files of a repo's branch (default: the default branch), or of a folder in
    it, versioned <version>.dev<YYYYMMDD>.<HHMMSS>.

    The suffix is the commit time (UTC), so each new commit is an update in
    Kodi, while still sorting below the next release. It's split in two so
    each number fits in a 32-bit long, which Kodi uses to compare versions.
    """
    ref = f'refs/heads/{branch}' if branch else 'HEAD'
    data = fetch(f'https://github.com/{repo}/archive/{ref}.tar.gz', missing_ok=True)
    if data is None:
        warn('repo/branch missing, private or empty, skipped')
        return None
    files = read_tarball(data, folder)
    if 'addon.xml' in files:
        # git archive stamps every file with the commit time.
        xml, commit_time = files['addon.xml']
        suffix = '.dev{:04}{:02}{:02}.{:02}{:02}{:02}'.format(*commit_time).encode()
        xml = re.sub(rb'(<addon\b[^>]*?\bversion="[^"]+)', lambda m: m[1] + suffix, xml, count=1)
        files['addon.xml'] = (xml, commit_time)
    print(f'  {branch or "default"} branch' + (f', {folder}' if folder else ''))
    return files


def addon_version(files):
    if 'addon.xml' in files:
        return ET.fromstring(files['addon.xml'][0]).get('version')
    return None


def sha256_sidecar(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(f'{path}.sha256').write_text(f'{digest}  {path.name}\n')


def package(files, zips):
    """Write one add-on's zip and artwork; returns (id, version, addon.xml text)."""
    if 'addon.xml' not in files:
        warn('no addon.xml at the top of the archive, skipped')
        return None
    xml_text = files['addon.xml'][0].decode('utf-8')
    root = ET.fromstring(xml_text)
    addon_id, version = root.get('id'), root.get('version')

    out_dir = zips / addon_id
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f'{addon_id}-{version}.zip'
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for name, (data, date_time) in sorted(files.items()):
            if EXCLUDE.intersection(Path(name).parts) or name.endswith('.pyc'):
                continue
            info = zipfile.ZipInfo(f'{addon_id}/{name}', max(date_time, FIXED_STAMP))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    sha256_sidecar(zip_path)
    print(f'  built {addon_id} {version}')

    # Kodi fetches artwork from <datadir>/<id>/<asset path>.
    assets = root.find(".//extension[@point='xbmc.addon.metadata']/assets")
    for asset in (assets if assets is not None else []):
        rel = (asset.text or '').strip()
        if rel in files:
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(files[rel][0])

    return addon_id, version, xml_text


def build_repo(out, repo_addon, sources):
    """Build one Kodi repository into out; returns its repository add-on zip.

    sources is a list of (name, function returning the add-on's files or None).
    """
    zips = out / 'zips'
    print(f'{repo_addon.name} (local):')
    built = [package(read_dir(repo_addon), zips)]
    for name, read in sources:
        print(f'{name}:')
        files = read()
        if files and (addon := package(files, zips)):
            built.append(addon)

    body = ''.join(re.sub(r'^\s*<\?xml[^>]*\?>\s*', '', xml).rstrip() + '\n'
                   for _, _, xml in built)
    addons_xml = zips / 'addons.xml'
    addons_xml.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                          f'<addons>\n{body}</addons>\n', encoding='utf-8')
    sha256_sidecar(addons_xml)

    # A copy of the repository add-on at the top, for "Install from zip file".
    repo_id, repo_version, _ = built[0]
    repo_zip = out / f'{repo_id}-{repo_version}.zip'
    shutil.copy(zips / repo_id / repo_zip.name, repo_zip)
    print('\n' + ''.join(f'{i} {v}\n' for i, v, _ in built))
    return repo_zip


def build_site():
    shutil.rmtree(SITE, ignore_errors=True)
    release = [(repo, functools.partial(read_release, repo)) for repo in GITHUB_REPOS]
    dev = ([(repo, functools.partial(read_dev, repo)) for repo in GITHUB_REPOS]
           + [(f'{repo} {branch}', functools.partial(read_dev, repo, branch, folder))
              for repo, branch, folder in GITHUB_FOLDERS])
    repo_zips = [build_repo(SITE, ROOT / 'repository.b-pass', release),
                 build_repo(SITE / 'dev', ROOT / 'repository.b-pass.dev', dev)]
    links = ''.join(f'<a href="{href}">{href}</a><br>\n'
                    for href in (html.escape(str(z.relative_to(SITE))) for z in repo_zips))
    (SITE / 'index.html').write_text(
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
        f'<title>b-pass Kodi repository</title></head><body>\n{links}</body></html>\n')
    (SITE / '.nojekyll').touch()  # serve the files as-is


def git(*args, env=None):
    result = subprocess.run(['git', '-C', str(ROOT), *args],
                            capture_output=True, text=True, env=env)
    if result.returncode:
        sys.exit(f'git {args[0]} failed, nothing published:\n{result.stderr.strip()}')
    return result.stdout.strip()


def publish():
    """Force-push SITE as a single commit on origin's gh-pages branch, if it changed."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, 'GIT_INDEX_FILE': os.path.join(tmp, 'index')}
        git('--work-tree', str(SITE), 'add', '--all', '--force', env=env)
        tree = git('write-tree', env=env)
    if git('ls-remote', '--heads', 'origin', 'gh-pages'):
        git('fetch', '--quiet', '--depth', '1', 'origin', 'gh-pages')
        if git('rev-parse', 'FETCH_HEAD^{tree}') == tree:
            print('Nothing changed; already published.')
            return
    commit = git('commit-tree', tree, '-m', 'Publish')
    git('push', '--quiet', '--force', 'origin', f'{commit}:refs/heads/gh-pages')
    print(f'Published {commit[:7]} to gh-pages.')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--no-push', action='store_true',
                        help='only build into _site/, to look at it')
    args = parser.parse_args()
    if not args.no_push:
        git('remote', 'get-url', 'origin')  # fail before the downloads, not after

    try:
        build_site()
    except urllib.error.URLError as e:
        sys.exit(f'Download failed, nothing published: {e}')

    if not args.no_push:
        publish()


if __name__ == '__main__':
    main()
