import glob, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')

tex_files = glob.glob('report-latex/contents/sections/SEC*.tex') + ['report-latex/main.tex']
patterns = ['resizebox', 'adjustbox', 'sloppy', 'tiny', 'scalebox']

results = {p: [] for p in patterns}

for tf in sorted(tex_files):
    if os.path.exists(tf):
        with open(tf, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line_no, line in enumerate(lines, 1):
                for pat in patterns:
                    if re.search(rf'\\?{pat}\b', line):
                        results[pat].append((tf, line_no, line.strip()))

print('=== SCAN RESULTS FOR LATEX KEYWORDS ===')
for pat in patterns:
    matches = results[pat]
    print(f'Keyword: "{pat}" -> {len(matches)} occurrences')
    for tf, lno, ltext in matches:
        print(f'  [{tf}:{lno}] {ltext[:100]}')
