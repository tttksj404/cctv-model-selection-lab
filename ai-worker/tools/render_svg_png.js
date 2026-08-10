#!/usr/bin/env node
"use strict";

const [sharpModule, inputPath, outputPath] = process.argv.slice(2);

if (!sharpModule || !inputPath || !outputPath) {
  console.error("usage: node render_svg_png.js <sharp-module> <input.svg> <output.png>");
  process.exit(2);
}

const sharp = require(sharpModule);

sharp(inputPath)
  .png()
  .toFile(outputPath)
  .then((info) => console.log(JSON.stringify(info)))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

