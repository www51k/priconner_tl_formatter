const PYODIDE_VERSION = "0.27.2";
const SCRIPT_NAMES = ["character_aliases.py", "character_master.py", "tl_common.py", "format_tl.py", "add_set_operations.py", "validate_tl.py", "review_tl.py", "tl_merge.py"];

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
const addSetOperations = document.querySelector("#add-set-operations");
const mergeA = document.querySelector("#merge-a");
const mergeB = document.querySelector("#merge-b");
const mergeButton = document.querySelector("#merge");
const mergeStatus = document.querySelector("#merge-status");
const mergeOutput = document.querySelector("#merge-output");
const mergeEditor = document.querySelector("#merge-editor");
const battlePreview = document.querySelector("#battle-preview");
const formattedPreview = document.querySelector("#formatted-preview");
const mergeLane = document.querySelector("#merge-lane");
const FORMATION_CACHE_KEY = "priconner_tl_formatter.formation.v1";
const INPUT_CACHE_KEY = "priconner_tl_formatter.input.v1";
const OUTPUT_CACHE_KEY = "priconner_tl_formatter.output.v1";
const MERGE_CACHE_KEY = "priconner_tl_formatter.merge.v1";

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

function saveInputCache() {
  try {
    localStorage.setItem(INPUT_CACHE_KEY, input.value);
  } catch (_) {
    // 保存できない環境でも入力・整形処理は継続する。
  }
}

function restoreInputCache() {
  try {
    input.value = localStorage.getItem(INPUT_CACHE_KEY) || "";
  } catch (_) {
    // 保存データを利用できない場合は空欄から開始する。
  }
}

function saveOutputCache() {
  try {
    localStorage.setItem(OUTPUT_CACHE_KEY, output.textContent);
  } catch (_) {
    // 保存できない環境でも整形処理は継続する。
  }
}

function restoreOutputCache() {
  try {
    output.textContent = localStorage.getItem(OUTPUT_CACHE_KEY) || "";
    copyButton.disabled = !output.textContent;
  } catch (_) {
    // 保存データを利用できない場合は空欄から開始する。
  }
}

function saveMergeCache() {
  try {
    localStorage.setItem(MERGE_CACHE_KEY, JSON.stringify({
      battle: mergeA.value,
      formatted: mergeB.value,
      result: mergeOutput.value,
    }));
  } catch (_) {
    // 保存できない環境でもマージ処理は継続する。
  }
}

function renderSourceRows(container, value, draggable) {
  container.replaceChildren();
  if (!value) return;
  value.split("\n").forEach((line, index) => {
    appendInsertZone(container, index, draggable);
    const row = document.createElement("div");
    row.className = "merge-source-row";
    row.dataset.index = String(index);
    row.draggable = draggable;
    row.innerHTML = `<span class="merge-source-number">${index + 1}</span><span class="merge-source-text" role="gridcell"></span>${draggable ? '<span class="merge-source-handle" aria-hidden="true">⠿</span>' : ''}`;
    row.querySelector(".merge-source-text").textContent = line || " ";
    if (!draggable) {
      row.addEventListener("dragover", (event) => event.preventDefault());
      row.addEventListener("drop", (event) => {
        event.preventDefault();
        replaceBattleRow(Number(formattedPreview.dataset.dragIndex), index);
      });
    }
    if (draggable) {
      row.addEventListener("dragstart", () => {
        row.classList.add("dragging");
        formattedPreview.dataset.dragIndex = String(index);
      });
      row.addEventListener("dragend", () => row.classList.remove("dragging"));
      row.addEventListener("dragover", (event) => event.preventDefault());
      row.addEventListener("drop", (event) => {
        event.preventDefault();
        const from = Number(formattedPreview.dataset.dragIndex);
        const to = Number(row.dataset.index);
        moveFormattedRow(from, to);
      });
    }
    container.append(row);
  });
  appendInsertZone(container, value.split("\n").length, draggable);
}

