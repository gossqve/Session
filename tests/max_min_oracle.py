"""Small independent rational Oracle: enumerate ordered-region vertices.

No progressive filling or production allocator calls. The max-min point lies
on a vertex of a region obtained by cutting capacity polytope with r_i=r_j.
Choose the feasible candidate with lexicographically greatest sorted rates.
Intentionally exponential; test-only, small finite systems.
"""
from fractions import Fraction
from itertools import combinations


def solve_equalities(rows, rhs):
    n = len(rows)
    matrix = [[Fraction(x) for x in row] + [Fraction(value)] for row, value in zip(rows, rhs)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if matrix[i][col]), None)
        if pivot is None:
            return None
        matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
        divisor = matrix[col][col]
        matrix[col] = [x / divisor for x in matrix[col]]
        for i in range(n):
            if i != col:
                multiplier = matrix[i][col]
                matrix[i] = [x - multiplier * y for x, y in zip(matrix[i], matrix[col])]
    return tuple(row[-1] for row in matrix)


def vertex_oracle(paths, capacities):
    names = sorted(paths)
    n = len(names)
    if not n:
        return {}
    constraints = [(tuple(int(link in paths[name]) for name in names), Fraction(str(cap)))
                   for link, cap in capacities.items()]
    planes = list(constraints)
    planes += [(tuple(int(i == j) for i in range(n)), Fraction(0)) for j in range(n)]
    planes += [(tuple(int(k == i) - int(k == j) for k in range(n)), Fraction(0))
               for i, j in combinations(range(n), 2)]
    best = None
    for selected in combinations(planes, n):
        point = solve_equalities([p[0] for p in selected], [p[1] for p in selected])
        if point is None or min(point) < 0:
            continue
        if any(sum(a * b for a, b in zip(row, point)) > cap for row, cap in constraints):
            continue
        if best is None or tuple(sorted(point)) > tuple(sorted(best)):
            best = point
    if best is None:
        raise AssertionError("No feasible Oracle candidate")
    return dict(zip(names, best))
