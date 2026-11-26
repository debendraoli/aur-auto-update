#!/usr/bin/env python3
import json
import sys
import traceback
from pathlib import Path

import requests
import toml
import yaml
from github import Github
from github.GithubException import GithubException
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    Retry = None

token = toml.load("config/keyfile.toml")["keys"]["github"]
github = Github(token)

session = requests.Session()
if Retry is not None:
    _retry = Retry(total=5, connect=5, read=5, backoff_factor=1,
                   status_forcelist=(500, 502, 503, 504),
                   allowed_methods=frozenset({"GET"}))
    session.mount("https://", HTTPAdapter(max_retries=_retry))


def warn(message):
    print(f"::warning::{message}")


def error(message):
    print(f"::error::{message}")


def aur_pkgbase_exists(package):
    """True/False when AUR answered, or None when AUR could not be reached.

    A transient network failure must not be mistaken for a missing package, so
    it is reported separately and treated as non-fatal by the caller.
    """
    try:
        response = session.get(
            f"https://aur.archlinux.org/pkgbase/{package}", timeout=30)
    except requests.exceptions.RequestException:
        return None
    return response.status_code != 404


with open("nvchecker.log") as f:
    lines = f.readlines()

nvtake = []
had_error = False
for line in lines:
    line = json.loads(line.strip("\n"))
    if 'name' not in line:
        # nvchecker summary / diagnostic lines without a package name.
        continue
    package = line["name"]
    event = line.get("event")
    if event == "updated":
        version = line["version"]
        try:
            config = next(Path("config").rglob(f"{package}.yaml"))
        except StopIteration:
            error(f"{package} reported as updated to {version} but no matching "
                  f"config/**/{package}.yaml was found.")
            had_error = True
            continue
        with open(config) as f:
            config = yaml.safe_load(f)
        flag = config.get("flag", False)
        test = config.get("test", False)

        exists = aur_pkgbase_exists(package)
        if exists is None:
            # Transient infrastructure issue, not an update failure: the next
            # scheduled run retries, so warn (visible) without failing the run.
            warn(f"Could not reach AUR to check {package} {version}; it will be "
                 f"retried on the next run.")
            continue
        if not exists:
            warn(f"{package} {version} is available upstream but does not exist "
                 f"on AUR. Publish it to AUR or remove it from config; it will "
                 f"not be auto-updated until then.")
            continue

        if test:
            clean = config.get("clean-up-ubuntu", 'false')
            try:
                repo = github.get_repo('debendraoli/aur-auto-update')
                workflow = repo.get_workflow("build.yml")
                workflow.create_dispatch('main', {'pkgbase': package, 'pkgver': version, 'clean-up-ubuntu': clean})
            except (GithubException, requests.exceptions.RequestException):
                error(f"Failed to trigger the build test for {package} {version}.")
                traceback.print_exc()
                had_error = True
                continue
            print(f"Triggered build test for {package} {version}.")
        elif flag:
            warn(f"{package} {version} detected but flagging on AUR is not "
                 f"implemented yet; no action taken.")
            # TODO: Flag the package on AUR
        else:
            warn(f"{package} {version} detected but no action (test/flag) is "
                 f"configured for it.")
    elif event != "up-to-date":
        # nvchecker could not determine a version (source error, rate limit, ...).
        warn(f"nvchecker could not check {package}: event={event!r}.")

with open("nvtake.txt", "w") as f:
    f.write(" ".join(nvtake))

if had_error:
    error("One or more updates could not be processed; see the errors above.")
    sys.exit(1)


