#!/usr/bin/env node
"use strict";

const sharp = require(process.argv[2]);
const input = process.argv[3];
const output = process.argv[4];

if (!input || !output) {
  throw new Error("usage: node clean_presentation_rasters.cjs <sharp> <input> <output>");
}

const isPaleBlue = (r, g, b) => r > 225 && g > 230 && b > 235 && b - r > 3 && b - g > 1;
// Catch both saturated blue accents and dark navy anti-aliased annotation text.
// Red/orange and green chart series do not satisfy both channel deltas.
const isBlue = (r, g, b) => b > r + 10 && b > g + 4;

const main = async () => {
  const { data, info } = await sharp(input).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let index = 0; index < data.length; index += 4) {
    const r = data[index];
    const g = data[index + 1];
    const b = data[index + 2];
    if (isPaleBlue(r, g, b)) {
      data[index] = 255;
      data[index + 1] = 255;
      data[index + 2] = 255;
    } else if (isBlue(r, g, b)) {
      const luminance = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
      const gray = luminance > 175 ? 145 : luminance > 120 ? 86 : 42;
      data[index] = gray;
      data[index + 1] = gray;
      data[index + 2] = gray;
    }
  }
  await sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } }).png().toFile(output);
  console.log(JSON.stringify({ output, width: info.width, height: info.height }));
};

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

