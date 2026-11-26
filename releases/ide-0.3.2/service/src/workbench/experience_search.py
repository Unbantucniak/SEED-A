"""Offline query expansion and relevance checks for the IDE search box."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


# These are software terms, not experience IDs or answers. Unlisted terms and
# user-defined identifiers remain searchable in their original language.
TERMS = (
    ("unique", "deduplicate", "dedup", "remove duplicates", "去重", "去除重复", "消除重复"),
    ("order", "stable", "preserve order", "preserving order", "保序", "顺序", "次序", "首次出现"),
    ("count", "frequency", "frequencies", "counts", "频次", "频率", "计数", "词频"),
    ("word", "words", "tokens", "词语", "单词", "分词", "词频"),
    ("lowercase", "casefold", "ignore case", "ignoring case", "忽略大小写", "不区分大小写", "小写"),
    ("clamp", "clip", "限幅", "裁剪", "截断数值", "钳制"),
    ("split", "partition", "拆分", "拆开", "分割"),
    ("merge", "combine", "合并", "归并"),
    ("range", "interval", "intervals", "区间", "范围"),
    ("sort", "sorted", "sorting", "排序"),
    ("encode", "encoding", "编码"),
    ("decode", "decoding", "解码"),
    ("parse", "parsing", "解析"),
    ("serialize", "serialization", "序列化"),
    ("format", "formatting", "格式化"),
    ("date", "dates", "日期"),
    ("calendar", "日历", "历法", "农历"),
    ("path", "paths", "路径"),
    ("filename", "文件名"),
    ("empty", "为空", "空值"),
    ("whitespace", "空格", "空白"),
    ("cache", "caching", "缓存"),
    ("retry", "重试"),
    ("precision", "精度"),
    ("round", "rounding", "舍入", "四舍五入"),
    ("suffix", "后缀"),
    ("prefix", "前缀"),
    ("normalize", "normalization", "归一", "规范化"),
    ("sum", "求和"),
    ("square", "squared", "平方"),
    ("positive", "正数", "正值"),
    ("negative", "负数", "负值"),
)
STOP = ENGLISH_STOP_WORDS | {
    "implement", "function", "return", "returns", "def", "language", "python",
    "calculate", "write", "given", "import", "input", "output", "value", "values",
    "list", "items", "item", "self", "int", "str", "args", "kwargs", "using",
}
CJK = re.compile(r"[\u3400-\u9fff]+")
CHINESE_DIGITS = {c: i for i, c in enumerate("零一二三四五六七八九")}
CHINESE_DIGITS["两"] = 2
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}


def _number(match):
    digits = match.group()
    if not any(c in CHINESE_UNITS for c in digits):
        return "".join(str(CHINESE_DIGITS[c]) for c in digits)
    total, current = 0, None
    for c in digits:
        if c in CHINESE_UNITS:
            total += (current if current is not None else 1) * CHINESE_UNITS[c]
            current = None
        else:
            current = CHINESE_DIGITS[c]
    return str(total + (current or 0))


def _pattern(alias):
    escaped = re.escape(alias)
    if alias.isascii():
        return r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])"
    return escaped


ALIASES = [(terms, re.compile("|".join(_pattern(a) for a in terms))) for terms in TERMS]


@lru_cache(maxsize=768)
def _features(text):
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", normalized).casefold().replace("_", " ")
    words = set(re.findall(r"[a-z][a-z0-9]*|[0-9]+", normalized)) - STOP
    terms = [aliases for aliases, pattern in ALIASES if pattern.search(normalized)]
    words.update(aliases[0] for aliases in terms)
    for run in CJK.findall(normalized):
        words.update(run[i:i+2] for i in range(len(run)-1))
    numbers = set(re.findall(r"(?<!\d)\d+(?!\d)", normalized))
    numbers.update(_number(m) for m in re.finditer(r"[零一二两三四五六七八九十百千]+", normalized))
    return words, terms, numbers


def query_variants(query):
    _, groups, numbers = _features(query)
    if not groups:
        return (query,)
    english = " ".join([*(group[0] for group in groups), *sorted(numbers)])
    chinese = " ".join(term for group in groups for term in group if not term.isascii())
    return tuple(dict.fromkeys([query, english, chinese]))


def rank_verified(query, rows, limit):
    """Rerank records that passed the existing scope/version/receipt gate."""
    words, concepts, numbers = _features(query)
    anchors = {group[0] for group in concepts}
    ascii_terms = {w for w in words if w.isascii() and not w.isdecimal()}
    ranked = []
    for row in rows:
        signature = next((line for line in row["code"].splitlines()
                          if line.lstrip().startswith(("def ", "async def ", "class "))), "")
        description = " ".join((row.get("title") or "", row["requirement"], signature))
        doc_words, _, doc_numbers = _features(description)
        shared = words & doc_words
        if not shared or (anchors and not anchors & doc_words):
            continue
        # English stop words or a generic mention of Python must not by
        # themselves cause an unrelated suggestion when the library is small.
        informative = anchors | ascii_terms
        if informative:
            coverage = len(informative & doc_words) / len(informative)
        else:
            coverage = len(shared) / max(len(words), 1)
        if coverage < 0.18:
            continue
        numeric = len(numbers & doc_numbers) / len(numbers) if numbers else 0.0
        score = 0.5 * coverage + 0.4 * row["similarity"] + 0.1 * numeric
        ranked.append({**row, "composite_score": score})
    ranked.sort(key=lambda item: (-item["composite_score"], -item["similarity"], item["id"]))
    seen, result = set(), []
    for row in ranked:
        key = (row["requirement"], row["code"], row.get("file_label"), row.get("source_path"))
        if key not in seen:
            seen.add(key)
            result.append(row)
        if len(result) == limit:
            break
    return result
