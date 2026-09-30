# `$lib/tvui` — the ten-foot vocabulary

Everything a television screen is made of, in one place, so that no two OPUS TV
screens can disagree about what a pill, a button, a portrait, a grid or a focus
ring is.

## Why this is a directory and not a second submodule

`$lib/opus` is a submodule (`Bacinac/opus-ui`) because three modules share it.
This is not shared with anybody:

- A ten-foot button is not a desk button with more padding: it is a different
  focus model. So `Press` is what a television presses, and the package's
  `Button` is drawn only on the pages a desk reads — settings, the vault, a
  series laid out as the Library lays it out.
- The leak was already measurable. The package's head for a page about one
  thing (`MediaHead`) reads variables only `tv/tenfoot.css`
  defines, and every one of them is a television accommodation — each costing
  a commit there plus a pointer bump in three repositories and putting an
  untested change into two productions with no interest in it.
- A television is a surface, not a theme. The spatial engine, the rail, the level
  machine and the back ladder have no meaning in a module with no remote.

A submodule exists to be shared, and this would have exactly one consumer. If
Library ever grows a television, promoting this directory is a `git subtree
split` away — building it that way first would be paying for sharing that does
not exist.

What genuinely IS shared — the brand, the palette, i18n, the marks, the door —
stays in `$lib/opus` and is imported from there.

## The boundary, which is checked rather than remembered

No `<style>` block under `lib/parts/**` or `lib/screens/**` may define a button,
a pill, a portrait, a grid or a focus ring. Those come from here.

`./check.sh` greps for the signatures that mean somebody has redrawn one of them
locally — a bare `outline: none`, a pill radius, a circle, a
`grid-template-columns: repeat(` and a `.go` class — outside this directory, and
fails on any more of them than the count it allows.

A control that says where the remote is in a mark of its own — a word in the
menu, a face — carries `data-own-mark`, and `marks.css` stands in for the ring.
