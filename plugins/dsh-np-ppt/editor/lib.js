export function normalizeRelativePath(value) {
  if (typeof value !== "string") {
    throw new TypeError("文件路径必须是字符串");
  }

  let path = value.trim().replaceAll("\\", "/");
  try {
    path = decodeURIComponent(path);
  } catch {
    // Keep the original path when it contains a literal percent sign.
  }

  path = path.replace(/^file:\/\/+/, "").replace(/^\.\//, "");
  if (!path || path.includes("\0") || path.startsWith("/") || /^[A-Za-z]:\//.test(path)) {
    throw new Error(`不允许的绝对路径：${value}`);
  }

  const parts = [];
  for (const part of path.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") throw new Error(`不允许越过项目目录：${value}`);
    parts.push(part);
  }

  if (parts.length === 0) throw new Error(`无效文件路径：${value}`);
  return parts.join("/");
}

export function dirname(path) {
  const normalized = normalizeRelativePath(path);
  const index = normalized.lastIndexOf("/");
  return index === -1 ? "" : normalized.slice(0, index);
}

export function basename(path) {
  const normalized = normalizeRelativePath(path);
  return normalized.slice(normalized.lastIndexOf("/") + 1);
}

export function joinDeckPath(base, path) {
  const child = normalizeRelativePath(path);
  if (!base) return child;
  const normalizedBase = normalizeRelativePath(base);
  if (child === normalizedBase || child.startsWith(`${normalizedBase}/`)) return child;
  return normalizeRelativePath(`${normalizedBase}/${child}`);
}

function unquoteYamlScalar(value) {
  const text = value.trim();
  if (text.startsWith('"')) {
    const match = text.match(/^"(?:\\.|[^"\\])*"/);
    if (match) {
      try {
        return JSON.parse(match[0]);
      } catch {
        return match[0].slice(1, -1);
      }
    }
  }
  if (text.startsWith("'")) {
    const end = text.indexOf("'", 1);
    if (end !== -1) return text.slice(1, end).replaceAll("''", "'");
  }
  return text.replace(/\s+#.*$/, "").trim();
}

export function extractPagePaths(manifestText) {
  const trimmed = manifestText.trim();
  if (!trimmed) throw new Error("PPTD manifest 是空文件");

  if (trimmed.startsWith("{")) {
    const parsed = JSON.parse(trimmed);
    if (!Array.isArray(parsed.pages)) throw new Error("PPTD manifest 缺少 pages 数组");
    return parsed.pages.map((path) => normalizeRelativePath(String(path)));
  }

  const lines = manifestText.replaceAll("\r\n", "\n").split("\n");
  const pageHeader = lines.findIndex((line) => /^(\s*)pages\s*:\s*(?:#.*)?$/.test(line));
  if (pageHeader === -1) throw new Error("PPTD manifest 缺少 pages 列表");

  const headerIndent = lines[pageHeader].match(/^\s*/)[0].length;
  const pages = [];
  for (let index = pageHeader + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    const indent = line.match(/^\s*/)[0].length;
    if (indent <= headerIndent && !/^\s*-/.test(line)) break;
    const match = line.match(/^\s*-\s*(.+?)\s*$/);
    if (!match) break;
    const path = unquoteYamlScalar(match[1]);
    if (path) pages.push(normalizeRelativePath(path));
  }

  if (pages.length === 0) throw new Error("PPTD manifest 的 pages 列表为空");
  return pages;
}

export function titleFromManifest(manifestText, fallback) {
  const trimmed = manifestText.trim();
  if (trimmed.startsWith("{")) {
    try {
      return JSON.parse(trimmed).title || fallback;
    } catch {
      return fallback;
    }
  }
  const match = manifestText.match(/^title\s*:\s*(.+?)\s*$/m);
  return match ? unquoteYamlScalar(match[1]) : fallback;
}

export function assertWritableChangePath(base, requestedPath) {
  const path = joinDeckPath(base, requestedPath);
  if (!/\.(?:pptd|page)$/i.test(path)) {
    throw new Error(`为安全起见，仅允许编辑 .pptd/.page：${requestedPath}`);
  }
  return path;
}

// ── PPTD 一致性校验 ──────────────────────────────────────────────
// 保证 55173 编辑器预览与原生 PPTX 导出渲染一致：禁止发行"预览白底、导出正常"的页面。
// 与 compiler/export_pptx.py 的 validate_page_consistency 保持同样的判定逻辑。
export const CONSISTENCY_RULES = [
  "background 必须是纯色：只能用顶层 `color` 字段（#HEX/rgb()/rgba()）。禁止使用 `type:\"gradient\"` / `stops` / `angle`——55173 编辑器无法渲染渐变会显示白底，而 PPTX 编译器却能渲染渐变，这正是被禁止的「预览≠导出」偏差。编译器也支持 `background.color` 纯色，故统一用纯色后两端完全一致。",
  "`content.text` HTML 内的颜色必须用 #HEX/rgb()/rgba() 内联，禁止 $theme 变量——$theme 仅被 PPTX 编译器解析，编辑器内核会丢色。",
];

function parsePageContent(text) {
  if (typeof text !== "string" || !text.trim()) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export function validatePageConsistency(path, pageText) {
  const violations = [];
  const pageId = basename(path);
  const data = parsePageContent(pageText);
  if (!data || typeof data !== "object") {
    violations.push(`[${pageId}] 页面不是合法 JSON/YAML 对象`);
    return violations;
  }
  const bg = data.background;
  if (!bg || typeof bg !== "object") {
    violations.push(`[${pageId}] 缺少 \`background\` 区块`);
  } else if (bg.type === "gradient" || "stops" in bg || "angle" in bg) {
    violations.push(
      `[${pageId}] background 用了渐变（\`type\`/\`stops\`/\`angle\`）。55173 编辑器无法渲染渐变会显示白底。请改用纯色 \`color\`——编译器也支持纯色，两端即可一致。`,
    );
  } else if (!("color" in bg) || !bg.color) {
    violations.push(`[${pageId}] background 缺少 \`color\` 字段`);
  } else if (typeof bg.color === "string" && bg.color.startsWith("$")) {
    violations.push(
      `[${pageId}] background.color 使用了 \`$theme\`（\`${bg.color}\`）；编辑器无法解析主题变量，请用 #HEX/rgb() 内联。`,
    );
  }
  const dollarRe = /color\s*:\s*\$[a-zA-Z_]+/i;
  for (const el of Array.isArray(data.elements) ? data.elements : []) {
    if (el.elementType !== "text") continue;
    const txt = (el.content && el.content.text) || "";
    if (dollarRe.test(txt)) {
      violations.push(
        `[${pageId}] 元素 \`${el.elementId || "?"}\` 的 content.text HTML 中使用了 $theme 颜色；请用 #HEX/rgb() 内联以保证编辑器与导出颜色一致。`,
      );
    }
  }
  return violations;
}

export function validateDeckConsistency(pages) {
  const all = [];
  for (const page of pages) {
    const vs = validatePageConsistency(page.path, page.content);
    for (const v of vs) all.push(v);
  }
  return all;
}
