"""
knights_tour.py — All Knight's Tour solvers in one module.

Algorithms:
  - solve_plain(start)      : Plain backtracking (slow, exponential)
  - solve_heuristic(start)  : Backtracking + MRV/LCV (Warnsdorff)
  - solve_genetic(...)      : Genetic Algorithm with repair decoding
"""

import random
import sys

BOARD_SIZE = 8
MAX_GENERATIONS = 3000
POPULATION_SIZE = 50
MUTATION_RATE = 0.02
TOURNAMENT_SIZE = 3

# All 8 knight move offsets, indexed 1–8 for the GA chromosome
KNIGHT_OFFSETS = [
    (1, 2), (2, 1), (2, -1), (1, -2),
    (-1, -2), (-2, -1), (-2, 1), (-1, 2),
]
DIRECTION_MAP = {i + 1: KNIGHT_OFFSETS[i] for i in range(8)}


# ═══════════════════════════════════════════════════════════
# SHARED UTILITY
# ═══════════════════════════════════════════════════════════

def in_board(x: int, y: int) -> bool:
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE


def legal_moves(pos: tuple, visited: set) -> list:
    """Return all valid, unvisited knight moves from pos."""
    x, y = pos
    return [
        (x + dx, y + dy)
        for dx, dy in KNIGHT_OFFSETS
        if in_board(x + dx, y + dy) and (x + dx, y + dy) not in visited
    ]


# ═══════════════════════════════════════════════════════════
# GENETIC ALGORITHM
# ═══════════════════════════════════════════════════════════

class Chromosome:
    """
    63 genes, each an integer 1–8 encoding one of the 8 knight directions.
    Crossover and mutation operate on the raw gene list; no silent repair here.
    """

    def __init__(self, genes=None):
        n = BOARD_SIZE ** 2 - 1          # 63 moves for an 8×8 board
        self.genes = list(genes) if genes is not None \
            else [random.randint(1, 8) for _ in range(n)]

    def crossover(self, other: "Chromosome"):
        """Single-point crossover. Returns two new Chromosome objects."""
        cut = random.randint(1, len(self.genes) - 1)
        return (
            Chromosome(self.genes[:cut] + other.genes[cut:]),
            Chromosome(other.genes[:cut] + self.genes[cut:]),
        )

    def mutate(self, rate: float = MUTATION_RATE):
        """Point mutation: each gene independently replaced with probability rate."""
        for i in range(len(self.genes)):
            if random.random() < rate:
                self.genes[i] = random.randint(1, 8)


class GAKnight:
    """
    One individual in the GA population.

    Decoding (evaluate) uses a repair strategy: when the gene's preferred
    direction is blocked, it tries adjacent directions in order.
    The chromosome itself is NEVER modified during evaluation — the repair
    is local to each call.  This keeps crossover/selection meaningful.
    """

    def __init__(self, chromosome: Chromosome = None):
        self.chromosome = chromosome or Chromosome()
        self.path: list = []
        self.fitness: int = 0

    def evaluate(self, start: tuple = (0, 0)) -> int:
        pos = start
        visited = {pos}
        path = [pos]

        for gene in self.chromosome.genes:
            moved = False
            for offset in range(8):
                direction = ((gene - 1 + offset) % 8) + 1
                dx, dy = DIRECTION_MAP[direction]
                nx, ny = pos[0] + dx, pos[1] + dy
                if in_board(nx, ny) and (nx, ny) not in visited:
                    pos = (nx, ny)
                    visited.add(pos)
                    path.append(pos)
                    moved = True
                    break
            if not moved:
                break       # knight is stuck; no benefit appending duplicates

        self.path = path
        self.fitness = len(path)
        return self.fitness


class Population:
    def __init__(self, size: int = POPULATION_SIZE):
        self.size = size
        self.generation = 1
        self.knights = [GAKnight() for _ in range(size)]

    def evaluate_all(self, start: tuple = (0, 0)):
        best = None
        best_fitness = 0
        for k in self.knights:
            f = k.evaluate(start)
            if f > best_fitness:
                best_fitness, best = f, k
        return best_fitness, best

    def tournament_selection(self) -> tuple:
        """Pick TOURNAMENT_SIZE random individuals; return the top two."""
        pool = random.sample(self.knights, TOURNAMENT_SIZE)
        pool.sort(key=lambda k: k.fitness, reverse=True)
        return pool[0], pool[1]

    def next_generation(self):
        new_knights = []
        while len(new_knights) < self.size:
            p1, p2 = self.tournament_selection()
            c1, c2 = p1.chromosome.crossover(p2.chromosome)
            c1.mutate()
            c2.mutate()
            new_knights.extend([GAKnight(c1), GAKnight(c2)])
        self.knights = new_knights[:self.size]
        self.generation += 1


