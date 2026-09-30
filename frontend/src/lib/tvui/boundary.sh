#!/bin/sh
# The one rule $lib/tvui exists to enforce, checked rather than remembered: a
# screen may not draw a button, a pill, a portrait, a grid or a focus ring of its
# own. Those come from the layer. See README.md beside this file.
#
# Five signatures, because they are the five that were actually being copied:
# a bare outline:none, a pill radius, a declared column track, a circle, and a
# `.go` class — the primary button redrawn under Press's own name.
#
# It is a RATCHET, not a gate. There are violations on the day it is written and
# clearing them is staged work; a check that is red from its first run is a check
# nobody reads. So it fails on anything ABOVE the count below, and the count only
# ever goes down. Lowering it is part of finishing a sweep — if a sweep leaves it
# where it was, the sweep did not happen.
set -eu
cd "$(dirname "$0")/../.."

# 27: the faces and the menu say where the remote is through marks.css, the
# vault's mosaic and the output pill went to Wall and Press, and the `.go`
# signature added the one enter key it finds. Before that 31 after the Portrait
# sweep taught the check to see circles, 26 after Choose, 27 after Press, 42
# after Wall, 51 honest at the start.
ALLOWED=25

# The pill pattern was `var(--radius-pill)` alone, which missed every
# `var(--radius-pill, 999px)` and every bare `999px` — nine more of them, in
# files the check was reporting as clean. A check that undercounts is worse than
# none: it says a sweep is finished when it is not.
found=$(grep -rnE 'outline:[[:space:]]*none|border-radius:[[:space:]]*(var\(--radius-pill|999px|50%)|grid-template-columns:[[:space:]]*repeat\(|^[[:space:]]*\.go[[:space:]]*[{,]' \
	lib/parts lib/screens lib/tv routes 2>/dev/null || true)
count=$(printf '%s\n' "$found" | grep -c . || true)

if [ "$count" -gt "$ALLOWED" ]; then
	printf '%s\n' "$found" | sed 's/^/  /'
	echo ""
	echo "boundary: $count local draws, $ALLOWED allowed."
	echo "A pill, a ring or a grid belongs in \$lib/tvui. See src/lib/tvui/README.md."
	exit 1
fi

if [ "$count" -lt "$ALLOWED" ]; then
	echo "boundary: $count local draws against an allowance of $ALLOWED."
	echo "Lower ALLOWED to $count — an allowance nobody lowers is an allowance."
	exit 1
fi

exit 0
