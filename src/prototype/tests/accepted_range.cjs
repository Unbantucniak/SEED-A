const assert = require("node:assert/strict");
const {replacementWithTargetEnding, selectsAppliedRange} = require("../out/acceptedRange");

for (const eol of ["\n", "\r\n"]) {
  const source = "def trim(x):" + eol + "    return x.strip()";
  const original = "def trim(x):" + eol + "    return x";
  const header = "# header" + eol;
  const footer = eol + "# footer" + eol;
  const after = replacementWithTargetEnding(source + eol, original, footer, eol);
  assert.equal(after, source, "keep the existing separator outside the target selection");
  assert.equal(replacementWithTargetEnding(source, original + eol, "# footer", eol), source + eol);
  const text = header + after + footer;
  const edit = {offset:header.length, after};
  assert.ok(selectsAppliedRange(text, edit.offset, edit.offset + after.length, edit));
  assert.ok(selectsAppliedRange(text, edit.offset, edit.offset + after.length + eol.length, edit));
  assert.ok(selectsAppliedRange(text, edit.offset + 4, edit.offset + 4, edit), "cursor in accepted code");
  assert.ok(selectsAppliedRange(text, 0, text.length, edit), "whole-file with comment-only surrounding lines");
  assert.ok(!selectsAppliedRange(text, 0, 0, edit), "cursor in a different line");
  const targetIncludesEol = {offset:edit.offset, after:after + eol};
  assert.ok(selectsAppliedRange(text, edit.offset, edit.offset + after.length, targetIncludesEol),
    "when the accepted text includes the newline, a re-selection without it stays credited");
  const nextLine = edit.offset + after.length + eol.length;
  assert.ok(!selectsAppliedRange(text, nextLine, nextLine, targetIncludesEol));
  const other = "def another(x):" + eol + "    return x";
  const multi = text + other;
  assert.ok(!selectsAppliedRange(multi, 0, multi.length, edit));
  assert.ok(!selectsAppliedRange(multi, text.length, multi.length, edit));
  assert.ok(!selectsAppliedRange(multi, text.length + 1, text.length + 1, edit));
  const repeated = text + source;
  assert.ok(!selectsAppliedRange(repeated, text.length, repeated.length, edit), "same bytes at a different offset");
  assert.ok(!selectsAppliedRange(text.replace("strip()", "upper()"), edit.offset, edit.offset + after.length, edit));
}
console.log("PASS: LF/CRLF admission, selection boundaries, caret, whole file, unrelated functions, changed text");
