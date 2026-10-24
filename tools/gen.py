"""Generate Birdle boards.

Each board is a square Squaredle grid (4x4, 5x5 or 7x7) with as many of a
region's birds as possible laid in as paths of adjacent tiles (at least 4).
Every word in the grid (4+ letters, adjacent tiles incl. diagonals, no tile
reused) is found and split into required words (common American English, plus
the birds) and bonus words (everything else in the dictionary). A grid that
contains any blocked word is thrown away.

Usage: python3 tools/gen.py [region-id ...]

Regions marked "draft" in regions.json are only built when named. A region's
"sizes" list sets its boards; otherwise it gets BOARDS_PER_REGION boards with
sizes drawn from SIZE_WEIGHTS.
"""
import json, random, sys
from pathlib import Path

HERE = Path(__file__).parent
MIN_LEN, MAX_LEN = 4, 12
MIN_BIRDS = 4
SIGNATURE = 8   # the first birds listed for a region are its best known, and score extra
BOARDS_PER_REGION = 3
SIZE_WEIGHTS = {4: 0.6, 5: 0.3, 7: 0.1}   # keeps most games short
# Per size: attempts, acceptable required-word range, and the count to aim for.
SETTINGS = {
    4: {'attempts': 6000, 'required': (15, 50), 'target': 30},
    5: {'attempts': 3000, 'required': (40, 100), 'target': 60},
    7: {'attempts': 300, 'required': (90, 260), 'target': 150},
}

def load(name):
    return [w.strip().upper() for w in open(HERE / 'data' / name)
            if w.strip() and not w.startswith('#')]

# Any grid containing a blocklisted word (or a simple inflection of one) is
# rejected, except for the unblocked bird names (TITS) and everyday words.
blocked_roots = {w for w in load('blocklist.txt') if w.isalpha() and len(w) >= 3} - set(load('unblock.txt'))
blocked = {root + suf for root in blocked_roots for suf in ('', 'S', 'ES', 'ED', 'ING', 'ER', 'ERS', 'Y')}
blocked = {w for w in blocked if MIN_LEN <= len(w) <= MAX_LEN} - set(load('unblock.txt'))

dictionary = {w for w in load('enable1.txt') if MIN_LEN <= len(w) <= MAX_LEN and w.isalpha()} - blocked
# Required words are the ones most people know: SCOWL's American English list
# up to size 55 (common words, no proper names, American spellings only, so
# British spellings like COLOUR end up as bonus words, as in Squaredle), plus a
# few hand-picked extras.
common = set(load('scowl-american-55.txt')) & dictionary
common |= set(load('promote.txt')) & dictionary
common -= set(load('avoid.txt'))
regions = json.load(open(HERE / 'regions.json'))
for r in regions:
    for b in r['birds']:
        dictionary.add(b['word'])

# Blocked words go in the trie too, so a grid that spells one can be spotted.
trie = {}
for w in dictionary | blocked:
    node = trie
    for ch in w:
        node = node.setdefault(ch, {})
    node['$'] = w

def neighbours(n):
    return {(r, c): [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                     if (dr or dc) and 0 <= r + dr < n and 0 <= c + dc < n]
            for r in range(n) for c in range(n)}
NEIGHBOURS = {n: neighbours(n) for n in SETTINGS}

# Rough English letter frequencies for filling the gaps.
FILL = 'EEEEEEEEEEEAAAAAAAARRRRRRRIIIIIIIOOOOOOOTTTTTTTNNNNNNNSSSSSSLLLLLCCCCUUUUDDDPPPMMMHHHGGBBFFYYWKV'

def find_words(grid):
    """Map each word in the grid to the set of tiles any of its paths use, and its start tiles."""
    n = len(grid)
    nbrs = NEIGHBOURS[n]
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
            for nb in nbrs[pos]:
                if nb not in path:
                    dfs(nb, node, path)
        path.pop()
    for pos in nbrs:
        dfs(pos, trie, [])
    return found

