"""Script to check verbatim overlap of consecutive 8-word sequences between LaTeX source files and reference PDFs (FALCON & DANTE)."""

import os
import re
import sys
import fitz


def extract_pdf_words(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ''
    for page in doc:
        full_text += page.get_text() + ' '
    # Normalize: lowercase, keep words, remove pure math punctuation
    words = re.findall(r'[a-zA-Z0-9_\-\./]+', full_text.lower())
    return words


def extract_tex_words(tex_path, filter_math=True):
    with open(tex_path, 'r', encoding='utf-8') as f:
        text = f.read()
    # Strip LaTeX comments
    lines = [l.split('%')[0] for l in text.splitlines()]
    text_clean = ' '.join(lines)
    if filter_math:
        # Strip display math $$...$$ and \[...\] and inline math $...$
        text_clean = re.sub(r'\$\$.*?\$\$', ' ', text_clean, flags=re.DOTALL)
        text_clean = re.sub(r'\\\[.*?\\\]', ' ', text_clean, flags=re.DOTALL)
        text_clean = re.sub(r'\$.*?\$', ' ', text_clean, flags=re.DOTALL)
        text_clean = re.sub(r'\\begin\{equation\}.*?\\end\{equation\}', ' ', text_clean, flags=re.DOTALL)
    # Strip LaTeX commands \command{...}
    text_clean = re.sub(r'\\[a-zA-Z]+', ' ', text_clean)
    words = re.findall(r'[a-zA-Z0-9_\-\./\w]+', text_clean.lower())
    return words


def find_ngrams(words, n=8):
    ngrams = {}
    for i in range(len(words) - n + 1):
        gram = tuple(words[i:i+n])
        if gram not in ngrams:
            ngrams[gram] = []
        ngrams[gram].append(i)
    return ngrams


def check_overlap(tex_path, falcon_pdf, dante_pdf, n=8):
    print(f'Checking overlap for {tex_path} against {falcon_pdf} and {dante_pdf} (N={n})...')
    f_words = extract_pdf_words(falcon_pdf)
    d_words = extract_pdf_words(dante_pdf)
    tex_words = extract_tex_words(tex_path)

    f_ngrams = find_ngrams(f_words, n)
    d_ngrams = find_ngrams(d_words, n)

    matches = []
    for i in range(len(tex_words) - n + 1):
        gram = tuple(tex_words[i:i+n])
        source = []
        if gram in f_ngrams:
            source.append(f'FALCON (pos {f_ngrams[gram]})')
        if gram in d_ngrams:
            source.append(f'DANTE (pos {d_ngrams[gram]})')
        if source:
            phrase = ' '.join(gram)
            matches.append((i, phrase, ', '.join(source)))

    print(f'Total words in TeX: {len(tex_words)}')
    print(f'Total matches found: {len(matches)}')
    for idx, phrase, src in matches:
        print(f'  [Match at word {idx}] Source: {src}')
        print(f'    Sequence: \"{phrase}\"')
    return matches


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    falcon_pdf = os.path.join(base_dir, 'falcon-icst-2026.pdf')
    dante_pdf = os.path.join(base_dir, 'dante-icst-2026.pdf')
    sec2_tex = os.path.join(base_dir, 'report-latex', 'contents', 'sections', 'SEC2.tex')
    sec3_tex = os.path.join(base_dir, 'report-latex', 'contents', 'sections', 'SEC3.tex')

    print('=== CHECKING SEC2.tex ===')
    m2 = check_overlap(sec2_tex, falcon_pdf, dante_pdf, n=8)
    print('\n=== CHECKING SEC3.tex ===')
    m3 = check_overlap(sec3_tex, falcon_pdf, dante_pdf, n=8)
