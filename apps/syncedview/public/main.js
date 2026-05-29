const roomDataText = document
  .querySelector('script[type="roomdata"]')
  .textContent.trim();
console.log(roomDataText);
const roomData = JSON.parse(roomDataText);
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

/**
 * NOTE: started at is a python unix epoch (seconds)
 * @param {boolean} paused
 * @param {number} baseTime
 * @param {number} startedAt
 * @returns {number} Seconds into the video
 */
function getTime(paused, baseTime, startedAt) {
  if (paused) return baseTime;
  const timePassed = Date.now() / 1000 - startedAt;
  return baseTime + timePassed;
}

let curState = {};
let suppressNextSeek = false;
let applyingRemote = false;

statusEl.textContent = "awaiting interaction";
await new Promise((res) => {
  document.addEventListener("click", () => res());
});
statusEl.textContent = "ok!";

const ws = new WebSocket("../ws/" + encodeURIComponent(roomData.name));

ws.addEventListener("message", (e) => {
  const [cmd, ...args] = e.data.toString().split(" ");
  console.log("ws message received", [cmd, ...args]);
  if (cmd === "timeupdate") {
    const paused = args[0] === "1";
    const baseTime = Number.parseFloat(args[1]);
    const startedAt = Number.parseFloat(args[2]);
    const isLocalOrigin = args[3] === "1";

    if (!isLocalOrigin) {
      suppressNextSeek = true;
      applyingRemote = true;
      video.currentTime = getTime(paused, baseTime, startedAt);
      if (paused) video.pause();
      else video.play();
      queueMicrotask(() => {
        applyingRemote = false;
      });
    }
    curState = { paused, baseTime, startedAt };
  }
});

setInterval(() => {
  console.log(curState);
  const { paused, baseTime, startedAt } = curState;
  const seekTo = getTime(paused, baseTime, startedAt);
  if (Math.abs(seekTo - video.currentTime) > 1) {
    suppressNextSeek = true;
    video.currentTime = seekTo;
  }
}, 5000);

const listener = (isSeekHandler) => {
  return (e) => {
    e.preventDefault();
    if ((isSeekHandler && suppressNextSeek) || applyingRemote) {
      suppressNextSeek = false;
      return false;
    }
    console.log("sending");
    if (!applyingRemote)
      ws.send(`timeupdate ${video.paused ? "1" : "0"} ${video.currentTime}`);
    return false;
  };
};

video.addEventListener("pause", listener(false));
video.addEventListener("play", listener(false));
video.addEventListener("seeked", listener(true));
// video.addEventListener("timeupdate", listener(false));
