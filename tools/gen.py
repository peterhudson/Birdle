"""Generate Birdle boards.

Each board is a 5x5 Squaredle grid with a region's birds laid in as paths of
adjacent tiles. Every word in the grid (4+ letters, adjacent tiles incl.
diagonals, no tile reused) is found and split into required words (common
English, plus the birds) and bonus words (everything else in the dictionary).

Usage: python3 tools/gen.py [region-id ...]
"""
import json, random, sys
from pathlib import Path

HERE = Path(__file__).parent
N = 5
MIN_LEN, MAX_LEN = 4, 12
ATTEMPTS = 3000
TARGET_REQUIRED = (40, 100)

def load(name):
    return [w.strip().upper() for w in open(HERE / 'data' / name)
            if w.strip() and not w.startswith('#')]

# The blocklist rejects words outright, except words we've unblocked (bird names
# like TITS, everyday words) and words that may only ever be bonus words.
bonus_only = set(load('bonus-only.txt'))
blocked = set(load('blocklist.txt')) - set(load('unblock.txt')) - bonus_only
dictionary = {w for w in load('enable1.txt') if MIN_LEN <= len(w) <= MAX_LEN and w.isalpha()} - blocked
# Required words are the ones most people know: SCOWL's American English list
# up to size 55 (common words, no proper names, American spellings only, so
# British spellings like COLOUR end up as bonus words, as in Squaredle), plus a
# few hand-picked extras.
common = set(load('scowl-american-55.txt')) & dictionary
common |= set(load('promote.txt')) & dictionary
common -= set(load('avoid.txt')) | bonus_only
regions = json.load(open(HERE / 'regions.json'))
for r in regions:
    for b in r['birds']:
        dictionary.add(b['word'])

trie = {}
for w in dictionary:
    node = trie
    for ch in w:
        node = node.setdefault(ch, {})
    node['$'] = w

NEIGHBOURS = {(r, c): [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                       if (dr or dc) and 0 <= r + dr < N and 0 <= c + dc < N]
              for r in range(N) for c in range(N)}

# Rough English letter frequencies for filling the gaps.
FILL = 'EEEEEEEEEEEAAAAAAAARRRRRRRIIIIIIIOOOOOOOTTTTTTTNNNNNNNSSSSSSLLLLLCCCCUUUUDDDPPPMMMHHHGGBBFFYYWKV'

def find_words(grid):
    """Map each word in the grid to the set of tiles any of its paths use, and its start tiles."""
    found = {}
    def dfs(pos, node, path):
        node = node.get(grid[pos[0]][pos[1]])
        if node is None:
            return
        path.append(pos)
        w = node.get('$')
        if w and len(path) >= MIN_LEN:
            uses, starts = found.setdefault(w, (set(), set()))
            uses.update(path); starts.add(path[0])
        if len(path) < MAX_LEN:
            for nb in NEIGHBOURS[pos]:
                if nb not in path:
                    dfs(nb, node, path)
        path.pop()
    for r in range(N):
        for c in range(N):
            dfs((r, c), trie, [])
    return found

def place(grid, word, rng):
    """Lay `word` into the grid along a random path, reusing matching letters."""
    def walk(i, pos, path):
        cur = grid[pos[0]][pos[1]]
        if cur not in (None, word[i]) or pos in path:
            return None
        path = path + [pos]
        if i == len(word) - 1:
            return path
        nbs = NEIGHBOURS[pos][:]
        rng.shuffle(nbs)
        for nb in nbs:
            p = walk(i + 1, nb, path)
            if p:
                return p
        return None
    starts = list(NEIGHBOURS)
    rng.shuffle(starts)
    for s in starts:
        p = walk(0, s, [])
        if p:
            for (r, c), ch in zip(p, word):
                grid[r][c] = ch
            return True
    return False

def attempt(birds, rng):
    grid = [[None] * N for _ in range(N)]
    for b in sorted(birds, key=len, reverse=True):
        if not place(grid, b, rng):
            return None
    for r in range(N):
        for c in range(N):
            if grid[r][c] is None:
                grid[r][c] = rng.choice(FILL)
    grid = [''.join(row) for row in grid]
    found = find_words(grid)
    if not all(b in found for b in birds):
        return None
    bird_forms = set(birds) | {b + 'S' for b in birds}
    required = sorted(w for w in found if w in common or w in bird_forms)
    bonus = sorted(w for w in found if w not in required)
    covered = set().union(*(found[w][0] for w in required)) if required else set()
    lo, hi = TARGET_REQUIRED
    # Every tile must be part of some required word, like Squaredle.
    if len(covered) < N * N or not lo <= len(required) <= hi:
        return None
    # Prefer grids whose filler words are plentiful but not overwhelming, with few bonus words.
    score = -abs(len(required) - 60) - 0.1 * len(bonus)
    return score, grid, required, bonus, found

def build(region, seed):
    rng = random.Random(seed)
    birds = [b['word'] for b in region['birds']]
    best = None
    for _ in range(ATTEMPTS):
        res = attempt(birds, rng)
        if res and (best is None or res[0] > best[0]):
            best = res
    if not best:
        sys.exit(f"Couldn't build a board for {region['name']}")
    _, grid, required, bonus, found = best
    idx = lambda tiles: sorted(r * N + c for r, c in tiles)
    return {'id': region['id'], 'name': region['name'], 'flag': region['flag'],
            'grid': grid, 'birds': region['birds'],
            # For each required word: the tiles it can start on and the tiles it can use,
            # which drive the red and white numbers.
            'words': [{'w': w, 's': idx(found[w][1]), 'u': idx(found[w][0])} for w in required],
            'bonus': bonus}

only = set(sys.argv[1:])
boards = []
for i, region in enumerate(regions):
    if only and region['id'] not in only:
        continue
    b = build(region, 1000 + i)
    boards.append(b)
    print(f"{b['name']:12} {' '.join(b['grid'])}  required={len(b['words'])} bonus={len(b['bonus'])}", file=sys.stderr)

out = HERE.parent / 'boards.js'
out.write_text('// Generated by tools/gen.py. Do not edit by hand.\nconst BOARDS = [\n'
               + ',\n'.join(json.dumps(b, ensure_ascii=False, separators=(',', ':')) for b in boards) + '\n];\n')
