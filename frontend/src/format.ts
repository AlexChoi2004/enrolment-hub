/** Small, pure helpers for the numbers on the page. */

/** A whole-number percentage of `part` in `whole`, kept between 0 and 100 (0 when there is nothing to divide by). */
export function percent(part: number, whole: number): number {
  if (whole <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((part / whole) * 100)));
}

export function plural(count: number, one: string, many: string = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function cp(value: number): string {
  return `${value} cp`;
}

/** "Autumn 2027" becomes "Semester 1" and "Spring 2027" "Semester 2": used only for the heading's year and semester. */
export function yearAndSemester(year: number, semester: number): string {
  return `Year ${year}, Semester ${semester}`;
}

export function firstName(displayName: string): string {
  return displayName.trim().split(/\s+/)[0] ?? displayName;
}
