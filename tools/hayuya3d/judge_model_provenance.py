#!/usr/bin/env python3
from __future__ import annotations

def model_provenance(model_id:str, model)->dict:
    """Return runtime evidence for the actual loaded checkpoint, not just a label."""
    revision=None
    config=getattr(model,"config",None)
    revision=getattr(config,"_commit_hash",None) if config is not None else None
    if not revision:
        try:
            from huggingface_hub import model_info
            revision=model_info(model_id).sha
        except Exception:
            revision=None
    params=None
    try:
        params=int(sum(int(p.numel()) for p in model.parameters()))
    except Exception:
        pass
    dtype=None
    try:
        dtype=str(next(model.parameters()).dtype)
    except Exception:
        pass
    return {
        "model_id":str(model_id),
        "resolved_revision":str(revision) if revision else None,
        "num_parameters":params,
        "dtype":dtype,
    }
