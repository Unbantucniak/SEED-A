/** Text offsets refer to the saved document revision in which the edit was accepted. */
export type AppliedRange = { offset: number; after: string };

function meaningfulRange(text: string, start: number, end: number): [number, number] {
  const value = text.slice(start, end);
  return [start + value.length - value.trimStart().length, start + value.trimEnd().length];
}

export function selectsAppliedRange(text: string, start: number, end: number, edit: AppliedRange): boolean {
  const left = edit.offset;
  const right = left + edit.after.length;
  if (left < 0 || right > text.length || text.slice(left, right) !== edit.after || !edit.after.trim()) return false;
  const [first, last] = meaningfulRange(text, left, right);
  if (start === end) {
    // At the beginning of the following nonempty line the cursor belongs to that line.
    return (start >= left && start < right) || (start === right && (right === text.length || !edit.after.endsWith("\n")));
  }
  const [selectedFirst, selectedLast] = meaningfulRange(text, start, end);
  if (selectedFirst === first && selectedLast === last) return true;
  if (start === 0 && end === text.length) {
    // A complete-file selection can still identify one snippet when every other
    // line is blank or a Python comment. A second definition never qualifies.
    const onlyComments = (outside: string) => outside.split(/\r?\n/).every(line => !line.trim() || line.trimStart().startsWith("#"));
    return onlyComments(text.slice(0, left)) && onlyComments(text.slice(right));
  }
  return false;
}

export function replacementWithTargetEnding(sourceCode: string, target: string, suffix: string, eol: string): string {
  let value = sourceCode.replace(/\r?\n/g, eol);
  if (!target.endsWith("\n") && suffix.startsWith(eol) && value.endsWith(eol)) {
    // The original line separator is outside the selection and stays in the file.
    value = value.slice(0, -eol.length);
  } else if (target.endsWith("\n") && !value.endsWith(eol)) {
    value += eol;
  }
  return value;
}
