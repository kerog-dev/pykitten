const roomData = JSON.parse(
  document.querySelector('script[type="roomdata"]').textContent.trim(),
);
const videoContainer = document.querySelector("#video-container");
const statusEl = document.querySelector("#status");

const video = document.createElement("video");
video.src = (
  await (
    await fetch("../room_video_path?name=" + encodeURIComponent(roomData.name))
  ).json()
).path;
video.controls = true;
videoContainer.appendChild(video);

let applyingRemote = false;

statusEl.textContent = "awaiting interaction";
await new Promise((res) => {
  document.addEventListener("click", () => res());
});
statusEl.textContent = "ok!";

const ws = new WebSocket("../ws/" + encodeURIComponent(roomData.name));

let isSeeking = false;

ws.addEventListener("message", async (e) => {
  if (isSeeking) return;
  const args = e.data.toString().split(" ");
  applyingRemote = true;
  const paused = args[0] === "True";
  const time = Number.parseFloat(args[1]);
  video.currentTime = time;
  if (paused) video.pause();
  else await video.play();
  setTimeout(() => {
    applyingRemote = false;
  }, 1000);
});

const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

const listener = async (e) => {
  await sleep(200);
  if (applyingRemote || isSeeking) return;
  ws.send(`${video.currentTime} ${video.paused ? 1 : 0}`);
};
["pause", "play", "seeked"].forEach((ev) =>
  video.addEventListener(ev, listener),
);

video.addEventListener("seeking", () => {
  isSeeking = true;
});
video.addEventListener("seeked", () => {
  isSeeking = false;
});