function appendInsertZone(container, index, draggable) {
  const zone = document.createElement("div");
  zone.className = `merge-insert-zone${draggable ? "" : " merge-insert-zone-left"}`;
  zone.dataset.index = String(index);
  zone.textContent = draggable ? "＋ ここへ挿入" : "＋ 行を追加";
  zone.addEventListener("dragover", (event) => event.preventDefault());
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    if (draggable) moveFormattedRow(Number(formattedPreview.dataset.dragIndex), index);
    else insertFormattedIntoBattle(Number(formattedPreview.dataset.dragIndex), index);
  });
  if (!draggable) zone.addEventListener("click", () => insertBattleRow(index));
  container.append(zone);
}

function formattedLineAt(index) {
  const lines = mergeB.value.split("\n");
  return Number.isInteger(index) && index >= 0 && index < lines.length ? lines[index] : null;
}

function replaceBattleRow(formattedIndex, battleIndex) {
  const line = formattedLineAt(formattedIndex);
  const lines = mergeA.value.split("\n");
  if (line === null || !Number.isInteger(battleIndex) || battleIndex < 0 || battleIndex >= lines.length) return;
  lines[battleIndex] = line;
  mergeA.value = lines.join("\n");
  saveMergeCache();
  renderMergeSources();
}

function insertFormattedIntoBattle(formattedIndex, battleIndex) {
  const line = formattedLineAt(formattedIndex);
  const lines = mergeA.value.split("\n");
  if (line === null || !Number.isInteger(battleIndex)) return;
  lines.splice(Math.max(0, Math.min(battleIndex, lines.length)), 0, line);
  mergeA.value = lines.join("\n");
  saveMergeCache();
  renderMergeSources();
}

function insertBattleRow(index) {
  const lines = mergeA.value.split("\n");
  lines.splice(index, 0, "");
  mergeA.value = lines.join("\n");
  saveMergeCache();
  renderMergeSources();
  mergeA.focus();
  const position = lines.slice(0, index + 1).join("\n").length;
  mergeA.setSelectionRange(position, position);
}

function moveFormattedRow(from, target) {
  const lines = mergeB.value.split("\n");
  if (!Number.isInteger(from) || !Number.isInteger(target) || from < 0 || from >= lines.length) return;
  const [moved] = lines.splice(from, 1);
  const destination = target > from ? target - 1 : target;
  if (destination === from) return;
  lines.splice(Math.max(0, Math.min(destination, lines.length)), 0, moved);
  mergeB.value = lines.join("\n");
  saveMergeCache();
  renderMergeSources();
}

function syncSourceRowHeights() {
  const left = [...battlePreview.querySelectorAll(".merge-source-row")];
  const right = [...formattedPreview.querySelectorAll(".merge-source-row")];
  const count = Math.max(left.length, right.length);
  for (let index = 0; index < count; index += 1) {
    const height = Math.max(left[index]?.offsetHeight || 0, right[index]?.offsetHeight || 0);
    if (left[index]) left[index].style.minHeight = `${height}px`;
    if (right[index]) right[index].style.minHeight = `${height}px`;
  }
}

function renderMergeSources() {
  renderSourceRows(battlePreview, mergeA.value, false);
  renderSourceRows(formattedPreview, mergeB.value, true);
  requestAnimationFrame(syncSourceRowHeights);
  renderMergeLane();
}

