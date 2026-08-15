// Generates PWA PNG icons from an inline SVG source using sharp.
import sharp from "sharp";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = resolve(__dirname, "..", "public");
mkdirSync(publicDir, { recursive: true });

const shield = (stroke) => `
  <path d="M256 60 L410 120 V276 C410 372 342 434 256 470 C170 434 102 372 102 276 V120 Z"
        fill="none" stroke="${stroke}" stroke-width="26" stroke-linejoin="round"/>
  <path d="M196 258 l44 44 l84 -100" fill="none" stroke="${stroke}" stroke-width="26"
        stroke-linecap="round" stroke-linejoin="round"/>`;

const svg = (bg, padded) => `
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#22d3ee"/>
      <stop offset="1" stop-color="#3b82f6"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="${padded ? 0 : 96}" fill="${bg}"/>
  <g transform="${padded ? "translate(51,51) scale(0.8)" : ""}">${shield("url(#g)")}</g>
</svg>`;

async function png(source, size, out) {
  await sharp(Buffer.from(source)).resize(size, size).png().toFile(resolve(publicDir, out));
  console.log("wrote", out);
}

await png(svg("#0a0e14", false), 192, "pwa-192.png");
await png(svg("#0a0e14", false), 512, "pwa-512.png");
await png(svg("#0a0e14", true), 512, "pwa-maskable-512.png");
await png(svg("#0a0e14", false), 180, "apple-touch-icon.png");
