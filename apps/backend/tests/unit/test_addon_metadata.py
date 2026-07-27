"""Guards on the add-on's published version.

Home Assistant pulls `<image>:<version>` using the `version` field from
`config.yaml`, and for a repository add-on it reads that file straight from
the git repo rather than from the image. So a forgotten bump does not fail
loudly — users simply stay on the old image with no update prompt, and the
release workflow happily publishes a tag nobody pulls.

These run in the normal backend suite so drift is caught on the pull request
that introduced it, rather than at release time.
"""

import re
from pathlib import Path

from ruamel.yaml import YAML

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG = _REPO_ROOT / "home-curator" / "config.yaml"
_CHANGELOG = _REPO_ROOT / "home-curator" / "CHANGELOG.md"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
# Matches "## 0.1.0" and "## 0.1.0 — 2026-04-22", with or without a `v`.
_HEADING = re.compile(r"^##\s+v?(\d+\.\d+\.\d+)", re.MULTILINE)


def _declared_version() -> str:
    data = YAML(typ="safe").load(_CONFIG.read_text())
    return str(data["version"])


def _changelog_versions() -> list[str]:
    return _HEADING.findall(_CHANGELOG.read_text())


def test_addon_version_is_semver():
    """The Supervisor uses this verbatim as a Docker tag."""
    version = _declared_version()
    assert _SEMVER.match(version), (
        f"config.yaml declares version {version!r}, which is not "
        "MAJOR.MINOR.PATCH"
    )


def test_image_reference_carries_no_tag():
    """A tag baked into `image:` would silently override `version:`."""
    data = YAML(typ="safe").load(_CONFIG.read_text())
    image = str(data["image"])
    # Strip a registry host:port before looking for a tag separator.
    last_segment = image.rsplit("/", 1)[-1]
    assert ":" not in last_segment, (
        f"config.yaml image {image!r} pins a tag; the Supervisor appends "
        "`version` itself"
    )


def test_changelog_documents_the_declared_version():
    """The newest CHANGELOG entry must be the version being shipped.

    Catches the common miss: bumping one of the two and not the other.
    """
    versions = _changelog_versions()
    assert versions, "CHANGELOG.md has no version headings"
    assert versions[0] == _declared_version(), (
        f"config.yaml declares {_declared_version()!r} but the newest "
        f"CHANGELOG entry is {versions[0]!r} — bump both together"
    )


def test_changelog_versions_are_unique():
    versions = _changelog_versions()
    assert len(versions) == len(set(versions)), (
        f"duplicate CHANGELOG headings: {versions}"
    )