function renderMergeLane() {
  mergeLane.replaceChildren();
  const battle = mergeA.value.split("\n");
  const source = mergeB.value.split("\n");
  const key = (line) => {
    const time = line.match(/(\d{1,2}):(\d{2})/);
    if (!time) return null;
    const name = line.replace(/^.*?\d{1,2}:\d{2}/, "").trim().split(/[　 \[（(]/, 1)[0];
    return `${Number(time[1]) * 60 + Number(time[2])}:${name}`;
  };
  const formattedByKey = new Map();
  source.forEach((line, index) => { const value = key(line); if (value) formattedByKey.set(value, { line, index }); });
  const matched = new Set();
  const title = document.createElement("div");
  title.className = "merge-lane-title";
  title.textContent = "整形済みTLの行を下のバトルTL行へドラッグ";
  mergeLane.append(title);
  const unmatched = document.createElement("div");
  unmatched.className = "merge-lane-pool merge-lane-unmatched";
  source.forEach((line, index) => {
    const card = document.createElement("div");
    card.className = "merge-lane-card formatted-card";
    card.draggable = true;
    card.dataset.index = String(index);
    card.textContent = line || " ";
    card.addEventListener("dragstart", () => { mergeLane.dataset.dragIndex = String(index); card.classList.add("dragging"); });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
    const value = key(line);
    card.hidden = Boolean(value && battle.some((battleLine) => key(battleLine) === value));
    if (!card.hidden) unmatched.append(card);
  });
  const timeline = document.createElement("div");
  timeline.className = "merge-lane-timeline";
  battle.forEach((line, index) => {
    const row = document.createElement("div");
    row.className = "merge-lane-row";
    row.innerHTML = `<span class="merge-source-number">${index + 1}</span><span class="merge-lane-text"></span>`;
    row.querySelector(".merge-lane-text").textContent = line || " ";
    const formatted = formattedByKey.get(key(line));
    if (formatted) {
      matched.add(formatted.index);
      const detail = document.createElement("span");
      detail.className = "merge-lane-match";
      detail.textContent = `整形済み: ${formatted.line}`;
      row.append(detail);
    }
    row.addEventListener("dragover", (event) => event.preventDefault());
    row.addEventListener("drop", (event) => { event.preventDefault(); replaceBattleRow(Number(mergeLane.dataset.dragIndex), index); });
    timeline.append(row);
    const insert = document.createElement("div");
    insert.className = "merge-lane-insert";
    insert.textContent = "＋ ここへ挿入";
    insert.addEventListener("dragover", (event) => event.preventDefault());
    insert.addEventListener("drop", (event) => { event.preventDefault(); insertFormattedIntoBattle(Number(mergeLane.dataset.dragIndex), index + 1); });
    timeline.append(insert);
  });
  mergeLane.append(timeline);
  if (unmatched.children.length) {
    const label = document.createElement("div");
    label.className = "merge-lane-unmatched-title";
    label.textContent = "未対応の整形済みTL（挿入候補）";
    mergeLane.append(label, unmatched);
  }
}

battlePreview.addEventListener("scroll", () => { formattedPreview.scrollTop = battlePreview.scrollTop; });
formattedPreview.addEventListener("scroll", () => { battlePreview.scrollTop = formattedPreview.scrollTop; });

function restoreMergeCache() {
  try {
    const data = JSON.parse(localStorage.getItem(MERGE_CACHE_KEY) || "null");
    if (!data || typeof data !== "object") return;
    mergeA.value = typeof data.battle === "string" ? data.battle : "";
    mergeB.value = typeof data.formatted === "string" ? data.formatted : "";
    mergeOutput.value = typeof data.result === "string" ? data.result : "";
    renderMergeSources();
    renderMergeEditor();
  } catch (_) {
    // 保存データが壊れていても空欄から開始する。
  }
}

function renderMergeEditor() {
  mergeEditor.replaceChildren();
  const lines = mergeOutput.value.split("\n");
  if (!mergeOutput.value) return;
  lines.forEach((line, index) => {
    const row = document.createElement("div");
    row.className = "merge-editor-row";
    row.draggable = true;
    row.dataset.index = String(index);
    row.innerHTML = `<span class="merge-editor-handle" aria-hidden="true">⠿</span><span class="merge-editor-number">${index + 1}</span><span class="merge-editor-text"></span>`;
    row.querySelector(".merge-editor-text").textContent = line || " ";
    row.addEventListener("dragstart", () => {
      row.classList.add("dragging");
      mergeEditor.dataset.dragIndex = String(index);
    });
    row.addEventListener("dragend", () => row.classList.remove("dragging"));
    row.addEventListener("dragover", (event) => event.preventDefault());
    row.addEventListener("drop", (event) => {
      event.preventDefault();
      const from = Number(mergeEditor.dataset.dragIndex);
      const to = Number(row.dataset.index);
      if (!Number.isInteger(from) || from === to) return;
      const reordered = [...mergeOutput.value.split("\n")];
      const [moved] = reordered.splice(from, 1);
      reordered.splice(to, 0, moved);
      mergeOutput.value = reordered.join("\n");
      saveMergeCache();
      renderMergeEditor();
    });
    mergeEditor.append(row);
  });
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
      .replace(/^(?:⭐️|⭐︎|⭐|★|☆|🔺|△)\s*/, "")
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
  if (!addSetOperations.checked) {
    diagnosis.innerHTML = "判定：<strong>書式整形のみ</strong>（SET操作追加OFF）";
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
  if (lines[0]?.trim().startsWith("[") && (lines[0].includes("(5)") || /\[[O〇○◯X×－ー＿-]{5}\]/.test(lines[0]))) {
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
        const source = await fetch(`scripts/${name}?v=20260913-merge-8`).then((response) => {
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
from tl_merge import parse_events, merge_events, merge_texts
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
    const header = addSetOperations.checked && !formationPanel.hidden ? formationHeader() : null;
    const sourceWithFormation = applyFormation(source, header);
    const pyodide = await loadPython();
    pyodide.globals.set("source_text", sourceWithFormation);
    pyodide.globals.set("carryover_seconds", Number(carryoverTime.value));
    pyodide.globals.set("add_set_operations", addSetOperations.checked);
    const result = await pyodide.runPythonAsync(`
import json
formatted = format_text(source_text, carryover_seconds=carryover_seconds)
report = []
set_text = add_operations(formatted, report=report) if add_set_operations and carryover_seconds >= 90 else formatted
errors = validate(set_text) if add_set_operations and carryover_seconds >= 90 else []
review_items = collect_review_items(set_text, formatted)
error_details = []
for error in errors:
    line_number = int(error.split(":", 1)[0])
    target_line = set_text.splitlines()[line_number - 1] if line_number > 0 else ""
    error_details.append(f"{error}\\n対象行: {target_line}")
json.dumps({"text": set_text, "errors": errors, "error_details": error_details, "review": review_items }, ensure_ascii=False)
`);
    const data = JSON.parse(result);
    output.textContent = addSetOperations.checked && Number(carryoverTime.value) >= 90
      ? ensureInitialSet(data.text)
      : data.text;
    mergeB.value = output.textContent;
    saveOutputCache();
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
  saveInputCache();
  autofillFormation(input.value);
  diagnoseTL(input.value);
});
addSetOperations.addEventListener("change", () => {
  if (addSetOperations.checked) autofillFormation(input.value);
  diagnoseTL(input.value);
});
clearButton.addEventListener("click", () => {
  input.value = "";
  saveInputCache();
  output.textContent = "";
  saveOutputCache();
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

mergeA.addEventListener("input", saveMergeCache);
mergeA.addEventListener("input", renderMergeSources);
mergeB.addEventListener("input", saveMergeCache);
mergeB.addEventListener("input", renderMergeSources);

mergeButton.addEventListener("click", async () => {
  if (!mergeA.value.trim() || !mergeB.value.trim()) {
    mergeStatus.textContent = "TL AとTL Bを入力してください";
    mergeStatus.className = "status error";
    return;
  }
  try {
    const formation = [...formationList.querySelectorAll("input")].map((field) => field.value.trim()).filter(Boolean);
    if (formation.length !== 5) throw new Error("編成を5人入力してください");
    mergeButton.disabled = true;
    const pyodide = await loadPython();
    pyodide.globals.set("merge_text_a", mergeA.value);
    pyodide.globals.set("merge_text_b", mergeB.value);
    pyodide.globals.set("merge_formation", formation);
    const result = await pyodide.runPythonAsync(`
import json
merged = merge_texts(merge_text_a, merge_text_b, merge_formation)
json.dumps(merged, ensure_ascii=False)
`);
    const data = JSON.parse(result);
    mergeOutput.value = data.text;
    saveMergeCache();
    renderMergeEditor();
    mergeStatus.textContent = data.unresolved.length ? `マージ完了・要確認（${data.unresolved.join("、")}）` : "マージ完了";
    mergeStatus.className = "status ready";
  } catch (error) {
    mergeStatus.textContent = error.message;
    mergeStatus.className = "status error";
  } finally {
    mergeButton.disabled = false;
  }
});

restoreFormationCache();
restoreInputCache();
restoreOutputCache();
restoreMergeCache();
autofillFormation(input.value);
diagnoseTL(input.value);
loadPython().then(() => setStatus("準備完了", "ready")).catch((error) => setStatus(`読み込みに失敗しました: ${error.message}`, "error"));
