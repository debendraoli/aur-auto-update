#!/usr/bin/env python3
import json
import sys
import requests
import traceback
from pathlib import Path

import toml
import yaml
from github import Github

token = toml.load("config/keyfile.toml")["keys"]["github"]
github = Github(token)
session = requests.Session()


def warn(message):
    print(f"::warning::{message}")


def error(message):
    print(f"::error::{message}")


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
            with open(config) as f:
                config = yaml.safe_load(f)
            flag = config.get("flag", False)
            test = config.get("test", False)
            if session.get(f'https://aur.archlinux.org/pkgbase/{package}').status_code == 404:
                warn(f"{package} {version} is available upstream but does not exist "
                     f"on AUR. Publish it to AUR or remove it from config; it will "
                     f"not be auto-updated until then.")
                continue
            if test:
                clean = config.get("clean-up-ubuntu", 'false')
                repo = github.get_repo('debendraoli/aur-auto-update')
                workflow = repo.get_workflow("build.yml")
                workflow.create_dispatch('main', {'pkgbase': package, 'pkgver': version, 'clean-up-ubuntu': clean})
                print(f"Triggered build test for {package} {version}.")
            elif flag:
                warn(f"{package} {version} detected but flagging on AUR is not "
                     f"implemented yet; no action taken.")
                # TODO: Flag the package on AUR
            else:
                warn(f"{package} {version} detected but no action (test/flag) is "
                     f"configured for it.")
        except StopIteration:
            error(f"{package} reported as updated to {version} but no matching "
                  f"config/**/{package}.yaml was found.")
            had_error = True
        except Exception:
            error(f"Failed to trigger the update for {package} {version}.")
            traceback.print_exc()
            had_error = True
    elif event != "up-to-date":
        # nvchecker could not determine a version (source error, rate limit, ...).
        warn(f"nvchecker could not check {package}: event={event!r}.")

with open("nvtake.txt", "w") as f:
    f.write(" ".join(nvtake))

if had_error:
    error("One or more updates could not be processed; see the errors above.")
    sys.exit(1)

