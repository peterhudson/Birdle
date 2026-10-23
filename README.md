# Birdle

A bird-themed take on [Squaredle](https://squaredle.app/). Each board is a grid of letters set in a
birding region, with some of that region's signature birds hidden among the words.

## Playing

Find words of 4 or more letters by connecting neighbouring squares (including diagonals), either by
swiping or by typing and pressing Enter. Each square can be used once per word. As the progress bar
fills you earn the same help as Squaredle:

1. ★ Red numbers: how many words start on each square.
2. ★ White numbers: how many words use each square.
3. ★ Hints: show each missing word's first letter and sort the word list alphabetically.

## Running locally

It's a static site with no build step:

```sh
python3 -m http.server
```

then open http://localhost:8000.

## Adding or changing boards

Regions and their birds live in `tools/regions.json`. Regenerate the boards with:

```sh
python3 tools/gen.py              # all regions
python3 tools/gen.py bc           # just one
```

The generator lays each region's birds into a 5×5 grid, fills the gaps, and finds every word on the
board. Familiar words become required words; the rest of the dictionary counts as bonus words. If a
required word feels too obscure or is a proper name, add it to `tools/data/avoid.txt` and regenerate.
Word list sources and licenses are in `tools/data/SOURCES.md`.

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
