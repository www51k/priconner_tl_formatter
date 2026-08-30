const PYODIDE_VERSION = "0.27.2";
const SCRIPT_NAMES = ["character_aliases.py", "tl_common.py", "format_tl.py", "add_set_operations.py", "validate_tl.py", "review_tl.py"];

const input = document.querySelector("#input");
const output = document.querySelector("#output");
const formatButton = document.querySelector("#format");
const copyButton = document.querySelector("#copy-output");
const clearButton = document.querySelector("#clear-input");
const status = document.querySelector("#status");
const validation = document.querySelector("#validation");
const review = document.querySelector("#review");
const reviewContent = document.querySelector("#review-content");
const formationList = document.querySelector("#formation-list");
const diagnosis = document.querySelector("#tl-diagnosis");
const formationPanel = document.querySelector("#formation-panel");
const carryoverTime = document.querySelector("#carryover-time");
const carryoverTimeValue = document.querySelector("#carryover-time-value");
const FORMATION_CACHE_KEY = "priconner_tl_formatter.formation.v1";

let pyodidePromise;
let draggedSlot = null;
let formationTouched = false;

carryoverTime.addEventListener("input", () => {
  carryoverTimeValue.value = carryoverTime.value;
  carryoverTimeValue.textContent = carryoverTime.value;
});

function saveFormationCache() {
  try {
    const names = [...formationList.querySelectorAll("input")].map((field) => field.value);
    localStorage.setItem(FORMATION_CACHE_KEY, JSON.stringify(names));
  } catch (_) {
    // プライベートブラウズ等で保存できない場合も、整形処理は継続する。
  }
}

function restoreFormationCache() {
  try {
    const names = JSON.parse(localStorage.getItem(FORMATION_CACHE_KEY) || "null");
    if (!Array.isArray(names) || names.length !== 5) return;
    [...formationList.querySelectorAll("input")].forEach((field, index) => {
      field.value = typeof names[index] === "string" ? names[index] : "";
    });
    // 保存済み編成は初期値。新しいTLを貼り付けた際は、本文から抽出した
    // 編成で更新できるよう、ユーザー編集済みとは扱わない。
    formationTouched = false;
  } catch (_) {
    // 保存データが壊れていても、空の編成欄から開始する。
  }
}

function updateSlotNumbers() {
  [...formationList.children].forEach((slot, index) => {
    slot.querySelector(".slot-number").textContent = String(5 - index);
    slot.querySelector("input").setAttribute("aria-label", `${5 - index}番キャラ`);
  });
}

formationList.addEventListener("dragstart", (event) => {
  draggedSlot = event.target.closest(".formation-slot");
  formationTouched = true;
  if (draggedSlot) draggedSlot.classList.add("dragging");
});
formationList.addEventListener("dragend", () => {
  if (draggedSlot) draggedSlot.classList.remove("dragging");
  draggedSlot = null;
  saveFormationCache();
});
formationList.addEventListener("dragover", (event) => {
  event.preventDefault();
  const target = event.target.closest(".formation-slot");
  if (!draggedSlot || !target || target === draggedSlot) return;
  const rect = target.getBoundingClientRect();
  formationList.insertBefore(draggedSlot, event.clientX < rect.left + rect.width / 2 ? target : target.nextSibling);
  updateSlotNumbers();
});

formationList.addEventListener("input", () => {
  formationTouched = true;
  saveFormationCache();
});

