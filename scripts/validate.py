#!/usr/bin/env python3
"""Checks ONIBORN's update configuration the way the game reads it, and more strictly.

Usage: python3 scripts/validate.py [versions.json ...] [--changelogs DIR]

Standard library only. The JSON Schema (versions.schema.json) checks the shape; this script
adds what a schema cannot: minSupportedBuild <= latestBuild, the store pages of this game
only, release notes with an English fallback, and warnings for anything that forces players.
Exit code 0 when every file is valid, 1 otherwise.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PACKAGE = "com.oniborn.app"
MAX_BUILD = 2_100_000_000
VERSION = re.compile(r"^\d{1,5}\.\d{1,5}\.\d{1,5}$")
LANGUAGE = re.compile(r"^[a-z]{2,3}(_[a-z0-9]{2,8}){0,2}$")
APP_STORE_PATH = re.compile(r"^/([a-z]{2}/)?app/([^/]+/)?id\d{1,12}$")
SETTINGS = {
    "reminderIntervalHours": (1, 720),
    "checkIntervalHours": (1, 168),
    "requestTimeoutSeconds": (1, 30),
    "maxCacheAgeHours": (1, 720),
}
PLATFORMS = ("android", "ios")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def version_key(text):
    return tuple(int(part) for part in text.split("."))


def store_url_problem(platform, url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port or parts.fragment:
        return "must be a plain https address"
    if platform == "android":
        if parts.hostname != "play.google.com" or parts.path != "/store/apps/details":
            return "must be https://play.google.com/store/apps/details?id=" + PACKAGE
        if parse_qs(parts.query).get("id") != [PACKAGE]:
            return "must name id=" + PACKAGE
    else:
        if parts.hostname != "apps.apple.com" or not APP_STORE_PATH.match(parts.path):
            return "must be an App Store product page, https://apps.apple.com/app/id<digits>"
    return None


def check_platform(name, block, errors, warnings):
    where = name
    if not isinstance(block, dict):
        errors.append(f"{where} is not an object")
        return
    for key, kind in (("enabled", bool), ("forceUpdateEnabled", bool)):
        if not isinstance(block.get(key), kind):
            errors.append(f"{where}.{key} must be true or false")
    version = block.get("latestVersion")
    if not isinstance(version, str) or not VERSION.match(version):
        errors.append(f"{where}.latestVersion must be major.minor.patch, like 1.5.0")
    for key in ("latestBuild", "minSupportedBuild"):
        value = block.get(key)
        if not is_int(value) or not 1 <= value <= MAX_BUILD:
            errors.append(f"{where}.{key} must be a whole number from 1 to {MAX_BUILD}")
    latest, minimum = block.get("latestBuild"), block.get("minSupportedBuild")
    if is_int(latest) and is_int(minimum) and minimum > latest:
        errors.append(f"{where}.minSupportedBuild ({minimum}) is above latestBuild ({latest})")
    if "storeUrl" not in block:
        errors.append(f"{where}.storeUrl is missing (null when there is no store page yet)")
    url = block.get("storeUrl")
    if url is None:
        if block.get("enabled") is True:
            errors.append(f"{where} is enabled without a storeUrl")
    elif not isinstance(url, str):
        errors.append(f"{where}.storeUrl must be text or null")
    elif problem := store_url_problem(name, url):
        errors.append(f"{where}.storeUrl {problem}")
    notes = block.get("releaseNotes", {})
    if not isinstance(notes, dict):
        errors.append(f"{where}.releaseNotes must be an object of language: [notes]")
    else:
        if len(notes) > 40:
            errors.append(f"{where}.releaseNotes has more than 40 languages")
        for tag, items in notes.items():
            if not LANGUAGE.match(tag.replace("-", "_").lower()):
                errors.append(f"{where}.releaseNotes: '{tag}' is not a language tag (en, ru, pt_BR, zh_Hant)")
            if not isinstance(items, list) or len(items) > 12:
                errors.append(f"{where}.releaseNotes.{tag} must be a list of at most 12 notes")
                continue
            for item in items:
                if not isinstance(item, str) or not item.strip() or len(item) > 300:
                    errors.append(f"{where}.releaseNotes.{tag} holds an empty, non-text or over 300 character note")
        if notes and "en" not in notes:
            errors.append(f"{where}.releaseNotes needs 'en': it is the fallback of every other language")
    if block.get("forceUpdateEnabled") is True:
        if block.get("enabled") is not True:
            warnings.append(f"{where}.forceUpdateEnabled is on while {where} is disabled: nothing is forced")
        elif is_int(latest) and is_int(minimum) and minimum <= 1:
            warnings.append(f"{where}.forceUpdateEnabled is on but minSupportedBuild is 1: nothing is forced")
        else:
            warnings.append(
                f"{where}: FORCED UPDATE ON for builds below {minimum}. Only after the build is live and"
                " installable for the whole audience (see README, 'Requiring an update')."
            )
            if name == "ios":
                warnings.append("ios: forced updates are enforced only when Apple's lookup lists the version")


def check_config(path):
    errors, warnings = [], []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"not valid JSON: {error}"], warnings
    if not isinstance(data, dict):
        return ["the root must be an object"], warnings
    if data.get("schemaVersion") != 1 or not is_int(data.get("schemaVersion")):
        errors.append("schemaVersion must be 1 (the schema every released game reads)")
    if not isinstance(data.get("updateCheckEnabled"), bool):
        errors.append("updateCheckEnabled must be true or false")
    elif data["updateCheckEnabled"] is False:
        warnings.append("updateCheckEnabled is false: the kill switch is on, nothing is shown or required")
    for name in PLATFORMS:
        if name in data:
            check_platform(name, data[name], errors, warnings)
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        errors.append("settings must be an object")
    else:
        for key, (low, high) in SETTINGS.items():
            if key in settings and (not is_int(settings[key]) or not low <= settings[key] <= high):
                errors.append(f"settings.{key} must be a whole number from {low} to {high}")
    return errors, warnings


def check_changelog(path):
    errors = []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"not valid JSON: {error}"]
    releases = data.get("releases") if isinstance(data, dict) else None
    if not isinstance(releases, list):
        return ["must be {\"releases\": [...]}"]
    previous = None
    for index, release in enumerate(releases):
        where = f"releases[{index}]"
        if not isinstance(release, dict):
            errors.append(f"{where} is not an object")
            continue
        version = release.get("version")
        if not isinstance(version, str) or not VERSION.match(version):
            errors.append(f"{where}.version must be major.minor.patch")
        elif previous is not None and version_key(version) >= version_key(previous):
            errors.append(f"{where}.version {version} must be older than {previous}: newest first")
        else:
            previous = version
        if not is_int(release.get("build")) or release["build"] < 1:
            errors.append(f"{where}.build must be a positive whole number")
        if not isinstance(release.get("date"), str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", release["date"]):
            errors.append(f"{where}.date must be YYYY-MM-DD")
        notes = release.get("notes")
        if not isinstance(notes, list) or not all(isinstance(n, str) and n.strip() for n in notes):
            errors.append(f"{where}.notes must be a list of text")
    return errors


def main(argv):
    configs, changelogs = [], None
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--changelogs":
            changelogs = args.pop(0)
        else:
            configs.append(arg)
    if not configs and changelogs is None:
        configs = ["versions.json"]
        changelogs = "changelogs"
    failed = False
    for path in configs:
        errors, warnings = check_config(path)
        for warning in warnings:
            print(f"::warning file={path}::{warning}")
        for error in errors:
            print(f"::error file={path}::{error}")
        print(f"{path}: {'INVALID' if errors else 'ok'}")
        failed |= bool(errors)
    if changelogs is not None:
        files = sorted(Path(changelogs).glob("*.json"))
        if not any(file.stem == "en" for file in files):
            print(f"::error::{changelogs}/en.json is missing")
            failed = True
        for file in files:
            if not LANGUAGE.match(file.stem.replace("-", "_").lower()):
                print(f"::error file={file}::the file name must be a language tag (en.json, ru.json)")
                failed = True
            errors = check_changelog(file)
            for error in errors:
                print(f"::error file={file}::{error}")
            print(f"{file}: {'INVALID' if errors else 'ok'}")
            failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
