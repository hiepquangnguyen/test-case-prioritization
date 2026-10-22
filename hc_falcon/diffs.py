"""Local-only, explicit per-Java-file patch documents; never execute repository code."""
import hashlib
import json
from pathlib import Path
import subprocess
import os

FORMAT = 'git_patch_per_java_file_unified3_no_renames_no_ext_diff_no_textconv_v1'


def declared_diff(repo, trunk, head, cache_dir):
    if not trunk or not head:
        return None, 'Missing declared trunk/head SHA'
    if any(len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha) for sha in (trunk, head)):
        return None, 'Invalid declared SHA'
    identity = dict(trunk=trunk, head=head, format=FORMAT)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    path = Path(cache_dir) / (key + '.json')
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved['identity'] != identity:
            raise ValueError('Diff cache identity mismatch')
        return saved['documents'], None
    command = ['git', '--git-dir', str(repo), '-c', 'remote.origin.promisor=false',
               'diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--no-color',
               '--unified=3', trunk, head, '--', '*.java']
    result = subprocess.run(command, capture_output=True, timeout=180,
                            env=dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0'))
    if result.returncode:
        return None, result.stderr.decode(errors='replace').strip()
    try:
        patch = result.stdout.decode('utf-8')
    except UnicodeError:
        return None, 'Diff is not strict UTF-8'
    documents = ['diff --git ' + part for part in patch.split('diff --git ')[1:]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(identity=identity, documents=documents), sort_keys=True), encoding='utf-8')
    return documents, None
