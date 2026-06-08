#!/usr/bin/env sh
# Optional: symlink the Goalkeeper CLI onto your PATH. No package install needed —
# the entrypoint bootstraps goalkeeper_core via sys.path (realpath-safe).
set -e
REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
TARGET="${1:-$HOME/.local/bin}"
mkdir -p "$TARGET"
ln -sf "$REPO_ROOT/bin/goalkeeper" "$TARGET/goalkeeper"
echo "linked $TARGET/goalkeeper -> $REPO_ROOT/bin/goalkeeper"
echo "ensure $TARGET is on your PATH, then: goalkeeper --version"
