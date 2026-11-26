"""Original public task contracts; expected outputs are tests, never solutions."""
from typing import Any
import json
from pydantic import BaseModel, Field, field_validator, model_validator


class Case(BaseModel):
    args: list[Any] = Field(max_length=16)
    expected: Any

    @model_validator(mode='after')
    def finite_json_values(self):
        try:
            rendered = json.dumps(self.model_dump(), ensure_ascii=False, allow_nan=False)
        except (ValueError, TypeError, RecursionError) as error:
            raise ValueError('测试值必须为有限的JSON数据') from error
        if len(rendered) > 12000:
            raise ValueError('单条测试过大')
        return self


class TaskSpec(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    requirement: str = Field(min_length=5, max_length=6000)
    entry_point: str = Field(min_length=1, max_length=80)
    cases: list[Case] = Field(min_length=1, max_length=40)
    scope: str = Field(default='workbench-python', min_length=1, max_length=80)
    version: str = Field(default='v1', min_length=1, max_length=40)

    @field_validator('entry_point')
    @classmethod
    def valid_identifier(cls, value):
        if not value.isidentifier() or value.startswith('_'):
            raise ValueError('entry_point must be a public Python identifier')
        return value


def task(identifier, title, requirement, entry_point, rows, version='v1'):
    return {'id': identifier, **TaskSpec(title=title, requirement=requirement,
        entry_point=entry_point, cases=[Case(args=a, expected=e) for a, e in rows],
        version=version).model_dump(), 'source': 'original_public_contract'}


TASKS = [
    task('stable_unique', '稳定去重', 'Implement stable_unique(items): return a new list containing each hashable item once, preserving first appearance order. Do not mutate input.', 'stable_unique',
         [([[]], []), ([[3, 1, 3, 2, 1]], [3, 1, 2]), ([['a', 'a', 'b']], ['a', 'b']), ([[0, -1, 0]], [0, -1])]),
    task('merge_ranges', '合并重叠区间', 'Implement merge_ranges(intervals): input is a list of two-element integer lists [start,end] with start<=end. Return sorted merged intervals as lists. Touching intervals merge. Empty input returns []. Do not mutate input.', 'merge_ranges',
         [([[]], []), ([[[5, 7], [1, 3], [3, 6]]], [[1, 7]]), ([[[1, 2], [4, 5]]], [[1, 2], [4, 5]]), ([[[1, 8], [2, 3]]], [[1, 8]])]),
    task('word_counts', '大小写归一词频', 'Implement word_counts(text): split on whitespace, lowercase each token, count occurrences and return a dictionary. Punctuation remains part of the token. Empty or whitespace input returns {}.', 'word_counts',
         [([''], {}), ([' Red blue RED '], {'red': 2, 'blue': 1}), (['a\tb\na'], {'a': 2, 'b': 1}), (['Hi, hi'], {'hi,': 1, 'hi': 1})]),
    task('chunk_items', '按大小分组', 'Implement chunk_items(items, size): return a list of consecutive list chunks of at most size elements, preserving order. If size<=0 return []. Empty input returns []. Do not mutate input.', 'chunk_items',
         [([[1, 2, 3, 4, 5], 2], [[1, 2], [3, 4], [5]]), ([[], 3], []), ([[1], 0], []), ([[1, 2], 5], [[1, 2]])]),
    task('clamp10', '数值限幅 0–10', 'Implement clamp_value(value): return max(0, min(10, value)). Accept integers and floats.', 'clamp_value',
         [([-3], 0), ([4], 4), ([25], 10), ([2.5], 2.5)]),
    task('clamp100', '数值限幅 0–100', 'Implement clamp_value(value): return max(0, min(100, value)). Accept integers and floats.', 'clamp_value',
         [([-3], 0), ([40], 40), ([250], 100), ([12.5], 12.5)]),
    task('word_counts_v2', '词频 v2：保留大小写', 'Implement word_counts(text): split on whitespace and count occurrences, preserving token case exactly. Punctuation remains part of each token. Empty or whitespace input returns {}.', 'word_counts',
         [([''], {}), (['Red red Red'], {'Red': 2, 'red': 1}), (['a\tb\na'], {'a': 2, 'b': 1})], version='v2'),
]
