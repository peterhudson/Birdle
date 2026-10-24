# Birdle

A bird-themed take on [Squaredle](https://squaredle.app/). Each board is a grid of letters set in a
birding region, with some of that region's signature birds hidden among the words.

## Playing

Find words of 4 or more letters by connecting neighbouring squares (including diagonals), either by
swiping or by typing and pressing Enter. Each square can be used once per word. As the progress bar
fills you earn the same help as Squaredle:

1. ★ Red numbers: how many words start on each square. This star is worth the same as all the
   board's birds, so finding the birds first earns it.
2. ★ White numbers: how many words use each square.
3. ★ Hints: show each missing word's first letter and sort the word list alphabetically.

## Running locally

It's a static site with no build step:

```sh
python3 -m http.server
```

then open http://localhost:8000.

## Adding or changing boards

Regions and their birds live in `tools/regions.json`. List a region's best-known birds first: the
first eight score extra when the generator picks which birds to place. Regenerate the boards with:

```sh
python3 tools/gen.py              # all regions not marked "draft"
python3 tools/gen.py bc           # just one region
```

Each region gets five boards: Express (3×3), Easy (4×4), Medium (5×5), Hard (6×6) and Extreme Birder
(7×7). For each board the generator places as many of the region's birds as it can (at least 4, or 1
on the 3×3 Express), fills the gaps, and finds every word on the board. Common American English
words (SCOWL up to size 55) become required words; everything else in the dictionary, including
British spellings, counts as a bonus word. To move a word across that line, add it to
`tools/data/avoid.txt` or `tools/data/promote.txt` and regenerate.

Any board that spells a word from `tools/data/blocklist.txt` is thrown away, apart from the bird
names and everyday words listed in `tools/data/unblock.txt`. Word list sources and licenses are in
`tools/data/SOURCES.md`.

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
