export class Editor {
  /** @type { ImageData } */
  #imageData;
  constructor(imageData) {
    if (!imageData || !(imageData instanceof ImageData))
      throw "bad input image data for editor";
    this.#imageData = imageData;
  }

  /** @returns {number} */
  get width() {
    return this.#imageData.width;
  }

  /** @returns {number} */
  get height() {
    return this.#imageData.height;
  }

  /**
   * @param {number} x
   * @param {number} y
   * @returns {{ r: number; g: number; b: number; a: number; }[]}
   */
  get(x, y) {
    const firstIndex = (y * this.#imageData.width + x) * 4;
    const pixelArr = this.#imageData.data.slice(firstIndex, firstIndex + 4);
    return {
      r: pixelArr[0],
      g: pixelArr[1],
      b: pixelArr[2],
      a: pixelArr[3],
    };
  }

  /**
   * @param {number} x
   * @param {number} y
   * @param {Partial<{ r: number; g: number; b: number; a: number; }>} updated
   */
  set(x, y, { r, g, b, a } = {}) {
    const baseIndex = (y * this.#imageData.width + x) * 4;
    if (r !== undefined) this.#imageData.data[baseIndex + 0] = r;
    if (g !== undefined) this.#imageData.data[baseIndex + 1] = g;
    if (b !== undefined) this.#imageData.data[baseIndex + 2] = b;
    if (a !== undefined) this.#imageData.data[baseIndex + 3] = a;
  }

  /** @returns {Editor} */
  copy() {
    const copied = new ImageData(
      new Uint8ClampedArray([...this.#imageData.data]),
      this.#imageData.width,
      this.#imageData.height,
    );
    return new Editor(copied);
  }

  /**
   * @param {Editor} src
   * @param {number} dx - destination x
   * @param {number} dy - destination y
   * @param {number} [dWidth]
   * @param {number} [dHeight]
   */
  drawImage(src, dx, dy, dWidth = src.width, dHeight = src.height) {
    for (let y = 0; y < dHeight; y++) {
      for (let x = 0; x < dWidth; x++) {
        const px = dx + x;
        const py = dy + y;

        // skip pixels outside destination bounds
        if (px < 0 || px >= this.width || py < 0 || py >= this.height) continue;

        // nearest-neighbor sample from source
        const sx = Math.floor((x / dWidth) * src.width);
        const sy = Math.floor((y / dHeight) * src.height);
        const s = src.get(sx, sy);

        if (s.a === 0) continue; // fully transparent, skip

        if (s.a === 255) {
          // fully opaque, just overwrite
          this.set(px, py, s);
        } else {
          // alpha composite (src-over)
          const d = this.get(px, py);
          const sa = s.a / 255;
          const da = d.a / 255;
          const oa = sa + da * (1 - sa);
          this.set(px, py, {
            r: Math.round((s.r * sa + d.r * da * (1 - sa)) / oa),
            g: Math.round((s.g * sa + d.g * da * (1 - sa)) / oa),
            b: Math.round((s.b * sa + d.b * da * (1 - sa)) / oa),
            a: Math.round(oa * 255),
          });
        }
      }
    }
  }

  newSolid(
    { r = 0, g = 0, b = 0, a = 255 } = {},
    width = this.#imageData.width,
    height = this.#imageData.height,
  ) {
    const arr = [];
    for (let pixI = 0; pixI < width * height; pixI++) {
      arr.push(r);
      arr.push(g);
      arr.push(b);
      arr.push(a);
    }
    const data = new ImageData(new Uint8ClampedArray(arr), width, height);
    return new Editor(data);
  }

  // /** @param {Editor} input */
  // assign(input) {
  //   this.#imageData = input.copy().#imageData;
  // }

  fill({ r = 0, g = 0, b = 0, a = 255 } = {}) {
    for (
      let pixI = 0;
      pixI < this.#imageData.width * this.#imageData.height;
      pixI++
    ) {
      this.#imageData.data[pixI * 4 + 0] = r;
      this.#imageData.data[pixI * 4 + 1] = g;
      this.#imageData.data[pixI * 4 + 2] = b;
      this.#imageData.data[pixI * 4 + 3] = a;
    }
  }
}
