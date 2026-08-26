const PYODIDE_VERSION = "0.27.2";
const SCRIPT_NAMES = ["tl_common.py", "format_tl.py", "add_set_operations.py", "validate_tl.py", "review_tl.py"];

const input = document.querySelector("#input");
const output = document.querySelector("#output");
const formatButton = document.querySelector("#format");
const copyButton = document.querySelector("#copy-output");
const clearButton = document.querySelector("#clear-input");
const status = document.querySelector("#status");
const validation = document.querySelector("#validation");

let pyodidePromise;

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
        const source = await fetch(`scripts/${name}`).then((response) => {
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
  try {
    const pyodide = await loadPython();
    pyodide.globals.set("source_text", source);
    const result = await pyodide.runPythonAsync(`
import json
formatted = format_text(source_text)
report = []
set_text = add_operations(formatted, report=report)
errors = validate(set_text)
review = collect_review_items(set_text, formatted)
json.dumps({"text": set_text, "errors": errors, "review_count": len(review) }, ensure_ascii=False)
`);
    const data = JSON.parse(result);
    output.value = data.text;
    copyButton.disabled = false;
    if (data.errors.length) {
      validation.textContent = `検証エラー（${data.errors.length}件）\n${data.errors.join("\n")}`;
      validation.hidden = false;
      setStatus("整形完了・要確認", "error");
    } else {
      setStatus(`整形完了（レビュー対象 ${data.review_count}件）`, "ready");
    }
  } catch (error) {
    setStatus(`処理に失敗しました: ${error.message}`, "error");
  } finally {
    formatButton.disabled = false;
  }
}

formatButton.addEventListener("click", formatTL);
clearButton.addEventListener("click", () => {
  input.value = "";
  output.value = "";
  copyButton.disabled = true;
  validation.hidden = true;
  setStatus("準備完了", "ready");
});
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(output.value);
  copyButton.textContent = "コピーしました";
  setTimeout(() => { copyButton.textContent = "コピー"; }, 1400);
});

loadPython().then(() => setStatus("準備完了", "ready")).catch((error) => setStatus(`読み込みに失敗しました: ${error.message}`, "error"));
