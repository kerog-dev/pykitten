import { Editor } from "./editor.js";

const inputEl = document.getElementById("input");
const outputEl = document.getElementById("output");
const codeEl = document.getElementById("code");
const runEl = document.getElementById("run");
const logEl = document.getElementById("log");

/** @type {File} */
let file = inputEl.files[0];

inputEl.addEventListener("change", (e) => {
  file = e.target.files[0];
});

runEl.addEventListener("click", () => {
  run();
});

window.addEventListener("message", async ({ data }) => {
  if (data.type === "log") {
    logEl.textContent += data.message + "\n";
  } else if (data.type === "result")
    if (data.ok) {
      const resultData = new ImageData(
        new Uint8ClampedArray(data.buffer),
        data.width,
        data.height,
      );

      const resultCanvas = new OffscreenCanvas(
        resultData.width,
        resultData.height,
      );
      const ctx = resultCanvas.getContext("2d");
      ctx.putImageData(resultData, 0, 0);
      const url = URL.createObjectURL(await resultCanvas.convertToBlob());
      outputEl.src = url;
    } else {
      alert(`error in your script: ${data.error}`);
    }
});

async function run() {
  if (!file) {
    alert("error: no file selected");
    return;
  }
  logEl.textContent = "";
  const imageData = await (async () => {
    const bmp = await createImageBitmap(file);
    const canvas = new OffscreenCanvas(bmp.width, bmp.height);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(bmp, 0, 0);
    return ctx.getImageData(0, 0, canvas.width, canvas.height);
  })();
  const iframeHTML = `
    <!doctype html>
    <html>
      <head>
      </head>
      <body>
        <script>
          'use strict';
          ${Editor}
          const __user_fn = (async (editor, log) => { ${codeEl.value} })
          function __log(...args) {
            parent.postMessage({ type: 'log', message: args.join(' ') }, '*');
          }
          async function __run(editor, imageData) {
            try {
              await __user_fn(editor, __log);
              const out = imageData.data.buffer;
              parent.postMessage({ type: 'result', ok: true, buffer: out, width: imageData.width, height: imageData.height }, '*', [out]);
            } catch (e) {
              parent.postMessage({ type: 'result', ok: false, error: e.message }, '*');
            }
          }
          window.onmessage = async ({ data }) => {
            const imageData = new ImageData(
              new Uint8ClampedArray(data.buffer), data.width, data.height
            );
            const editor = new Editor(imageData);
            __run(editor, imageData);
          };
        </script>
      </body>
    </html>
`;
  const iframeBlob = new Blob([iframeHTML], { type: "text/html" });
  const url = URL.createObjectURL(iframeBlob);
  const iframe = document.createElement("iframe");
  iframe.sandbox = "allow-scripts";
  iframe.style.display = "none";
  iframe.src = url;
  setTimeout(() => {
    iframe.remove();
    URL.revokeObjectURL(url);
  }, 25_000);
  document.body.appendChild(iframe);
  iframe.addEventListener("load", () => {
    const buf = imageData.data.buffer.slice(0);
    iframe.contentWindow.postMessage(
      { buffer: buf, width: imageData.width, height: imageData.height },
      "*",
      [buf],
    );
  });
}
