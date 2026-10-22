"""Run the pinned FALCON embedding and FL functions, with separate local outputs.

Use the falcon venv. --download resolves and records the encoder commit once.
Default reruns use only local model files. Upstream artifact files stay unchanged.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from stage1_audit import ROOT, OUT, data_pickle, independent_apfd, write_json

os.environ['HF_HOME'] = str(ROOT/'work/cache/huggingface')
os.environ['HF_HUB_DISABLE_XET'] = '1'
sys.path.insert(0,str(ROOT/'work/artifacts/falcon/py'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--limit',type=int,default=0,help='0 means full Chart suite')
    args=parser.parse_args()
    import numpy as np
    import torch
    from huggingface_hub import HfApi
    from transformers import AutoModel, AutoTokenizer
    import embedding_generator as upstream_embedding
    import submodtcp
    torch.set_num_threads(4)
    torch.manual_seed(0)
    np.random.seed(0)
    model_name='microsoft/unixcoder-base'
    pin_path=OUT/'unixcoder-pin.json'
    if pin_path.exists():
        pin=json.loads(pin_path.read_text())
    elif args.download:
        info=HfApi().model_info(model_name)
        pin=dict(model=model_name,revision=info.sha)
        write_json('unixcoder-pin.json',pin)
    else:
        raise RuntimeError('Run once with --download to pin and fetch the encoder')
    print('Encoder',pin,flush=True)
    started=time.perf_counter()
    tokenizer=AutoTokenizer.from_pretrained(model_name,revision=pin['revision'],trust_remote_code=False,local_files_only=not args.download)
    model=AutoModel.from_pretrained(model_name,revision=pin['revision'],trust_remote_code=False,local_files_only=not args.download)
    model.eval()
    load_seconds=time.perf_counter()-started
    source=ROOT/'work/artifacts/falcon/input/Chart/Chart-bbox.txt'
    tests=upstream_embedding.load_test_cases(str(source))
    if args.limit:
        tests=tests[:args.limit]
    name='chart-full' if not args.limit else f'chart-first-{args.limit}'
    run=ROOT/'work/runs/falcon'/name
    run.mkdir(parents=True,exist_ok=True)
    cache_key=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),limit=args.limit,encoder=pin,batch_size=16,max_length=512,pooling='upstream unmasked mean over last_hidden_state',torch=torch.__version__)
    embeddings_path=run/'embeddings.npy'
    cache_path=run/'embedding-config.json'
    embedding_started=time.perf_counter()
    cache_hit=embeddings_path.exists() and cache_path.exists() and json.loads(cache_path.read_text())==cache_key
    if cache_hit:
        embeddings=np.load(embeddings_path)
    else:
        embeddings=upstream_embedding.generate_embeddings_transformer(tests,model_name,tokenizer,model,'cpu',batch_size=16,max_length=512)
        np.save(embeddings_path,embeddings)
        cache_path.write_text(json.dumps(cache_key,indent=2),encoding='utf-8')
    embedding_seconds=time.perf_counter()-embedding_started
    assert embeddings.shape[0]==len(tests) and np.isfinite(embeddings).all()
    print('Embedding ready',embeddings.shape,flush=True)
    started=time.perf_counter()
    fl=submodtcp.FacilityLocation(source_embeddings=embeddings,metric='cosine',device='cpu')
    minimum=float(fl.similarity_matrix.min())
    negative_count=int((fl.similarity_matrix<0).sum())
    similarity_seconds=time.perf_counter()-started
    started=time.perf_counter()
    order,gains=fl.lazy_greedy(len(tests))
    ranking_seconds=time.perf_counter()-started
    assert len(order)==len(tests) and set(order)==set(range(len(tests)))
    reference_order=None
    if args.limit and args.limit<=32:
        reference_order,_=fl.greedy(len(tests))
        assert order==reference_order
    all_faults=data_pickle((ROOT/'work/artifacts/falcon/input/Chart/fault_matrix.pickle').read_bytes())
    score=independent_apfd(order,all_faults) if not args.limit else None
    # Subsets deliberately receive no full-suite APFD.
    result=dict(run=name,python=platform.python_version(),device='cpu',threads=4,tests=len(tests),embedding_shape=list(embeddings.shape),model=pin,model_load_seconds=load_seconds,embedding_cache_hit=cache_hit,embedding_seconds=embedding_seconds,similarity_seconds=similarity_seconds,ranking_seconds=ranking_seconds,similarity_min=minimum,negative_similarities=negative_count,valid_permutation=True,standard_greedy_equal=order==reference_order if reference_order is not None else None,apfd=score,upstream_entry='embedding_generator.generate_embeddings_transformer + submodtcp.FacilityLocation.lazy_greedy',note='Original functions; explicit CPU adapter bypasses runner python3/CUDA and existing-output skip. Not a claim of paper reproduction.')
    write_json('falcon-'+name+'-smoke.json',result)
    (run/'ranking.json').write_text(json.dumps(order),encoding='utf-8')
    (run/'gains.json').write_text(json.dumps(gains),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
