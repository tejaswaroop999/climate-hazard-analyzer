import { expect, it } from "vitest";
import { csvCell } from "./csv";
it("escapes quotes and protects formula text", () => {
  expect(csvCell('a"b')).toBe('"a""b"');
  expect(csvCell("=SUM(A1)")).toContain("'=SUM(A1)");
  expect(csvCell(-1)).toBe('"-1"');
  expect(csvCell(null)).toBe('""');
});
