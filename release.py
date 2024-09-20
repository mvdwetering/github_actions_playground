#!/usr/bin/env python3
"""Helper script for release related tasks."""

import argparse
from enum import Enum
import logging
import subprocess
import json
import os

from awesomeversion import AwesomeVersion

MASTER = "master"	

class ReleaseType(Enum):
    MAJOR = 1
    MINOR = 2
    PATCH = 3
    BETA = 4

class Branch:
    def __init__(self, name):
        self.name = name

    @property
    def is_dev(self):
        return self.name == "dev"
    
    @property
    def is_release(self):
        return self.name.startswith("release/")

class Git():

    @staticmethod
    def get_current_branch() -> Branch:
        branch_name = subprocess.check_output(["git", "branch", "--show-current"])
        return Branch(branch_name.decode("utf-8").strip())

    @staticmethod
    def workarea_is_clean() -> bool:
        return subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8").strip() == ""

    @staticmethod
    def checkout(branch):
        subprocess.run(["git", "checkout", branch])

    @staticmethod
    def add_changes():
        subprocess.run(["git", "add", "--all"])

    @staticmethod
    def commit_changes(message):
        subprocess.run(["git", "commit", "-m", message])

    @staticmethod
    def pull():
        subprocess.run(["git", "pull"])

    @staticmethod
    def delete_branch(name):
        subprocess.run(["git", "branch", "-D", name])

    @staticmethod
    def create_tag(name):
        subprocess.run(["git", "tag", name])

    @staticmethod
    def push_to_origin(name):
        subprocess.run(["git", "push", "origin", name])

    @staticmethod
    def fetch_tags():
        subprocess.run(["git", "fetch", "--tags"])


def get_release_type():
    while True:
        str_choice = input("What type of release is this?\n  1 = Major\n  2 = Minor\n  3 = Patch\n  4 = Beta\n: ")
        try:
            choice = int(str_choice)
        except ValueError:
            print("Invalid input, please enter a number")
            continue
        if choice == 1:
            return ReleaseType.MAJOR
        elif choice == 2:
            return ReleaseType.MINOR
        elif choice == 3:
            return ReleaseType.PATCH
        elif choice == 4:
            return ReleaseType.BETA
        else:
            print("Invalid input, please enter a valid number")

def determine_next_version(version, release_type):
    if release_type == ReleaseType.MAJOR:
        return AwesomeVersion(f"{int(version.major) + 1}.0.0")
    elif release_type == ReleaseType.MINOR:
        return AwesomeVersion(f"{version.major}.{int(version.minor) + 1}.0")
    elif release_type == ReleaseType.PATCH:
        return AwesomeVersion(f"{version.major}.{version.minor}.{int(version.patch) + 1}")
    elif release_type == ReleaseType.BETA:
        return AwesomeVersion(f"{version.major}.{version.minor}.{version.patch}b{int(version.beta) + 1}")

    raise ValueError(f"Invalid release type: {release_type}")


def get_versions():
    version_tags = subprocess.check_output(["git", "tag", "-l", "v*"])

    awesome_versions = []
    for version_tag in version_tags.decode("utf-8").split("\n"):
        version = AwesomeVersion(version_tag[1:])
        if version.valid:
            awesome_versions.append(version)

    awesome_versions.sort()
    return awesome_versions


def get_integration_name():
    dir_list = [name for name in os.listdir("custom_components") if os.path.isdir(os.path.join("custom_components", name))]
    if len(dir_list) != 1:
        raise ValueError(f"Expected one directory below custom_components, but found {', '.join(dir_list)}")
    return dir_list[0]
    

def update_manifest_version_number(version):
    manifest_file = "custom_components/{}/manifest.json".format(get_integration_name())

    with open(manifest_file) as f:
        manifest = json.load(f)

    manifest["version"] = str(version)
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

def get_version_from_manifest():
    manifest_file = "custom_components/{}/manifest.json".format(get_integration_name())

    with open(manifest_file) as f:
        manifest = json.load(f)

    return AwesomeVersion(manifest["version"])


def get_last_released_version():
    versions = get_versions()
    logging.debug(f"Versions: {versions}")
    return versions[-1]


def main(args):
    branch = Git.get_current_branch()

    if not Git.workarea_is_clean():
        logging.error("Workarea is not clean")
        exit(1)

    Git.fetch_tags()

    if branch.is_dev:
        last_released_version = get_last_released_version()
        release_type = get_release_type()

        next_version = determine_next_version(last_released_version, release_type)
        logging.debug(f"Next version: {next_version}")

    if branch.is_release:
        current_version = get_version_from_manifest()
        if current_version == AwesomeVersion("0.0.0"):
            current_version = AwesomeVersion(branch.name.split("/")[1])

        next_version = determine_next_version(current_version, release_type)
        logging.debug(f"Next version: {next_version}")

        print(f"Previous version was {last_released_version}")
        if input(f"Confirm next {release_type.name} release version {next_version}? [y/N]: ") != "y":
            exit(1)

        release_branch_name = f"release/{next_version}"
        tag_name = f"v{next_version}"


    print(f"Previous version was {last_released_version}")
    if input(f"Confirm next {release_type.name} release version {next_version}? [y/N]: ") != "y":
        exit(1)

    release_branch_name = f"release/{next_version}"
    tag_name = f"v{next_version}"
    logging.debug(f"Release branch: {release_branch_name}")
    logging.debug(f"Tag name: {tag_name}")

    if branch.name != release_branch_name:
        Git.checkout(release_branch_name)

    update_manifest_version_number(next_version)
    Git.add_changes()
    Git.commit_changes("Update version to {next_version}")

    if release_type != ReleaseType.BETA:
        # Merge to master
        Git.checkout(MASTER)
        Git.pull()
        subprocess.run(["git", "merge", "--no-ff", release_branch_name, "--strategy-option theirs", "-m", f"Release v{next_version}"])

    Git.create_tag(tag_name)

    if input("Push to origin? [y/N]: ") != "y":
        exit(1)

    if Git.get_current_branch() == MASTER:
        Git.push_to_origin(MASTER)

    Git.push_to_origin(release_branch_name)
    Git.push_to_origin(tag_name)
    

    # Restore initial branch
    Git.checkout(branch.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Define loglevel, default is INFO.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    main(args)
