const versions = [];
for (let n = 0; n < 3; n++) {
  const version = editor.copy();
  for (let i = 0; i < n; i++) {
    for (let x = 0; x < editor.width; x++)
      for (let y = 0; y < editor.height; y++) {
        const org = version.get(x, y);
        version.set(x, y, { r: org.b, g: org.r, b: org.g });
      }
  }
  versions.push(version);
}

editor.fill();

const subwidth = editor.width / versions.length;
const subheight = editor.height / versions.length;

for (let i = 0; i < versions.length; i++) {
  const version = versions[i];
  editor.drawImage(version, subwidth * i, 0, subwidth, subheight);
}
