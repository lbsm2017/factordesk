#!/bin/sh
# factordesk bootstrap for macOS and Linux.
#
# What it does, in order:
#   1. optionally checks its own SHA-256 against the value published with the release;
#   2. installs uv with uv's official installer, only if uv is missing;
#   3. runs the pinned release: uvx --from factordesk==VERSION factordesk serve --open
#
# Read it before you run it. It is short on purpose. See docs/release-checklist.md for how the
# release checksum is made and docs/dashboard.md for how to use it.
#
# Usage:
#   sh install.sh --version 0.1.0 [--expect-sha256 HEX] [--uv-sha256 HEX] [--dry-run]
#                 [--no-open] [-- EXTRA ARGS FOR "factordesk serve"]
#
#   --version V         release to run (required; no "latest", so a run is repeatable)
#   --expect-sha256 H   SHA-256 of this file, copied from the release page; stops on a mismatch
#   --uv-sha256 H       SHA-256 of uv's installer for the pinned uv version, if you have it
#   --dry-run           print what would happen and change nothing
#   --no-open           do not open the browser

set -eu

# uv version whose installer this script downloads (documented form:
# https://docs.astral.sh/uv/getting-started/installation/ ). Change it with a new release.
UV_VERSION="0.11.28"
UV_INSTALLER_URL="https://astral.sh/uv/${UV_VERSION}/install.sh"

version=""
expect_sha=""
uv_sha=""
dry_run=0
open_flag="--open"

die() {
    echo "install.sh: error: $*" >&2
    exit 1
}

usage() {
    sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d ' ' -f 1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d ' ' -f 1
    else
        die "no sha256sum or shasum found; cannot verify a checksum"
    fi
}

is_sha256() {
    printf '%s' "$1" | grep -Eq '^[0-9a-fA-F]{64}$'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --version) [ $# -ge 2 ] || die "--version needs a value"; version="$2"; shift 2 ;;
        --expect-sha256) [ $# -ge 2 ] || die "--expect-sha256 needs a value"; expect_sha="$2"; shift 2 ;;
        --uv-sha256) [ $# -ge 2 ] || die "--uv-sha256 needs a value"; uv_sha="$2"; shift 2 ;;
        --dry-run) dry_run=1; shift ;;
        --no-open) open_flag=""; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; break ;;
        *) die "unknown option: $1 (try --help)" ;;
    esac
done

[ -n "$version" ] || die "--version is required, for example: --version 0.1.0"
printf '%s' "$version" | grep -Eq '^[0-9]+(\.[0-9]+)*([.-]?[A-Za-z0-9]+)*$' \
    || die "version '$version' does not look like a release number"
[ -z "$expect_sha" ] || is_sha256 "$expect_sha" || die "--expect-sha256 must be 64 hex digits"
[ -z "$uv_sha" ] || is_sha256 "$uv_sha" || die "--uv-sha256 must be 64 hex digits"

# 1. Check this file against the published checksum. This catches a damaged or swapped download.
# It cannot protect you if the place you got both the script and the checksum from is hacked, so
# take the checksum from the release page and the script from the same tagged release.
if [ -n "$expect_sha" ]; then
    actual=$(sha256_of "$0")
    expected=$(printf '%s' "$expect_sha" | tr 'A-F' 'a-f')
    [ "$actual" = "$expected" ] || die "checksum mismatch for $0: expected $expected, got $actual"
    echo "Checksum of this script matches the published value."
fi

# 2. Find uv. The uv installer puts it in ~/.local/bin, which may not be on PATH yet.
PATH="$HOME/.local/bin:$PATH"
export PATH
if command -v uvx >/dev/null 2>&1; then
    have_uv=1
else
    have_uv=0
fi

run_line="uvx --from factordesk==$version factordesk serve"
if [ -n "$open_flag" ]; then run_line="$run_line $open_flag"; fi
if [ $# -gt 0 ]; then run_line="$run_line $*"; fi

echo "This script will:"
if [ "$have_uv" -eq 1 ]; then
    echo "  1. keep your existing uv ($(command -v uvx))"
else
    echo "  1. download uv's installer from $UV_INSTALLER_URL"
    if [ -n "$uv_sha" ]; then
        echo "     and check its SHA-256 against the value you gave"
    fi
    echo "     and run it (puts uv in ~/.local/bin and adds that folder to your shell profile)"
fi
echo "  2. run: $run_line"
echo "     (uv downloads factordesk $version from PyPI into its cache; nothing else is installed)"
echo "     The dashboard stays running until you press Ctrl+C."

if [ "$dry_run" -eq 1 ]; then
    echo "Dry run: nothing was downloaded, installed or started."
    exit 0
fi

if [ "$have_uv" -eq 0 ]; then
    tmp=$(mktemp "${TMPDIR:-/tmp}/uv-install.XXXXXX")
    trap 'rm -f "$tmp"' EXIT
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf "$UV_INSTALLER_URL" -o "$tmp" || die "could not download $UV_INSTALLER_URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$tmp" "$UV_INSTALLER_URL" || die "could not download $UV_INSTALLER_URL"
    else
        die "neither curl nor wget is installed; install uv by hand from https://docs.astral.sh/uv/"
    fi
    if [ -n "$uv_sha" ]; then
        actual=$(sha256_of "$tmp")
        expected=$(printf '%s' "$uv_sha" | tr 'A-F' 'a-f')
        [ "$actual" = "$expected" ] || die "uv installer checksum mismatch: expected $expected, got $actual"
    fi
    sh "$tmp"
    command -v uvx >/dev/null 2>&1 || die "uv was installed but uvx is not on PATH; open a new shell and run this script again"
fi

# 3. Run the pinned release. "$@" holds the extra arguments given after "--".
if [ -n "$open_flag" ]; then
    exec uvx --from "factordesk==$version" factordesk serve "$open_flag" "$@"
fi
exec uvx --from "factordesk==$version" factordesk serve "$@"
