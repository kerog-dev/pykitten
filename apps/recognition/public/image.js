import { pipeline, env } from "/transformers.js";

env.allowLocalModels = true;
env.allowRemoteModels = false;
env.localModelPath = "/aimodels/";

const input = document.getElementById("input");
const canvas = document.getElementById("canvas");

const ctx = canvas.getContext("2d");

console.log("Loading model...");
const detector = await pipeline("object-detection", "detr-resnet-50");
console.log("Model loaded");

input.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const img = new Image();

  img.onload = async () => {
    // Clear canvas
    ctx.clearRect(0, 0, 800, 800);

    // Resize image to exactly 800x800
    ctx.drawImage(
      img,
      0,
      0,
      img.naturalWidth,
      img.naturalHeight,
      0,
      0,
      800,
      800,
    );

    console.log("Running detection...");

    const detections = await detector(canvas, {
      threshold: 0.7,
    });

    console.log(detections);

    // Draw boxes
    ctx.lineWidth = 3;
    ctx.font = "16px sans-serif";

    for (const detection of detections) {
      const { xmin, ymin, xmax, ymax } = detection.box;

      const width = xmax - xmin;
      const height = ymax - ymin;

      ctx.strokeStyle = "#ff0000";
      ctx.strokeRect(xmin, ymin, width, height);

      const label = `${detection.label} ${(detection.score * 100).toFixed(1)}%`;

      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = "#ff0000";
      ctx.fillRect(xmin, Math.max(0, ymin - 22), textWidth + 8, 22);

      ctx.fillStyle = "#ffffff";
      ctx.fillText(label, xmin + 4, Math.max(16, ymin - 6));
    }
  };

  img.src = URL.createObjectURL(file);
});
