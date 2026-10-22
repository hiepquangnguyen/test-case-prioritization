"""Local pinned-artifact fidelity audit; no reserved data or experiment tuning."""
import ast
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.stage6_pilot import write_json
from tcp.lrts import file_sha256
from hc_falcon.greedy import rank, normalize
from hc_falcon.semantic import masked_mean


def definition(path, name, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name == name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[name]


def main():
    torch.set_num_threads(1)
    freezes = ('reports/stage6/final-evidence-freeze.json','reports/stage7/evidence-freeze.json','reports/stage8/evidence-freeze.json')
    for name in freezes:
        for path, expected in json.loads((ROOT/name).read_text())['files_sha256'].items():
            assert file_sha256(ROOT/path) == expected, path
    archive = ROOT/'references/artifacts/falcon/falcon.zip'
    assert file_sha256(archive) == 'd60fa62edf1d1838185edf19e61146f5981895702f6a7afce0ab8c3f65ee36c8'
    code, datasets = {},[]
    with zipfile.ZipFile(archive) as z:
        for name in ('embedding_generator.py','submodtcp.py','metric.py','prioritize_method.py'):
            member = next(n for n in z.namelist() if n.endswith('/py/'+name))
            content = z.read(member)
            local = ROOT/'work/artifacts/falcon/py'/name
            assert local.read_bytes() == content
            code[name] = dict(member=member,sha256=hashlib.sha256(content).hexdigest())
        for member in sorted(n for n in z.namelist() if n.endswith('_fault_matrix.csv') and '/projects/' in n):
            rows = list(csv.reader(io.StringIO(z.read(member).decode('utf-8-sig'))))
            header, data = rows[0],rows[1:]
            assert all(len(row)==len(header) for row in data)
            assert len({row[0] for row in data}) == len(data)
            assert all(v in ('0','1') for row in data for v in row[1:])
            detected = [any(row[i]=='1' for row in data) for i in range(1,len(header))]
            datasets.append(dict(member=member,tests=len(data),faults=len(header)-1,
                all_faults_detectable=all(detected),sha256=hashlib.sha256(z.read(member)).hexdigest()))
    namespace = dict(torch=torch,np=np,tqdm=lambda values,**kwargs:values)
    upstream = definition(ROOT/'work/artifacts/falcon/py/submodtcp.py','FacilityLocation',namespace)
    fixtures = {}
    for name,k in [('nonnegative',np.array([[1,.2,.1],[.2,1,.4],[.1,.4,1]],dtype=np.float32)),
                   ('negative_cosine',np.array([[1,-1,0],[-1,1,0],[0,0,1]],dtype=np.float32)),
                   ('tie_index_vs_fqn',np.ones((3,3),dtype=np.float32))]:
        ids = ('c','b','a') if name=='tie_index_vs_fqn' else ('a','b','c')
        original = upstream(similarity_matrix=k,device='cpu').lazy_greedy(3)[0]
        adapted = rank(ids,np.clip(k,0,1),np.zeros(3),alpha=1)[0]
        fixtures[name] = dict(upstream=[ids[i] for i in original],adapted=list(adapted))
    assert fixtures['nonnegative']['upstream'] == fixtures['nonnegative']['adapted']
    assert fixtures['negative_cosine']['upstream'] != fixtures['negative_cosine']['adapted']
    assert fixtures['tie_index_vs_fqn']['upstream'] != fixtures['tie_index_vs_fqn']['adapted']
    # Use the upstream function body with deterministic hidden states, no model download.
    from types import SimpleNamespace
    class Batch(dict):
        def to(self,device):
            return self
    class Model:
        def eval(self):
            return self
        def __call__(self,**kwargs):
            return SimpleNamespace(last_hidden_state=torch.tensor([[[1.],[5.]]]))
    generator = definition(ROOT/'work/artifacts/falcon/py/embedding_generator.py','generate_embeddings_transformer',namespace)
    original = generator(['test'],'fixture',lambda *a,**kw:Batch(attention_mask=torch.tensor([[1,0]])),Model(),'cpu')
    masked = masked_mean(torch.tensor([[[1.],[5.]]]),torch.tensor([[1,0]])).numpy()
    assert original.item() == 3 and masked.item() == 1
    k = np.diag([0.,1.]).astype(np.float32)
    raw = rank(('a','b'),k,[2.,1.],alpha=.5)[0]
    normalized = rank(('a','b'),k,normalize([2.,1.]),alpha=.5)[0]
    assert raw != normalized
    result = dict(prior_freezes_verified=list(freezes),reserved_opened=False,
        artifact_sha256=file_sha256(archive),upstream_code=code,datasets=datasets,
        total_faults=sum(d['faults'] for d in datasets),
        probes=dict(greedy=fixtures,pooling=dict(upstream_unmasked=float(original.item()),adapted_masked=float(masked.item())),
                    objective=dict(raw=list(raw),normalized=list(normalized))),
        interpretation='toy probes demonstrate non-equivalence, not causes or effect sizes of LRTS losses',
        chart_prior_run=json.loads((ROOT/'reports/stage1/falcon-chart-full-smoke.json').read_text()))
    write_json(ROOT/'reports/stage9/fidelity-audit.json',result)
    print(json.dumps(dict(datasets=datasets,probes=result['probes']),indent=2))


if __name__ == '__main__':
    main()
