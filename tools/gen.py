"""Generate Birdle boards.

Each board is a square Squaredle grid (4x4, 5x5 or 7x7) with as many of a
region's birds as possible laid in as paths of adjacent tiles (at least 4).
Every word in the grid (4+ letters, adjacent tiles incl. diagonals, no tile
reused) is found and split into required words (common American English, plus
the birds) and bonus words (everything else in the dictionary). A grid that
contains any blocked word is thrown away.

Usage: python3 tools/gen.py [region-id ...]

Regions marked "draft" in regions.json are only built when named. A region's
Every region gets one board per level in LEVELS, from a 3x3 Express to a 7x7
Extreme Birder.
"""
import json, random, sys
from pathlib import Path

HERE = Path(__file__).parent
MIN_LEN, MAX_LEN = 4, 12
SIGNATURE = 8   # the first birds listed for a region are its best known, and score extra
# One board per level for every region: (id, name, size, minimum and maximum birds,
# lengths of the birds it places). A 3x3 only has room for one or two birds. Each bird
# goes on only one of a region's boards, so the maximums and lengths share the birds out:
# short birds for the small boards, long ones for the big boards, and whatever is left
# for the last board.
LEVELS = [
    ('express', 'Express', 3, 1, 3, (4, 6)),
    ('easy', 'Easy', 4, 4, 5, (4, 6)),
    ('medium', 'Medium', 5, 4, 5, (5, 8)),
    ('hard', 'Hard', 6, 4, 6, (6, 10)),
    ('extreme', 'Extreme Birder', 7, 4, 8, (4, 12)),
]
# Per size: attempts, acceptable required-word range, and the count to aim for.
SETTINGS = {
    3: {'attempts': 20000, 'required': (6, 30), 'target': 14},
    4: {'attempts': 6000, 'required': (15, 50), 'target': 30},
    5: {'attempts': 3000, 'required': (40, 100), 'target': 60},
    6: {'attempts': 800, 'required': (70, 180), 'target': 110},
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
# Bird words in general (OWLET, KITE, SWAN...). One that turns up on a board by
# chance becomes a surprise bird: a required word that scores and shows like a bird.
surprise_birds = {b['word']: b for b in json.load(open(HERE / 'data' / 'bird-words.json'))}

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

def attempt(n, birds, candidates, rng, used, min_birds, max_birds):
    grid = [[None] * n for _ in range(n)]
    # Try the birds in a random order, keeping every one that still fits.
    order = candidates[:]
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
    # Each of a region's birds belongs to just one of its boards.
    if any(b in found for b in used):
        return None
    on_board = [b for b in birds if b in found]
    if not min_birds <= len(on_board) <= max_birds:
        return None
    bird_forms = set(on_board) | {b + 'S' for b in on_board}
    required = sorted(w for w in found if w in common or w in bird_forms)
    bonus = sorted(w for w in found if w not in required)
    covered = set().union(*(found[w][0] for w in required))
    lo, hi = SETTINGS[n]['required']
    # Every tile must be part of some required word, like Squaredle.
    if len(covered) < n * n or not lo <= len(required) <= hi:
        return None
    # More birds first, favouring signature birds; then a comfortable number of words
    # and few bonus words.
    bird_score = sum(100 + (60 if birds.index(b) < SIGNATURE else 0) for b in on_board)
    score = bird_score - abs(len(required) - SETTINGS[n]['target']) - 0.1 * len(bonus)
    return score, grid, on_board, required, bonus, found

def build(region, n, seed, used, seen, min_birds, max_birds, lengths):
    rng = random.Random(seed)
    birds = [b['word'] for b in region['birds']]
    # Leave out birds that hold another board's bird (GOSHAWK holds HAWK) or a blocked word.
    inside = lambda b: {b[i:j] for i in range(len(b)) for j in range(i + MIN_LEN, len(b) + 1)}
    candidates = [b for b in birds if lengths[0] <= len(b) <= lengths[1] and b not in used
                  and not inside(b) & (used | blocked)]
    best = None
    # Some regions' birds are hard to fit; if no grid works, keep trying for longer.
    for tries in range(4):
        for _ in range(SETTINGS[n]['attempts'] * 2 ** tries):
            res = attempt(n, birds, candidates, rng, used, min_birds, max_birds)
            if res and (best is None or res[0] > best[0]):
                best = res
        if best:
            break
    if not best:
        raise RuntimeError(f"Couldn't build a {n}x{n} board for {region['name']}")
    _, grid, on_board, required, bonus, found = best
    # Surprise birds are added after the grid is chosen, so they never change which grid wins.
    # One the region's other boards already have is just a word here.
    surprises = [surprise_birds[w] | {'note': f"A surprise bird! It isn't one of the {region['name']} birds this board was built around, but it's a bird all the same.", 'extra': True}
                 for w in sorted(found) if w in surprise_birds and w not in on_board and w not in seen]
    extra = {w for s in surprises for w in (s['word'], s['word'] + 'S') if w in found}
    required = sorted(set(required) | extra)
    bonus = [w for w in bonus if w not in extra]
    idx = lambda tiles: sorted(r * n + c for r, c in tiles)
    return {'region': region['id'], 'name': region['name'], 'flag': region['flag'], 'group': region.get('group', ''), 'size': n,
            'grid': grid, 'birds': [b for b in region['birds'] if b['word'] in on_board] + surprises,
            # For each required word: the tiles it can start on and the tiles it can use,
            # which drive the red and white numbers.
            'words': [{'w': w, 's': idx(found[w][1]), 'u': idx(found[w][0])} for w in required],
            'bonus': bonus}

def build_region(job):
    i, region = job
    used, seen, boards = set(), set(), []
    for k, (level, label, n, min_birds, max_birds, lengths) in enumerate(LEVELS):
        # A region's seed is fixed in regions.json once it has boards, so reordering regions keeps them.
        b = build(region, n, 1000 + 100 * region.get('seed', i) + k, used, seen, min_birds, max_birds, lengths)
        used |= {x['word'] for x in b['birds'] if not x.get('extra')}
        seen |= {x['word'] for x in b['birds'] if x.get('extra')}
        b['id'] = f"{region['id']}-{level}"
        b['level'] = label
        boards.append(b)
        print(f"{b['id']:14} {n}x{n} {' '.join(b['grid'])}  birds={','.join(x['word'] for x in b['birds'])} "
              f"required={len(b['words'])} bonus={len(b['bonus'])}", file=sys.stderr, flush=True)
    return region['id'], boards

if __name__ == '__main__':
    from multiprocessing import Pool
    out = HERE.parent / 'boards.js'
    only = set(sys.argv[1:])
    live = [r for r in regions if not r.get('draft') or r['id'] in only]
    # Naming regions rebuilds just those and keeps every other region's boards as they are.
    kept = {}
    if only and out.exists():
        text = out.read_text()
        for b in json.loads(text[text.index('['):text.rindex(']') + 1]):
            kept.setdefault(b['region'], []).append(b)
    jobs = [(i, r) for i, r in enumerate(regions) if r in live and (not only or r['id'] in only)]
    with Pool() as pool:   # regions build in parallel, one per core
        built = dict(pool.map(build_region, jobs))
    boards = [b for r in live for b in built.get(r['id'], kept.get(r['id'], []))]
    out.write_text('// Generated by tools/gen.py. Do not edit by hand.\nconst BOARDS = [\n'
                   + ',\n'.join(json.dumps(b, ensure_ascii=False, separators=(',', ':')) for b in boards) + '\n];\n')
