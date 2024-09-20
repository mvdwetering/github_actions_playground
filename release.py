#!/usr/bin/env python3
"""Helper script for release related tasks."""

import argparse
from enum import Enum
import logging
import subprocess
import json

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

def get_release_type():
    while True:
        str_choice = input("What type of release is this?\n  1 = Major\n  2 = Minor\n  3 = Patch\n: ")
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

def get_current_branch():
    branch_name = subprocess.check_output(["git", "branch", "--show-current"])
    return Branch(branch_name.decode("utf-8").strip())

def get_versions():
    version_tags = subprocess.check_output(["git", "tag", "-l", "v*"])

    awesome_versions = []
    for version_tag in version_tags.decode("utf-8").split("\n"):
        version = AwesomeVersion(version_tag[1:])
        if version.valid:
            awesome_versions.append(version)

    awesome_versions.sort()
    return awesome_versions

def workarea_is_clean():
    return subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8").strip() == ""

def get_integration_name():
    return "integration_name"

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

def checkout_branch(branch):
    subprocess.run(["git", "checkout", branch])

def add_changes():
    subprocess.run(["git", "add", "--all"])

def commit_changes(message):
    subprocess.run(["git", "commit", "-m", message])

def merge_to_master(release_branch, message):
    subprocess.run(["git", "checkout", MASTER])    
    subprocess.run(["git", "pull"])
    subprocess.run(["git", "merge", "--no-ff", release_branch, "--strategy-option theirs", "-m", message])

def delete_release_branch(release_branch):
    subprocess.run(["git", "branch", "-D", release_branch])

def create_tag(tag_name):
    subprocess.run(["git", "tag", tag_name])

def push_to_origin(branch):
    subprocess.run(["git", "push", "origin", branch])

def get_last_released_version():
    versions = get_versions()
    logging.debug(f"Versions: {versions}")
    return versions[-1]


def main(args):

    logging.basicConfig(level=args.loglevel)

    branch = get_current_branch()
    logging.info(f"Current branch: {branch.name}")

    if not workarea_is_clean():
        logging.error("Workarea is not clean")
        # exit(1) TODO ENABLE ME

    if args.command == "release":
        if branch.is_dev:
            last_released_version = get_last_released_version()
            release_type = get_release_type()

            next_version = determine_next_version(last_released_version, release_type)
            logging.debug(f"Next version: {next_version}")

            print(f"Previous version was {last_released_version}")
            if input(f"Confirm next {release_type.name} release version {next_version}? [y/N]: ") != "y":
                exit(1)

            release_branch_name = f"release/{next_version}"
            tag_name = f"v{next_version}"

            checkout_branch(release_branch_name)

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

        logging.debug(f"Release branch: {release_branch_name}")
        logging.debug(f"Tag name: {tag_name}")

        update_manifest_version_number(next_version)
        add_changes()
        commit_changes("Update version to {next_version}")

        if release_type != ReleaseType.BETA:
            merge_to_master(release_branch_name, f"Release v{next_version}")

        create_tag(tag_name)

        if input("Push to origin? [y/N]: ") != "y":
            exit(1)

        if release_type != ReleaseType.BETA:
            push_to_origin(MASTER)

        push_to_origin(release_branch_name)
        push_to_origin(tag_name)
        

        # Restore initial branch
        checkout_branch(branch.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "command",
        help="Command to execute.",
        choices=["release", "create-release-branch"],
        nargs="?",
    )

    parser.add_argument(
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Define loglevel, default is INFO.",
    )
    args = parser.parse_args()

    main(args)
