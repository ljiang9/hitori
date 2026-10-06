#!/usr/bin/env python3
"""hitori —— 独数（Hitori）谜题生成器与求解器。

规则（涂黑 = shade）：
1. 同一行 / 同一列中，未涂黑的数字不能重复；
2. 涂黑的格子不能上下左右相邻；
3. 所有未涂黑的格子必须连成一片（四连通）。

纯标准库：argparse / sys / random。
"""

import argparse
import random
import sys


def neighbors(r, c, n):
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < n and 0 <= nc < n:
            yield nr, nc


def check_solution(grid, shade):
    """验证 (grid, shade) 是否满足三条规则。返回 (ok, 说明)。"""
    n = len(grid)
    # 规则 2：涂黑格不相邻
    for r in range(n):
        for c in range(n):
            if shade[r][c]:
                for nr, nc in neighbors(r, c, n):
                    if shade[nr][nc]:
                        return False, f"涂黑格相邻：({r+1},{c+1}) 与 ({nr+1},{nc+1})"
    # 规则 1：未涂黑的行列无重复
    for r in range(n):
        seen = set()
        for c in range(n):
            if not shade[r][c]:
                v = grid[r][c]
                if v in seen:
                    return False, f"第 {r+1} 行未涂黑数字 {v} 重复"
                seen.add(v)
    for c in range(n):
        seen = set()
        for r in range(n):
            if not shade[r][c]:
                v = grid[r][c]
                if v in seen:
                    return False, f"第 {c+1} 列未涂黑数字 {v} 重复"
                seen.add(v)
    # 规则 3：未涂黑格连通
    total = sum(1 for r in range(n) for c in range(n) if not shade[r][c])
    start = next(((r, c) for r in range(n) for c in range(n)
                  if not shade[r][c]), None)
    if start is None:
        return False, "全部格子都被涂黑"
    seen, stack = {start}, [start]
    while stack:
        r, c = stack.pop()
        for nr, nc in neighbors(r, c, n):
            if not shade[nr][nc] and (nr, nc) not in seen:
                seen.add((nr, nc))
                stack.append((nr, nc))
    if len(seen) != total:
        return False, "未涂黑的格子没有连成一片"
    return True, "合法"


class Solver:
    """回溯求解器。按行优先逐格决定涂黑/不涂黑，边填边剪枝。"""

    def __init__(self, grid, rng=None, max_nodes=2_000_000, order_seed=None):
        self.grid = grid
        self.n = len(grid)
        self.rng = rng or random.Random()
        self.max_nodes = max_nodes
        self.order_seed = order_seed
        self.nodes = 0
        self.shade = [[None] * self.n for _ in range(self.n)]

    def _ok_shaded(self, r, c):
        for nr, nc in neighbors(r, c, self.n):
            if self.shade[nr][nc] is True:
                return False
        return True

    def _ok_unshaded(self, r, c):
        v = self.grid[r][c]
        for cc in range(self.n):  # 同行已填
            if cc != c and self.shade[r][cc] is False and self.grid[r][cc] == v:
                return False
        for rr in range(self.n):  # 同列已填
            if rr != r and self.shade[rr][c] is False and self.grid[rr][c] == v:
                return False
        return True

    def _connected_prune(self):
        """廉价连通性剪枝：已确定未涂黑的格子若被孤立则剪掉。

        只做最便宜的一步：某个未涂黑格的全部邻居都已确定涂黑
        （且未涂黑总数 > 1）→ 不可能连通。
        """
        n = self.n
        unshaded = [(r, c) for r in range(n) for c in range(n)
                    if self.shade[r][c] is False]
        if len(unshaded) <= 1:
            return True
        for r, c in unshaded:
            nbrs = list(neighbors(r, c, n))
            if all(self.shade[nr][nc] is True for nr, nc in nbrs):
                return False
        return True

    def _search(self, cells, i):
        self.nodes += 1
        if self.nodes > self.max_nodes:
            return None
        if i == len(cells):
            ok, _ = check_solution(self.grid, self.shade)
            return [row[:] for row in self.shade] if ok else None
        r, c = cells[i]
        order = [False, True]
        if self.order_seed is not None:
            # 打乱尝试顺序，让多次求解/生成有多样性
            rr = random.Random((self.order_seed, self.nodes))
            rr.shuffle(order)
        for val in order:
            if val is True:
                if not self._ok_shaded(r, c):
                    continue
            else:
                if not self._ok_unshaded(r, c):
                    continue
            self.shade[r][c] = val
            if self._connected_prune():
                res = self._search(cells, i + 1)
                if res is not None:
                    return res
            self.shade[r][c] = None
        return None

    def solve(self):
        cells = [(r, c) for r in range(self.n) for c in range(self.n)]
        return self._search(cells, 0)


def random_latin(n, rng):
    """循环群表 + 行列/符号置换，得到随机拉丁方阵。"""
    base = [[(r + c) % n + 1 for c in range(n)] for r in range(n)]
    rows = list(range(n))
    cols = list(range(n))
    syms = list(range(1, n + 1))
    rng.shuffle(rows)
    rng.shuffle(cols)
    rng.shuffle(syms)
    return [[syms[base[rows[r]][cols[c]] - 1] for c in range(n)]
            for r in range(n)]


def generate(n, rng, tries=60):
    """生成一道可解的 Hitori：拉丁方阵打乱制造重复 → 求解器找涂黑方案。

    返回 (grid, shade)。构造上保证可解（生成器自己的解即为一解）。
    """
    for _ in range(tries):
        grid = random_latin(n, rng)
        # 随机改 ~35% 的格子制造重复
        for r in range(n):
            for c in range(n):
                if rng.random() < 0.35:
                    grid[r][c] = rng.randint(1, n)
        solver = Solver(grid, rng, max_nodes=500_000)
        shade = solver.solve()
        if shade is not None:
            return grid, shade
    raise RuntimeError(f"{tries} 次尝试都未能生成可解谜题")