def place(grid, word, rng):
    """Lay `word` into the grid along a random path, reusing matching letters."""
    nbrs = NEIGHBOURS[len(grid)]
    def walk(i, pos, path):
        cur = grid[pos[0]][pos[1]]
        if cur not in (None, word[i]) or pos in path:
            return None
        path = path + [pos]
        if i == len(word) - 1:
            return path
        nbs = nbrs[pos][:]
        rng.shuffle(nbs)
        for nb in nbs:
            p = walk(i + 1, nb, path)
            if p:
                return p
        return None
    starts = list(nbrs)
    rng.shuffle(starts)
    for s in starts:
        p = walk(0, s, [])
        if p:
            for (r, c), ch in zip(p, word):
                grid[r][c] = ch
            return True
    return False

def attempt(n, birds, rng, used):
    grid = [[None] * n for _ in range(n)]
    # Try the birds in a random order, keeping every one that still fits.
    order = [b for b in birds if len(b) <= n * n]
    rng.shuffle(order)
    for b in order:
        place(grid, b, rng)
    for r in range(n):
        for c in range(n):
            if grid[r][c] is None:
                grid[r][c] = rng.choice(FILL)
    grid = [''.join(row) for row in grid]
    found = find_words(grid)
    if any(w in blocked for w in found):
        return None
    on_board = [b for b in birds if b in found]
    if len(on_board) < MIN_BIRDS:
        return None
    bird_forms = set(on_board) | {b + 'S' for b in on_board}
    required = sorted(w for w in found if w in common or w in bird_forms)
    bonus = sorted(w for w in found if w not in required)
    covered = set().union(*(found[w][0] for w in required))
    lo, hi = SETTINGS[n]['required']
    # Every tile must be part of some required word, like Squaredle.
    if len(covered) < n * n or not lo <= len(required) <= hi:
        return None
    # More birds first, favouring signature birds and ones the region's other boards
    # haven't used; then a comfortable number of words and few bonus words.
    bird_score = sum(100 + (60 if birds.index(b) < SIGNATURE else 0) - (50 if b in used else 0) for b in on_board)
    score = bird_score - abs(len(required) - SETTINGS[n]['target']) - 0.1 * len(bonus)
    return score, grid, on_board, required, bonus, found

def build(region, n, seed, used):
    rng = random.Random(seed)
    birds = [b['word'] for b in region['birds']]
    best = None
    for _ in range(SETTINGS[n]['attempts']):
        res = attempt(n, birds, rng, used)
        if res and (best is None or res[0] > best[0]):
            best = res
    if not best:
        sys.exit(f"Couldn't build a {n}x{n} board for {region['name']}")
    _, grid, on_board, required, bonus, found = best
    idx = lambda tiles: sorted(r * n + c for r, c in tiles)
    return {'region': region['id'], 'name': region['name'], 'flag': region['flag'], 'size': n,
            'grid': grid, 'birds': [b for b in region['birds'] if b['word'] in on_board],
            # For each required word: the tiles it can start on and the tiles it can use,
            # which drive the red and white numbers.
            'words': [{'w': w, 's': idx(found[w][1]), 'u': idx(found[w][0])} for w in required],
            'bonus': bonus}

def sizes_for(region, seed):
    if 'sizes' in region:
        return region['sizes']
    rng = random.Random(seed)
    return sorted(rng.choices(list(SIZE_WEIGHTS), weights=list(SIZE_WEIGHTS.values()), k=BOARDS_PER_REGION))

only = set(sys.argv[1:])
boards = []
for i, region in enumerate(regions):
    if (only and region['id'] not in only) or (not only and region.get('draft')):
        continue
    used = set()
    for k, n in enumerate(sizes_for(region, 1000 + i)):
        b = build(region, n, 1000 + 100 * i + k, used)
        used |= {x['word'] for x in b['birds']}
        b['id'] = f"{region['id']}-{k + 1}"
        boards.append(b)
        print(f"{b['id']:14} {n}x{n} {' '.join(b['grid'])}  birds={','.join(x['word'] for x in b['birds'])} "
              f"required={len(b['words'])} bonus={len(b['bonus'])}", file=sys.stderr)

out = HERE.parent / 'boards.js'
out.write_text('// Generated by tools/gen.py. Do not edit by hand.\nconst BOARDS = [\n'
               + ',\n'.join(json.dumps(b, ensure_ascii=False, separators=(',', ':')) for b in boards) + '\n];\n')
