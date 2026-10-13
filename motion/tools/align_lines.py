# Associe chaque ligne du script à un groupe de morceaux de voix consécutifs (programmation dynamique,
# durée attendue ∝ nombre de lettres, les longues pauses séparent plutôt deux lignes).
# usage : align_lines.py script.txt segs.json out.json
import json, sys
lines = [l.strip() for l in open(sys.argv[1]) if l.strip()]; S = json.load(open(sys.argv[2]))
L, N = len(lines), len(S)
chars = [len(l) for l in lines]; rate = sum(b - a for a, b in S) / sum(chars)
INF = 1e18; best = [[INF] * (N + 1) for _ in range(L + 1)]; prev = [[0] * (N + 1) for _ in range(L + 1)]
best[0][0] = 0
for i in range(1, L + 1):
    exp = chars[i - 1] * rate
    for j in range(1, N + 1):
        for k in range(max(0, j - 6), j):   # ligne i = morceaux k..j-1
            if best[i - 1][k] >= INF: continue
            dur = S[j - 1][1] - S[k][0]
            gaps = sum(max(0, S[t + 1][0] - S[t][1] - 0.35) for t in range(k, j - 1))
            c = best[i - 1][k] + ((dur - exp) / (0.6 + 0.25 * exp)) ** 2 + 3 * gaps
            if c < best[i][j]: best[i][j], prev[i][j] = c, k
out = []; j = N
for i in range(L, 0, -1):
    k = prev[i][j]; out.append({'line': i - 1, 'text': lines[i - 1], 'segs': list(range(k, j)), 't': [S[k][0], S[j - 1][1]]}); j = k
out.reverse(); json.dump(out, open(sys.argv[3], 'w'), indent=1, ensure_ascii=False)
for o in out: print(o['line'], o['segs'], o['t'], round(o['t'][1] - o['t'][0], 2), round(chars[o['line']] * rate, 2), o['text'][:60])