def solve_genetic(
    start: tuple = (0, 0),
    max_gen: int = MAX_GENERATIONS,
    callback=None,          # callable(gen, fitness, path) — called every generation
) -> tuple:
    """
    Run the Genetic Algorithm.

    Returns (path, generation_count, solved_flag).
    'solved_flag' is True only when all 64 squares are visited.
    If the GA times out, the best partial path found is returned.
    """
    pop = Population()
    best_path = [start]
    best_fitness = 0

    for gen in range(1, max_gen + 1):
        fitness, best = pop.evaluate_all(start)

        if fitness > best_fitness:
            best_fitness = fitness
            best_path = best.path[:]        # snapshot; not a live reference

        if callback:
            callback(gen, fitness, best_path[:])

        if fitness == BOARD_SIZE ** 2:
            return best_path, gen, True     # full tour found

        pop.next_generation()

    return best_path, max_gen, False        # timed out


# ═══════════════════════════════════════════════════════════
# PLAIN BACKTRACKING
# ═══════════════════════════════════════════════════════════

def _bt_plain(path: list, visited: set) -> bool:
    if len(path) == BOARD_SIZE ** 2:
        return True
    for move in legal_moves(path[-1], visited):
        path.append(move)
        visited.add(move)
        if _bt_plain(path, visited):
            return True
        path.pop()
        visited.discard(move)
    return False


def solve_plain(start: tuple = (0, 0)):
    """
    Plain backtracking — no heuristics.
    WARNING: can be extremely slow from many starting positions.
    Returns the completed path or None if unsolvable from this start.
    """
    sys.setrecursionlimit(100_000)
    path, visited = [start], {start}
    return path if _bt_plain(path, visited) else None


# ═══════════════════════════════════════════════════════════
# HEURISTIC BACKTRACKING  (MRV + LCV / Warnsdorff's rule)
# ═══════════════════════════════════════════════════════════

def _order_mrv_lcv(moves: list, visited: set) -> list:
    """
    Sort candidate moves by:
      Primary   MRV  — fewest onward moves from that square (ascending).
      Tiebreak  LCV  — highest sum of options from those onward squares
                       (descending), i.e. least constraining.
    Together this is Warnsdorff's rule extended with a LCV tiebreaker.
    """
    def score(m):
        v_after = visited | {m}
        onward = legal_moves(m, v_after)
        mrv = len(onward)
        lcv = sum(len(legal_moves(o, v_after | {o})) for o in onward)
        return (mrv, -lcv)

    return sorted(moves, key=score)


def _bt_heuristic(path: list, visited: set) -> bool:
    if len(path) == BOARD_SIZE ** 2:
        return True
    ordered = _order_mrv_lcv(legal_moves(path[-1], visited), visited)
    for move in ordered:
        path.append(move)
        visited.add(move)
        if _bt_heuristic(path, visited):
            return True
        path.pop()
        visited.discard(move)
    return False


def solve_heuristic(start: tuple = (0, 0)):
    """
    Heuristic backtracking (MRV + LCV).
    Solves the Knight's Tour near-instantly for any starting square.
    Returns the completed path or None.
    """
    sys.setrecursionlimit(100_000)
    path, visited = [start], {start}
    return path if _bt_heuristic(path, visited) else None


# ═══════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════

def _print_board(path):
    board = [["  ."] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    for i, (col, row) in enumerate(path):
        board[row][col] = f"{i + 1:3d}"
    for row in board:
        print("".join(row))


if __name__ == "__main__":
    print("─── Heuristic Backtracking (MRV + LCV) ───")
    p = solve_heuristic(start=(0, 0))
    if p:
        _print_board(p)
        print(f"  {len(p)}/64 squares visited\n")
    else:
        print("  No solution found.\n")

    print("─── Genetic Algorithm (500 generations) ───")
    path, gen, solved = solve_genetic(max_gen=500)
    label = "Solved" if solved else "Best partial tour"
    print(f"  {label} after {gen} generations — {len(path)}/64 squares\n")

    # Plain backtracking is omitted here due to potential long runtime.
    # Call solve_plain() directly if you want to test it.
