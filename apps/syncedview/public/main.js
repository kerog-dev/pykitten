const roomData = JSON.parse(
  document.querySelector("script[type=\"roomdata\"]").textContent.trim(),
);
const videoContainer = document.querySelector("#video-container");
const switchVideoYtForm = document.querySelector("#switch-video-yt-form");
let hasInteracted = false;

async function getVideoPath(roomName, attemptNum = 0) {
  try {
    const json = await (await fetch(`../room_video_path?name=${encodeURIComponent(roomName)}`)).json();
    if (!json.ok) throw "not ok: " + json.err;
    return json.path;
  } catch (e) {
    if (attemptNum >= 18) {
      alert("giving up auto re-load!");
      return "about:blank";
    }
    return new Promise(res => {
      setTimeout(() => {
        getVideoPath(roomName, attemptNum + 1).then(res);
      }, 10_000);
    });
  }
}

async function createVideo(roomName) {
  const video = document.createElement("video");
  video.src = await getVideoPath(roomName);
  video.controls = true;
  video.width = window.innerWidth;
  video.addEventListener("error", () => {
    setTimeout(() => {
      video.load();
    }, 3_000);
  });

  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

  let lastSend = {
    at: 0,
    time: null,
    paused: null,
  };

  const listener = async (e) => {
    await sleep(200);
    if (applyingRemote || isSeeking) return;
    const isRecent = Date.now() - lastSend.at < 1_000;
    const isTimeClose = video.currentTime - lastSend.time < 1.5;
    const switchedPause = video.paused !== lastSend.paused;
    console.log("is recent:", isRecent, "is time close:", isTimeClose, "switched pause:", switchedPause);
    if (isRecent && isTimeClose && !switchedPause) return;
    ws.send(`stateupdate ${video.currentTime} ${video.paused ? 1 : 0}`);
    lastSend = {
      at: Date.now(),
      time: video.currentTime,
      paused: video.paused,
    };
  };

  ["pause", "play", "seeked"].forEach((ev) => video.addEventListener(ev, listener));

  video.addEventListener("seeking", () => {
    isSeeking = true;
  });
  video.addEventListener("seeked", () => {
    isSeeking = false;
  });

  const setVideoEl = () => {
    videoContainer.innerHTML = "";
    videoContainer.appendChild(video);
  };
  if (!hasInteracted) {
    await new Promise(res => {
      const activateBtn = document.getElementById("activate");
      activateBtn.addEventListener("click", () => {
        setVideoEl();
        hasInteracted = true;
        res();
      }, { once: true });
    });
  } else setVideoEl();
  return video;
}

let video = await createVideo(roomData.name);
let applyingRemote = false;

const ws = new WebSocket("../ws/" + encodeURIComponent(roomData.name));

let isSeeking = false;
let curWatching = roomData.watching;

ws.addEventListener("message", async (e) => {
  if (isSeeking) return;
  const [cmd, ...args] = e.data.toString().split(" ");
  const argstr = args.join(" ");
  switch (cmd) {
    case "state":
      applyingRemote = true;
      const { watching, paused, time } = JSON.parse(argstr);
      if (JSON.stringify(watching) !== JSON.stringify(curWatching)) {
        console.log("watching changed! new:", watching);
        video.remove();
        video = await createVideo(
          roomData.name,
        );
      }
      video.currentTime = time;
      if (paused) video.pause();
      else video.play().catch(() => {});
      setTimeout(() => {
        applyingRemote = false;
      }, 1000);
      break;
  }
});

switchVideoYtForm.addEventListener("submit", (e) => {
  e.preventDefault();
  ws.send(`switchvideoyt ${e.target.elements.videoId.value} ${e.target.elements.quality.value}`);
});
