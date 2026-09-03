"""Stamp the firmware with the version git reports, before each build.

A hand-edited CLIENT_VERSION drifts from the tags. This derives it instead,
so a device's boot log always identifies the commit it was built from:

    v1.5.1                    built from the tag
    v1.5.1-3-gab12cd4         three commits past it
    v1.5.1-3-gab12cd4-dirty   with uncommitted changes

Falls back to "dev" when git cannot answer — no binary, no repository, or a
shallow clone with no tags. CI needs fetch-depth: 0 to see tags.
"""
import subprocess

Import("env")  # noqa: F821 - injected by PlatformIO


def git_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=env.subst("$PROJECT_DIR"),  # noqa: F821
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip() or "dev"
    except Exception:
        return "dev"


version = git_version()
print(f"CLIENT_VERSION: {version}")
env.Append(CPPDEFINES=[("CLIENT_VERSION", env.StringifyMacro(version))])  # noqa: F821