function pickCharacters(source) {
  const excluded = new Set(["開始時", "開始", "バトル開始", "ボス", "ボスUB", "敵", "敵UB", "止めぽ", "AUTO", "オート"]);
  const declarations = [];
  const sourceLines = source.split("\n");
  for (let index = 0; index < sourceLines.length - 1; index += 1) {
    const formal = sourceLines[index].trim();
    if (!formal || /[ \t　]/.test(formal) || /^(?:\\+|ーー|--|\/\/|TL表記)/.test(formal)) continue;
    let nextIndex = index + 1;
    while (nextIndex < sourceLines.length && /^(?:\s*|\\+)$/.test(sourceLines[nextIndex])) nextIndex += 1;
    const tlMatch = sourceLines[nextIndex]?.trim().match(/^TL表記は\s*(\S+)$/);
    if (tlMatch) declarations.push({ formal, tl: tlMatch[1] });
  }
  if (declarations.length === 5) return declarations.map(({ formal }) => formal).reverse();
  const names = [];
  for (const rawLine of source.split("\n")) {
    const candidateLine = rawLine.trimStart();
    const isTimedLine = /^(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*\d{1,2}:\d{1,2}(?:[-〜~](?:\d{1,2}:)?\d{1,2})?/.test(candidateLine)
      || /^(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*\d{1,2}(?=\s|　)/.test(candidateLine);
    const isArrowLine = /^(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*(?:→|➡︎|⇨|⇒|->|>)/.test(candidateLine);
    // 使用キャラ説明やコメント中の単語ではなく、時間行・矢印行だけから拾う。
    if (!isTimedLine && !isArrowLine) continue;
    const line = rawLine.split("//", 1)[0]
      .replace(/^\s*(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*/, "")
      .replace(/^(?:\d{1,2}:\d{1,2}(?:[-〜~](?:\d{1,2}:)?\d{1,2})?|\d{1,2})\s*/, "")
      .replace(/^(?:→|➡︎|⇨|⇒|->|>)\s*/, "");
    if (!line || line.startsWith("[") || line.startsWith("【")) continue;
    if (/^(?:タゲ|ターゲット)/.test(line) || /^(?:[ABC]\s*\/\s*)+[ABC]$/.test(line)) continue;
    const match = line.match(/^([^\s　\[\]【】「"'()（）]+)(?=[\s　\[【「"'()（）]|$)/);
    const name = match?.[1];
    if (
      name
      && !excluded.has(name)
      && !/^(?:ボス|敵)(?:UB)?$/.test(name)
      && !/^タゲ|^ターゲット/.test(name)
      && name.length <= 8
      && !names.includes(name)
    ) names.push(name);
    if (names.length === 5) break;
  }
  return names;
}

function autofillFormation(source) {
  const formationLine = source.split("\n").find((line) => /\(5\)[^|\]]+\|/.test(line) && /\(1\)[^|\]]+\]/.test(line));
  if (formationLine) {
    const parsed = [...formationLine.matchAll(/\(([54321])\)([^|\]]+)/g)]
      .map((match) => ({ number: Number(match[1]), name: match[2].trim() }))
      .filter(({ name }) => name);
    if (parsed.length === 5) {
      const byNumber = new Map(parsed.map(({ number, name }) => [number, name]));
      [...formationList.querySelectorAll("input")].forEach((field, index) => {
        field.value = byNumber.get(5 - index) || "";
      });
      formationTouched = true;
      return;
    }
  }
  if (formationTouched) return;
  const names = pickCharacters(source);
  const start = 5 - names.length;
  [...formationList.querySelectorAll("input")].forEach((field, index) => {
    field.value = index >= start ? names[index - start] : "";
  });
}

function isSetNotationLine(line) {
  // # / // / '' はコメント・注記なので、SET判定へ含めない。
  const structural = line.split(/#|\/\/|''/, 1)[0];
  const normalized = structural
    .replaceAll("⭕️", "O")
    .replaceAll("❌", "X")
    .replaceAll("〇", "O");
  return /^\s*\[[54321-]{5}\]/.test(normalized)
    || /[〇○◯⭕OXx0０×❌＿_－ー-]{5}/.test(normalized);
}

function diagnoseTL(source) {
  if (!source.trim()) {
    diagnosis.textContent = "TLを貼り付けると、自動判定します";
    formationPanel.hidden = true;
    return;
  }
  const lines = source.split("\n");
  const headerIndex = lines.findIndex((line) => /^\s*\[\(5\)/.test(line));
  const hasSetOperation = lines.some((line, index) =>
    index !== headerIndex && isSetNotationLine(line)
  );
  if (hasSetOperation) {
    diagnosis.innerHTML = "判定：<strong>セミオ扱い</strong>（SET操作あり。SET操作は不要として扱います）";
    formationPanel.hidden = true;
  } else {
    diagnosis.innerHTML = "判定：<strong>手動TL</strong>（SET表記なし）";
    formationPanel.hidden = false;
  }
}

function formationHeader() {
  const names = [...formationList.querySelectorAll("input")].map((field) => field.value.trim());
  const filled = names.filter(Boolean);
  if (!filled.length) return null;
  if (new Set(filled).size !== filled.length) throw new Error("編成内のキャラ名が重複しています");
  if (filled.length !== names.length) return null;
  return `[${names.map((name, index) => `(${5 - index})${name}`).join("|")}]`;
}

function applyFormation(source, header) {
  if (!header) return source;
  const lines = source.split("\n");
  if (lines[0]?.trim().startsWith("[") && (lines[0].includes("(5)") || /\[[54321O〇○◯X×－ー＿-]{5}\]/.test(lines[0]))) {
    lines.shift();
  }
  return `${header}\n${lines.join("\n")}`;
}

function ensureInitialSet(text) {
  const lines = text.split("\n");
  const headerIndex = lines.findIndex((line) => line.startsWith("[(") && line.includes("|"));
  const firstEventIndex = lines.findIndex((line) =>
    /\d{1,2}:\d{1,2}/.test(line)
    || /^\s*(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*(?:→|➡︎|⇨|⇒)/.test(line));
  const end = firstEventIndex < 0 ? lines.length : firstEventIndex;
  const start = headerIndex >= 0 ? headerIndex + 1 : 0;
  if (lines.slice(start, end).some((line) => /^\s*\[[54321-]{5}\](?:🅰️(?:ON|OFF))?\s*$/.test(line))) {
    return text;
  }
  if (headerIndex < 0) {
    const firstNonEmpty = lines.findIndex((line) => line.trim());
    if (firstNonEmpty >= 0 && /^\s*\[[54321-]{5}\]/.test(lines[firstNonEmpty])) {
      return text;
    }
    lines.unshift("[-----]🅰️OFF", "");
  } else {
    lines.splice(headerIndex + 1, 0, "", "[-----]🅰️OFF", "");
  }
  return lines.join("\n");
}

function setStatus(message, kind = "") {
  status.textContent = message;
  status.className = `status ${kind}`;
}

async function loadPython() {
  if (!pyodidePromise) {
    setStatus("処理エンジンを読み込み中...");
    pyodidePromise = (async () => {
      const { loadPyodide } = await import(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.mjs`);
      const pyodide = await loadPyodide({ indexURL: `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/` });
      pyodide.FS.mkdirTree("/home/pyodide/scripts");
      for (const name of SCRIPT_NAMES) {
        const source = await fetch(`scripts/${name}?v=20260830-carryover-2`).then((response) => {
          if (!response.ok) throw new Error(`${name} の読み込みに失敗しました`);
          return response.text();
        });
        pyodide.FS.writeFile(`/home/pyodide/scripts/${name}`, source);
      }
      await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/home/pyodide/scripts")
from format_tl import format_text
from add_set_operations import add_operations
from validate_tl import validate
from review_tl import collect_review_items
from tl_common import MASK_RE
`);
      return pyodide;
    })();
  }
  return pyodidePromise;
}

async function formatTL() {
  const source = input.value;
  if (!source.trim()) {
    setStatus("元TLを入力してください", "error");
    return;
  }
  formatButton.disabled = true;
  validation.hidden = true;
  review.hidden = true;
  try {
    const header = formationPanel.hidden ? null : formationHeader();
    const sourceWithFormation = applyFormation(source, header);
    const pyodide = await loadPython();
    pyodide.globals.set("source_text", sourceWithFormation);
    pyodide.globals.set("carryover_seconds", Number(carryoverTime.value));
    const result = await pyodide.runPythonAsync(`
import json
formatted = format_text(source_text, carryover_seconds=carryover_seconds)
report = []
set_text = add_operations(formatted, report=report)
errors = validate(set_text)
review_items = collect_review_items(set_text, formatted)
error_details = []
for error in errors:
    line_number = int(error.split(":", 1)[0])
    target_line = set_text.splitlines()[line_number - 1] if line_number > 0 else ""
    error_details.append(f"{error}\\n対象行: {target_line}")
json.dumps({"text": set_text, "errors": errors, "error_details": error_details, "review": review_items }, ensure_ascii=False)
`);
    const data = JSON.parse(result);
    output.textContent = ensureInitialSet(data.text);
    copyButton.disabled = false;
    if (data.review.length) {
      reviewContent.textContent = data.review.map((item) =>
        `行${item.line} / ${item.kind}\n${item.reason}\n${item.text}`
      ).join("\n\n");
      review.hidden = false;
    }
    if (data.errors.length) {
      validation.textContent = `検証エラー（${data.errors.length}件）\n\n${data.error_details.join("\n\n")}`;
      validation.hidden = false;
      setStatus("整形完了・要確認", "error");
    } else {
      setStatus(`整形完了（レビュー対象 ${data.review.length}件）`, "ready");
    }
  } catch (error) {
    setStatus(`処理に失敗しました: ${error.message}`, "error");
  } finally {
    formatButton.disabled = false;
  }
}

formatButton.addEventListener("click", formatTL);
input.addEventListener("input", () => {
  autofillFormation(input.value);
  diagnoseTL(input.value);
});
clearButton.addEventListener("click", () => {
  input.value = "";
  output.textContent = "";
  copyButton.disabled = true;
  validation.hidden = true;
  review.hidden = true;
  formationTouched = false;
  autofillFormation("");
  diagnoseTL("");
  setStatus("準備完了", "ready");
});
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(output.textContent);
  copyButton.textContent = "コピーしました";
  setTimeout(() => { copyButton.textContent = "コピー"; }, 1400);
});

restoreFormationCache();
loadPython().then(() => setStatus("準備完了", "ready")).catch((error) => setStatus(`読み込みに失敗しました: ${error.message}`, "error"));
