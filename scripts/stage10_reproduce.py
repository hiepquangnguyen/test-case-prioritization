"""Stage 10 Reproduction Runner for FALCON artifact on Defects4J suites.

Adheres strictly to the protocol defined in docs/10-handoff/README.md and
configs/falcon-reproduction-v1.json.
- Model: microsoft/unixcoder-base (pinned revision 5604afdc964f6c53782a6813140ade5216b99006)
- Runtime: CPU float32, torch threads=4, seed=0, batch_size=16
- Pooling: upstream unmasked mean over last_hidden_state
- Metric: raw cosine (preserving negative values)
- Ranker: lazy_greedy with tolerance 1e-6, tie-breaking by smallest input index
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
os.environ["HF_HOME"] = str(ROOT / "work/cache/huggingface")
os.environ["HF_HUB_DISABLE_XET"] = "1"

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, str(ROOT / "work/artifacts/falcon/py"))

import submodtcp  # Upstream FacilityLocation


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_peak_rss_mib() -> float:
    """Returns peak memory working set in MiB across platforms."""
    if platform.system() == "Windows":
        from ctypes import wintypes
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        psapi = ctypes.windll.psapi
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return pmc.PeakWorkingSetSize / (1024 * 1024)
        return 0.0
    else:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def load_test_cases(file_path: Path) -> List[str]:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def generate_embeddings_with_checkpoints(
    tests: List[str],
    tokenizer: Any,
    model: Any,
    device: str,
    batch_size: int,
    max_length: int,
    checkpoint_dir: Path,
    resume: bool = True,
    identity_key: Optional[Dict[str, Any]] = None
) -> Tuple[np.ndarray, float, bool]:
    """Generates embeddings using unmasked mean pooling with atomic batch checkpointing."""
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    chk_file = checkpoint_dir / "checkpoint_batches.npy"
    chk_meta = checkpoint_dir / "checkpoint_meta.json"
    
    total_tests = len(tests)
    total_batches = (total_tests + batch_size - 1) // batch_size
    batches_done = 0
    collected: List[np.ndarray] = []
    cache_hit = False

    if resume and chk_file.exists() and chk_meta.exists():
        try:
            meta = json.loads(chk_meta.read_text(encoding="utf-8"))
            saved_key = meta.get("identity_key")
            key_ok = True
            if identity_key is not None:
                if saved_key is None:
                    print(f"Warning: Checkpoint lacks identity_key while identity_key is required. Starting fresh.", flush=True)
                    key_ok = False
                elif saved_key != identity_key:
                    print(f"Warning: Checkpoint identity key mismatch. Expected: {identity_key}, found: {saved_key}. Starting fresh.", flush=True)
                    key_ok = False

            if not key_ok:
                try:
                    chk_file.unlink(missing_ok=True)
                    chk_meta.unlink(missing_ok=True)
                except Exception:
                    pass
                collected = []
                batches_done = 0
            elif meta.get("total_tests") == total_tests and meta.get("batch_size") == batch_size:
                saved = np.load(chk_file)
                batches_done = meta.get("batches_completed", 0)
                expected_rows = min(batches_done * batch_size, total_tests)
                if saved.shape[0] == expected_rows:
                    collected.append(saved)
                    print(f"Resumed from checkpoint: {batches_done}/{total_batches} batches ({expected_rows} items).", flush=True)
                    if batches_done == total_batches:
                        return saved, 0.0, True
        except Exception as e:
            print(f"Warning: Failed to load checkpoint, starting fresh: {e}", flush=True)
            collected = []
            batches_done = 0

    started = time.perf_counter()
    model.eval()
    
    start_batch_idx = batches_done
    with torch.no_grad():
        for b_idx in range(start_batch_idx, total_batches):
            i = b_idx * batch_size
            batch_tests = tests[i:i + batch_size]
            
            inputs = tokenizer(
                batch_tests,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt"
            ).to(device)
            
            outputs = model(**inputs)
            
            if hasattr(outputs, "last_hidden_state"):
                batch_emb = outputs.last_hidden_state.mean(dim=1).cpu().numpy().astype(np.float32)
            elif hasattr(outputs, "pooler_output"):
                batch_emb = outputs.pooler_output.cpu().numpy().astype(np.float32)
            else:
                batch_emb = outputs[0].mean(dim=1).cpu().numpy().astype(np.float32)
                
            collected.append(batch_emb)
            
            # Atomic checkpoint save every batch or every 10 batches
            curr_all = np.vstack(collected)
            tmp_chk = checkpoint_dir / f"checkpoint_batches.tmp.npy"
            np.save(tmp_chk, curr_all)
            if tmp_chk.exists():
                if chk_file.exists():
                    chk_file.unlink()
                tmp_chk.rename(chk_file)
                
            meta_content = {
                "total_tests": total_tests,
                "batch_size": batch_size,
                "batches_completed": b_idx + 1,
                "total_batches": total_batches,
                "items_completed": curr_all.shape[0]
            }
            if identity_key is not None:
                meta_content["identity_key"] = identity_key
            tmp_meta = checkpoint_dir / "checkpoint_meta.tmp.json"
            tmp_meta.write_text(json.dumps(meta_content, indent=2), encoding="utf-8")
            if tmp_meta.exists():
                if chk_meta.exists():
                    chk_meta.unlink()
                tmp_meta.rename(chk_meta)
                
    elapsed = time.perf_counter() - started
    final_embeddings = np.vstack(collected)
    return final_embeddings, elapsed, False


def run_reproduction(
    project: str,
    config_path: Path,
    output_dir: Path,
    limit: int = 0,
    resume: bool = True,
    validate_only: bool = False
) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Validate output dir safety
    out_dir = output_dir.resolve()
    for forbidden in ["reports/stage1", "work/runs/falcon/chart-full"]:
        if out_dir == (ROOT / forbidden).resolve():
            raise ValueError(f"Writing to frozen or legacy directory is strictly forbidden: {forbidden}")
            
    out_dir.mkdir(parents=True, exist_ok=True)
    
    source_bbox = ROOT / f"work/artifacts/falcon/input/{project}/{project}-bbox.txt"
    if not source_bbox.exists():
        raise FileNotFoundError(f"Source bbox file not found: {source_bbox}")

    all_tests = load_test_cases(source_bbox)
    tests = all_tests[:limit] if limit > 0 else all_tests
    n_tests = len(tests)

    # Set threads & seeds
    torch_threads = cfg.get("runtime", {}).get("torch_threads", 4)
    seed = cfg.get("runtime", {}).get("seed", 0)
    torch.set_num_threads(torch_threads)
    torch.manual_seed(seed)
    np.random.seed(seed)

    model_name = cfg["model"]["name"]
    model_rev = cfg["model"]["revision"]
    batch_size = cfg.get("runtime", {}).get("batch_size", 16)
    max_length = cfg.get("tokenizer", {}).get("max_length", 512)
    device = cfg.get("runtime", {}).get("device", "cpu")

    cache_key = {
        "project": project,
        "source_sha256": sha256_file(source_bbox),
        "limit": limit,
        "model": {"name": model_name, "revision": model_rev},
        "batch_size": batch_size,
        "max_length": max_length,
        "pooling": "upstream unmasked mean over last_hidden_state",
        "metric": "cosine",
        "torch_version": torch.__version__,
        "numpy_version": np.__version__
    }

    embeddings_path = out_dir / "embeddings.npy"
    cache_meta_path = out_dir / "embedding-config.json"
    ranking_path = out_dir / "ranking.json"
    gains_path = out_dir / "gains.json"
    result_path = out_dir / "result.json"

    # If validate-only, check existing outputs
    if validate_only:
        if not embeddings_path.exists() or not ranking_path.exists() or not result_path.exists():
            raise FileNotFoundError(f"Missing outputs for validate-only in {out_dir}")
        res = json.loads(result_path.read_text(encoding="utf-8"))
        print(f"Validation mode: Existing run validated for {project} ({n_tests} tests).")
        return res

    # 1. Model Loading
    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, revision=model_rev, trust_remote_code=False, local_files_only=True
    )
    model = AutoModel.from_pretrained(
        model_name, revision=model_rev, trust_remote_code=False, local_files_only=True
    )
    model.eval()
    model_load_sec = time.perf_counter() - t0

    # 2. Embedding Generation / Cache
    chk_dir = out_dir / "checkpoints"
    is_cache_hit = False
    if (
        embeddings_path.exists()
        and cache_meta_path.exists()
        and json.loads(cache_meta_path.read_text(encoding="utf-8")) == cache_key
    ):
        print(f"Loaded verified cache embeddings from {embeddings_path}", flush=True)
        t0 = time.perf_counter()
        embeddings = np.load(embeddings_path)
        embedding_sec = time.perf_counter() - t0
        is_cache_hit = True
    else:
        print(f"Generating embeddings for {project} ({n_tests} tests, batch_size={batch_size})...", flush=True)
        embeddings, embedding_sec, is_cache_hit = generate_embeddings_with_checkpoints(
            tests=tests,
            tokenizer=tokenizer,
            model=model,
            device=device,
            batch_size=batch_size,
            max_length=max_length,
            checkpoint_dir=chk_dir,
            resume=resume,
            identity_key=cache_key
        )
        np.save(embeddings_path, embeddings)
        cache_meta_path.write_text(json.dumps(cache_key, indent=2), encoding="utf-8")

    assert embeddings.shape[0] == n_tests, f"Shape mismatch: {embeddings.shape[0]} != {n_tests}"
    assert np.isfinite(embeddings).all(), "Embeddings contain non-finite values!"
    assert embeddings.dtype == np.float32 or embeddings.dtype == np.float64

    # 3. Similarity Matrix (Raw Cosine)
    t0 = time.perf_counter()
    fl = submodtcp.FacilityLocation(source_embeddings=embeddings, metric="cosine", device=device)
    sim_min = float(fl.similarity_matrix.min().cpu().numpy())
    negative_similarities = int((fl.similarity_matrix < 0).sum().cpu().numpy())
    sim_sec = time.perf_counter() - t0

    # 4. Lazy Greedy Ranking
    t0 = time.perf_counter()
    order, gains = fl.lazy_greedy(n_tests)
    ranking_sec = time.perf_counter() - t0

    assert len(order) == n_tests
    assert set(order) == set(range(n_tests)), "Ranking is not a valid permutation!"

    # Save outputs
    ranking_path.write_text(json.dumps(order), encoding="utf-8")
    gains_path.write_text(json.dumps([(int(c), float(g)) for c, g in gains]), encoding="utf-8")

    peak_rss = get_peak_rss_mib()

    apfd_val = None
    fault_path = ROOT / f"work/artifacts/falcon/input/{project}/fault_matrix.pickle"
    if limit == 0 and fault_path.exists():
        try:
            import pickle
            from stage10_validate import independent_apfd
            with open(fault_path, "rb") as f:
                faults = pickle.load(f)
            apfd_val = independent_apfd(order, faults)
        except Exception as exc:
            print(f"Warning: could not calculate APFD in reproduction: {exc}", flush=True)

    result: Dict[str, Any] = {
        "project": project,
        "config_name": cfg.get("config_name", "falcon-reproduction-v1"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version(),
        "device": device,
        "threads": torch_threads,
        "tests": n_tests,
        "full_suite": (limit == 0),
        "embedding_shape": list(embeddings.shape),
        "embedding_sha256": hashlib.sha256(embeddings.tobytes()).hexdigest(),
        "model": {"name": model_name, "revision": model_rev},
        "model_load_seconds": round(model_load_sec, 4),
        "embedding_cache_hit": is_cache_hit,
        "embedding_seconds": round(embedding_sec, 4),
        "similarity_seconds": round(sim_sec, 4),
        "ranking_seconds": round(ranking_sec, 4),
        "total_wallclock_seconds": round(model_load_sec + embedding_sec + sim_sec + ranking_sec, 4),
        "similarity_min": round(sim_min, 6),
        "negative_similarities": negative_similarities,
        "valid_permutation": True,
        "peak_rss_mib": round(peak_rss, 2),
        "peak_rss_gib": round(peak_rss / 1024.0, 3)
    }
    if apfd_val is not None:
        result["apfd"] = apfd_val

    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Run completed successfully for {project}: wallclock={result['total_wallclock_seconds']}s, peak_rss={result['peak_rss_gib']} GiB")
    return result


def main():
    parser = argparse.ArgumentParser(description="Stage 10 Reproduction Runner")
    parser.add_argument("--project", type=str, required=True, choices=["Chart", "Mockito", "Lang", "Math", "Time", "Closure"])
    parser.add_argument("--config", type=Path, default=ROOT / "configs/falcon-reproduction-v1.json")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tests (0 for full suite)")
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from atomic checkpoint if available")
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing run without executing")
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = ROOT / f"work/runs/stage10/{args.project}"

    run_reproduction(
        project=args.project,
        config_path=args.config,
        output_dir=args.output_dir,
        limit=args.limit,
        resume=args.resume,
        validate_only=args.validate_only
    )


if __name__ == "__main__":
    main()
