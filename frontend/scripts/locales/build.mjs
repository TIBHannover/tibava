// Converts src/locales/<lang>.yaml into src/locales/<lang>.json for vue-i18n.
// Values tagged `!md` are rendered from Markdown to HTML; all others are copied as-is.
// Afterwards, checks the source code for missing and unused keys.
// Usage (from frontend/): npm run locales
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";
import { marked } from "marked";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const srcDir = path.join(frontendDir, "src");
const localesDir = path.join(srcDir, "locales");
const sourceLocale = "en";

// External links (http/https) in !md texts open in a new tab. Relative links,
// anchors and mailto: keep the default behaviour; raw <a> tags are left as written.
marked.use({
  renderer: {
    link(token) {
      const html = marked.Renderer.prototype.link.call(this, token);
      if (!/^https?:\/\//i.test(token.href)) return html;
      return html.replace(/^<a /, '<a target="_blank" rel="noopener noreferrer" ');
    },
  },
});

const warnings = [];
const warn = (msg) => warnings.push(msg);

// ---------------------------------------------------------------------------
// YAML -> JSON
// ---------------------------------------------------------------------------

class Markdown {
  constructor(text) {
    this.text = text;
  }
}
const schema = yaml.DEFAULT_SCHEMA.extend([
  new yaml.Type("!md", { kind: "scalar", construct: (text) => new Markdown(text) }),
]);

// Untagged strings that look like Markdown or HTML were probably meant to be `!md`.
const MARKUP_HINTS = [
  [/\*\*[^*\n]+\*\*/, "**bold**"],
  [/\[[^\]\n]+\]\([^)\s]+\)/, "[link](url)"],
  [/\n[ \t]*\n/, "blank line (paragraph)"],
  [/^#{1,6} /m, "# heading"],
  [/^[ \t]*[-*] /m, "- list item"],
  [/<[a-z][^>]*>/i, "HTML tag"],
];

// Renders !md values, checks strings, and records which file defined each key.
function convert(node, prefix, file, keyFiles) {
  const result = {};
  for (const [key, value] of Object.entries(node)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value instanceof Markdown) {
      // vue-i18n treats `{...}` as interpolation and `@:` as a linked message.
      if (/[{}]|@:/.test(value.text)) {
        warn(`${file}: "${fullKey}" is !md but contains vue-i18n syntax ({ } or @:)`);
      }
      result[key] = marked.parse(value.text).trim();
      keyFiles.set(fullKey, file);
    } else if (value && typeof value === "object") {
      result[key] = convert(value, fullKey, file, keyFiles);
    } else {
      if (typeof value === "string") {
        const hint = MARKUP_HINTS.find(([re]) => re.test(value));
        if (hint) warn(`${file}: "${fullKey}" contains ${hint[1]} but is not tagged !md`);
      }
      result[key] = value;
      keyFiles.set(fullKey, file);
    }
  }
  return result;
}

// One file per language: src/locales/<lang>.yaml
const files = fs.readdirSync(localesDir).filter((f) => /\.ya?ml$/.test(f));
if (files.length === 0) {
  console.error(`No .yaml files found in ${localesDir}`);
  process.exit(1);
}

let sourceKeys = null;
for (const file of files) {
  let data;
  try {
    data = yaml.load(fs.readFileSync(path.join(localesDir, file), "utf8"), { schema }) ?? {};
  } catch (err) {
    if (!(err instanceof yaml.YAMLException)) throw err;
    console.error(`${file}: ${err.message}\n\nNothing was written.`);
    process.exit(1);
  }
  if (typeof data !== "object" || Object.keys(data).length === 0) {
    console.error(`${file}: file is empty or not a mapping of keys\n\nNothing was written.`);
    process.exit(1);
  }
  const keyFiles = new Map(); // key -> file that defines it
  const json = convert(data, "", file, keyFiles);
  const lang = file.replace(/\.ya?ml$/, "");
  fs.writeFileSync(path.join(localesDir, `${lang}.json`), JSON.stringify(json, null, 2) + "\n");
  console.log(`${file} -> ${lang}.json (${keyFiles.size} keys)`);
  if (lang === sourceLocale) sourceKeys = keyFiles;
}

// ---------------------------------------------------------------------------
// Key usage check against src/**/*.{vue,js}
// ---------------------------------------------------------------------------

function listSourceFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return full === localesDir ? [] : listSourceFiles(full);
    return /\.(vue|js|ts)$/.test(entry.name) ? [full] : [];
  });
}

// Blank out comments but keep line breaks, so line numbers stay correct.
// `//` is only treated as a comment at the start of a line, to leave URLs alone.
function stripComments(code) {
  const blank = (m) => m.replace(/[^\n]/g, " ");
  return code
    .replace(/<!--[\s\S]*?-->/g, blank)
    .replace(/\/\*[\s\S]*?\*\//g, blank)
    .replace(/^[ \t]*\/\/.*$/gm, blank);
}

const CALL = /(?:\$t|\$tc|\$te|i18n\.t|i18n\.tc)\(\s*(['"`])((?:(?!\1)[^\\]|\\.)*)\1/g;

const used = new Map(); // key -> ["file:line", ...]
const dynamic = [];
for (const file of listSourceFiles(srcDir)) {
  const code = stripComments(fs.readFileSync(file, "utf8"));
  const rel = path.relative(frontendDir, file);
  for (const m of code.matchAll(CALL)) {
    const where = `${rel}:${code.slice(0, m.index).split("\n").length}`;
    if (m[2].includes("${")) {
      dynamic.push(`${where}  ${m[2]}`);
      continue;
    }
    if (!used.has(m[2])) used.set(m[2], []);
    used.get(m[2]).push(where);
  }
}

if (sourceKeys) {
  const missing = [...used].filter(([key]) => !sourceKeys.has(key));
  const unused = [...sourceKeys].filter(([key]) => !used.has(key));
  for (const [key, places] of missing) warn(`missing key "${key}" used in ${places.join(", ")}`);
  for (const [key, file] of unused) warn(`${file}: unused key "${key}"`);
} else {
  warn(`no ${sourceLocale}.yaml found, skipped key usage check`);
}
for (const d of dynamic) warn(`key built at runtime, cannot be checked: ${d}`);

if (warnings.length) {
  console.warn(`\n${warnings.length} warning(s):`);
  for (const w of warnings) console.warn(`  - ${w}`);
} else {
  console.log("No missing or unused keys.");
}
