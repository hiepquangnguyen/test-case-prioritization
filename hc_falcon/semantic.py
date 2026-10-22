"""Pinned offline encoder and content-addressed vector cache."""
import hashlib
import json
from pathlib import Path
import numpy as np
from .preprocess import VERSION, preprocess


def digest(content):
    return hashlib.sha256(content).hexdigest()


def masked_mean(hidden, attention):
    mask = attention.to(hidden.dtype).unsqueeze(-1)
    return (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)


def kernel(vectors, valid):
    vectors = np.asarray(vectors, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    if vectors.ndim != 2 or valid.shape != (len(vectors),) or not np.isfinite(vectors).all():
        raise ValueError('Invalid vectors or mask')
    norms = np.linalg.norm(vectors, axis=1)
    valid = valid & (norms > 0)
    unit = np.zeros_like(vectors)
    unit[valid] = vectors[valid] / norms[valid, None]
    result = np.clip(unit @ unit.T, 0, 1).astype(np.float32)
    result[~valid, :] = 0
    result[:, ~valid] = 0
    result[np.diag_indices(len(vectors))] = valid.astype(np.float32)
    return result


def cached_kernel(cache_dir, test_ids, vectors, valid, config):
    vectors = np.asarray(vectors, dtype=np.float32)
    identity = dict(test_ids=list(test_ids), valid=list(map(bool, valid)), config=config,
                    vector_sha256=[digest(v.tobytes()) for v in vectors], version='clipped_cosine_v1')
    if len(test_ids) != len(vectors) or len(set(test_ids)) != len(test_ids):
        raise ValueError('Invalid kernel cache inventory')
    key = digest(json.dumps(identity, sort_keys=True).encode())
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (key + '.npz')
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            result = saved['kernel']
            expected = str(saved['sha256'])
        if result.shape != (len(test_ids), len(test_ids)) or not np.isfinite(result).all() or digest(result.tobytes()) != expected:
            raise ValueError('Corrupt kernel cache')
        return result, key, True
    result = kernel(vectors, valid)
    np.savez(path, kernel=result, sha256=digest(result.tobytes()))
    return result, key, False


class Encoder:
    def __init__(self, cache_dir, model_cache, config):
        import torch
        import transformers
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.config = dict(config)
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        kwargs = dict(revision=config['revision'], cache_dir=str(model_cache),
                      local_files_only=True, trust_remote_code=False)
        self.tokenizer = AutoTokenizer.from_pretrained(config['encoder'], **kwargs)
        self.model = AutoModel.from_pretrained(config['encoder'], **kwargs).float().cpu().eval()
        self.identity = dict(config=config, preprocessing=VERSION, torch=torch.__version__,
                             transformers=transformers.__version__, numpy=np.__version__,
                             device='cpu', dtype='float32',
                             tokenizer_sha256=digest(self.tokenizer.backend_tokenizer.to_str().encode()),
                             model_config_sha256=digest(self.model.config.to_json_string().encode()))

    def encode(self, content):
        key = digest(json.dumps(dict(source_sha256=digest(content), **self.identity),
                                sort_keys=True).encode())
        path = self.cache / (key + '.npz')
        if path.exists():
            with np.load(path, allow_pickle=False) as saved:
                vector = saved['vector']
                metadata = json.loads(str(saved['metadata']))
            if vector.dtype != np.float32 or not np.isfinite(vector).all() or digest(vector.tobytes()) != metadata['vector_sha256']:
                raise ValueError('Corrupt vector cache')
            return vector, dict(metadata, cache_hit=True)
        metadata = dict(cache_key=key, source_sha256=digest(content), cache_hit=False,
                        token_count=0, chunks=0, truncation_fraction=0.0)
        vector = np.zeros(self.model.config.hidden_size, dtype=np.float32)
        try:
            source = preprocess(content)
        except (UnicodeError, ValueError) as exc:
            source = ''
            metadata['unavailable_reason'] = str(exc)
        backend = self.tokenizer.backend_tokenizer
        backend.no_truncation()
        backend.no_padding()
        encoding = backend.encode(source, add_special_tokens=False) if source.strip() else None
        tokens = encoding.ids if encoding is not None else []
        payload = self.config['max_length'] - self.tokenizer.num_special_tokens_to_add(pair=False)
        if payload <= 0 or self.config['max_chunks'] <= 0:
            raise ValueError('Invalid chunk configuration')
        chunks = [tokens[i:i + payload] for i in range(0, min(len(tokens), payload * self.config['max_chunks']), payload)]
        metadata.update(token_count=len(tokens), chunks=len(chunks),
                        truncation_fraction=max(0, len(tokens) - sum(map(len, chunks))) / max(1, len(tokens)))
        if chunks:
            encoding.truncate(payload, stride=0, direction='right')
            pieces = [encoding, *encoding.overflowing][:self.config['max_chunks']]
            rows = [backend.post_process(piece, add_special_tokens=True) for piece in pieces]
            width = max(len(row.ids) for row in rows)
            for row in rows:
                row.pad(width, pad_id=self.tokenizer.pad_token_id, pad_token=self.tokenizer.pad_token)
            batch = dict(input_ids=self.torch.tensor([row.ids for row in rows]),
                         attention_mask=self.torch.tensor([row.attention_mask for row in rows]))
            with self.torch.inference_mode():
                hidden = self.model(**batch).last_hidden_state
                pooled = masked_mean(hidden, batch['attention_mask']).cpu().numpy().astype(np.float32)
            vector = np.average(pooled, axis=0, weights=np.asarray(list(map(len, chunks)), dtype=np.float32)).astype(np.float32)
            if not np.isfinite(vector).all():
                raise ValueError('Nonfinite encoder output')
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector /= norm
        metadata.update(valid=bool(np.linalg.norm(vector) > 0), vector_sha256=digest(vector.tobytes()))
        np.savez(path, vector=vector, metadata=json.dumps(metadata, sort_keys=True))
        return vector, metadata
