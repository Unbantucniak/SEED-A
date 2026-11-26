"""CPU semantic retrieval over the already eligible, local experience records."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np


class SemanticSearch:
    def __init__(self, directory: Path, threshold: float, margin: float):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.threshold = threshold
        self.margin = margin
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.model = ort.InferenceSession(str(directory / "model.onnx"), sess_options=options,
                                          providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>"), pad_token="<pad>")
        self.input_names = {i.name for i in self.model.get_inputs()}
        self.vector = lru_cache(maxsize=2048)(self._vector)

    def _vector(self, text):
        tokens = self.tokenizer.encode(text)
        ids = np.asarray([tokens.ids], dtype=np.int64)
        mask = np.asarray([tokens.attention_mask], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = self.model.run(None, feed)[0]
        vector = (hidden[0] * mask[0, :, None]).sum(axis=0) / max(1, mask.sum())
        return (vector / max(float(np.linalg.norm(vector)), 1e-12)).astype(np.float32)

    def candidates(self, query, eligible):
        """Rank distinct, compatible snippets using normalized multilingual vectors."""
        if not eligible or not query.strip():
            return []
        query_vector = self.vector("query: " + query)
        ranked = []
        for row in eligible:
            title = row.get("title") or row["requirement"]
            description = title if title == row["requirement"] else title + " " + row["requirement"]
            signature = next((s.strip() for s in row["code"].splitlines()
                              if s.lstrip().startswith(("def ", "async def ", "class "))), "")
            vector = self.vector("passage: " + description + " " + signature)
            cosine = float(query_vector @ vector)
            ranked.append({**row, "similarity": cosine, "composite_score": cosine})
        ranked.sort(key=lambda r: (-r["composite_score"], r["id"]))
        distinct = {}
        for row in ranked:
            distinct.setdefault((row["requirement"], row["code"]), row)
        return list(distinct.values())

    def select(self, candidates, limit):
        if not candidates:
            return []
        first = candidates[0]["composite_score"]
        if first < self.threshold or (len(candidates) > 1 and
                first - candidates[1]["composite_score"] < self.margin):
            return []
        return [row for row in candidates[:limit] if row["composite_score"] >= self.threshold]