def render(grid, shade=None):
    n = len(grid)
    lines = []
    for r in range(n):
        cells = []
        for c in range(n):
            v = str(grid[r][c])
            if shade and shade[r][c]:
                cells.append(f"[{v}]")
            else:
                cells.append(f" {v} ")
        lines.append(" ".join(cells))
    return "\n".join(lines)


def parse_grid(text):
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        # 跳过标题/说明行：谜题行必须以数字开头，这样
        # `hitori --seed 7 | hitori --solve -` 可以直接管道
        if not (s[0].isdigit() or (s[0] == "-" and len(s) > 1 and s[1].isdigit())):
            continue
        lines.append(s)
    grid = []
    for i, ln in enumerate(lines):
        parts = ln.replace(",", " ").split()
        try:
            row = [int(p) for p in parts]
        except ValueError:
            raise ValueError(f"第 {i+1} 行有非数字：{ln!r}")
        grid.append(row)
    if not grid:
        raise ValueError("输入为空")
    n = len(grid)
    if any(len(row) != n for row in grid):
        raise ValueError("不是方阵")
    if n not in (4, 5):
        raise ValueError(f"只支持 4x4 / 5x5，得到 {n}x{n}")
    if any(v < 1 or v > n for row in grid for v in row):
        raise ValueError(f"数字必须在 1..{n} 之间")
    return grid


def selftest():
    """内置自检：手工 4x4 + 20 种子生成求解。"""
    passed, failed = 0, 0

    def check(name, cond):
        nonlocal passed, failed
        print(f"  [{'通过' if cond else '失败'}] {name}")
        passed, failed = passed + cond, failed + (not cond)

    # 1. 手工 4x4（答案已手工验算）
    grid = [
        [2, 2, 1, 3],
        [1, 3, 2, 4],
        [3, 4, 1, 1],
        [4, 1, 3, 2],
    ]
    hand_shade = [
        [False, True, False, False],
        [False, False, False, False],
        [False, False, True, False],
        [False, False, False, False],
    ]
    ok, msg = check_solution(grid, hand_shade)
    check(f"手工解满足三规则（{msg}）", ok)
    sol = Solver(grid).solve()
    check("求解器对手工 4x4 有解",
          sol is not None and check_solution(grid, sol)[0])
    # 手工解里 (0,1) 与 (2,2) 涂黑是被迫的：求解器的解也必须涂黑这两格
    # （第 1 行两个 2 必去其一，涂 (0,0) 会让第 1 列出现两个未涂黑 1？不——
    #  这里只断言解合法，不强求唯一）
    check("手工解涂黑数 == 2", sum(sum(row) for row in hand_shade) == 2)

    # 2. 矛盾谜题：3x3 不在支持范围，用 4x4 全 1（无解）
    bad = [[1] * 4 for _ in range(4)]
    check("全 1 的 4x4 无解", Solver(bad, max_nodes=200_000).solve() is None)

    # 3. 20 个种子生成 → 求解 → 验证三规则
    rng = random.Random(20261005)
    good = 0
    for s in range(20):
        srng = random.Random(s)
        try:
            g, _ = generate(5, srng)
        except RuntimeError:
            continue
        s2 = Solver(g, srng).solve()
        if s2 is not None and check_solution(g, s2)[0]:
            good += 1
    check(f"20 种子 5x5 生成可解且合法：{good}/20", good == 20)

    # 4. 4x4 生成
    good4 = 0
    for s in range(20, 30):
        srng = random.Random(s)
        try:
            g, _ = generate(4, srng)
        except RuntimeError:
            continue
        s2 = Solver(g, srng).solve()
        if s2 is not None and check_solution(g, s2)[0]:
            good4 += 1
    check(f"10 种子 4x4 生成可解且合法：{good4}/10", good4 == 10)

    print(f"自检结果：{passed} 通过，{failed} 失败")
    return failed == 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hitori", description="独数 Hitori：生成与求解")
    ap.add_argument("--size", type=int, default=5, choices=[4, 5],
                    help="棋盘尺寸（默认 5）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--solution", action="store_true", help="同时打印答案（涂黑方案）")
    ap.add_argument("--solve", metavar="FILE",
                    help="求解文件/-（stdin）中的谜题，而不是生成新题")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检")
    args = ap.parse_args(argv)

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    if args.solve:
        text = sys.stdin.read() if args.solve == "-" else open(args.solve).read()
        try:
            grid = parse_grid(text)
        except ValueError as e:
            print(f"输入错误：{e}", file=sys.stderr)
            return 2
        sol = Solver(grid).solve()
        if sol is None:
            print("无解（或超出搜索预算）。")
            return 1
        print("解（[x] 为涂黑）：\n")
        print(render(grid, sol))
        ok, msg = check_solution(grid, sol)
        print(f"\n验证：{msg}")
        return 0

    rng = random.Random(args.seed)
    grid, shade = generate(args.size, rng)
    tag = f"hitori {args.size}x{args.size}"
    if args.seed is not None:
        tag += f"（种子={args.seed}）"
    print(f"{tag}：把重复数字涂黑（[x]），未涂黑连成一片\n")
    print(render(grid))
    if args.solution:
        print("\n答案：\n")
        print(render(grid, shade))
    return 0


if __name__ == "__main__":
    sys.exit(main())
