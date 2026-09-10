#!/bin/sh
# Regenerates DesignMyRoom.xcodeproj from project.yml. Always use this instead of
# calling `xcodegen generate` directly: project.yml reads DEVELOPMENT_TEAM from the
# DESIGNMYROOM_DEV_TEAM environment variable, and XcodeGen has no "${VAR:-default}"
# syntax — a variable that's merely *unset* (as opposed to set-but-empty) leaves the
# literal "${DESIGNMYROOM_DEV_TEAM}" text sitting in the generated setting instead of
# resolving to an empty, automatically-signed default. This script guarantees it's
# always defined before xcodegen ever sees it.
#
# xcodegen.env (committed, empty default) + .env (gitignored, your real Team id) —
# same layering as the repo's own compose.env/.env. Put one line in ios/.env:
#   DESIGNMYROOM_DEV_TEAM=YOUR_TEAM_ID
# and it survives every regeneration from here on, instead of being silently reset
# to empty each time.
set -eu
cd "$(dirname "$0")"

for env_file in xcodegen.env .env; do
  if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1090
    . "./$env_file"
    set +a
  fi
done

: "${DESIGNMYROOM_DEV_TEAM:=}"
export DESIGNMYROOM_DEV_TEAM

exec xcodegen generate --spec project.yml
