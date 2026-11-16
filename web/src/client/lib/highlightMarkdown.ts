interface Point {
  offset?: number;
}

interface HastNode {
  type: string;
  value?: string;
  tagName?: string;
  properties?: Record<string, unknown>;
  children?: HastNode[];
  position?: { start: Point; end: Point };
}

function align(value: string, source: string): number[] | null {
  const map: number[] = [];
  let j = 0;
  for (let i = 0; i < value.length; i++) {
    while (j < source.length && source[j] !== value[i]) j++;
    if (j >= source.length) return null;
    map.push(j++);
  }
  return map;
}

function inRanges(offset: number, ranges: [number, number][]): boolean {
  return ranges.some(([start, end]) => offset >= start && offset < end);
}

function splitText(node: HastNode, markdown: string, ranges: [number, number][]): HastNode[] {
  const value = node.value ?? "";
  const start = node.position?.start.offset;
  const end = node.position?.end.offset;
  if (start === undefined || end === undefined || !value) return [node];
  if (!ranges.some(([a, b]) => a < end && b > start)) return [node];
  const map = align(value, markdown.slice(start, end));
  const flags = map ? map.map((m) => inRanges(start + m, ranges)) : value.split("").map(() => true);
  const out: HastNode[] = [];
  let at = 0;
  for (let i = 1; i <= value.length; i++) {
    if (i < value.length && flags[i] === flags[at]) continue;
    const text: HastNode = { type: "text", value: value.slice(at, i) };
    const marked = flags[at] && text.value!.trim().length > 0;
    out.push(marked ? { type: "element", tagName: "mark", properties: { className: ["source-highlight"] }, children: [text] } : text);
    at = i;
  }
  return out;
}

function walk(node: HastNode, markdown: string, ranges: [number, number][]): void {
  if (!node.children) return;
  node.children = node.children.flatMap((child) => {
    if (child.type === "text") return splitText(child, markdown, ranges);
    walk(child, markdown, ranges);
    return [child];
  });
}

export function rehypeHighlightRanges(options: { markdown: string; ranges: [number, number][] }) {
  return (tree: HastNode) => {
    if (options.ranges.length > 0) walk(tree, options.markdown, options.ranges);
  };
}
