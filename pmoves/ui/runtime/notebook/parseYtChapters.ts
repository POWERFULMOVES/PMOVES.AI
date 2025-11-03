export function parseChapters(text: string) {
  const lines = text.split(/\r?\n/);
  const result: Array<{ t: number; title: string }> = [];
  for (const line of lines) {
    const match = line.match(/(\d{1,2}:)?\d{1,2}:\d{2}/);
    if (!match) continue;
    const parts = match[0].split(":").map((value) => parseInt(value, 10));
    const seconds =
      parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1];
    const title =
      line
        .replace(match[0], "")
        .trim()
        .replace(/^[-–—:\s]+/, "") || `Chapter ${result.length + 1}`;
    result.push({ t: seconds, title });
  }
  return result;
}
