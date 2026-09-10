/* Mock camera frame (1280x720): neutral board, 1 cm dot grid, six leaf blobs at known centres.
   Used by PreviewStage when MOCK is on (no MJPEG stream available on GitHub Pages). */

export const MOCK_PREVIEW_SIZE: [number, number] = [1280, 720]

/** Blob centres in preview pixels — a 3x2 grid matching config rois from `grid_rois(4608,2592,3,2)` scaled by 1280/4608. */
export const MOCK_BLOBS: { cx: number; cy: number; r: number }[] = (() => {
  const scale = 1280 / 4608
  const mx = Math.floor(4608 * 0.04), my = Math.floor(2592 * 0.04)
  const cw = Math.floor((4608 - 2 * mx) / 3), ch = Math.floor((2592 - 2 * my) / 2)
  const side = Math.floor(Math.min(cw, ch) * 0.92)
  const out: { cx: number; cy: number; r: number }[] = []
  for (let r = 0; r < 2; r++) for (let c = 0; c < 3; c++) {
    out.push({ cx: (mx + cw * c + Math.floor(cw / 2)) * scale, cy: (my + ch * r + Math.floor(ch / 2)) * scale, r: side * scale * 0.22 })
  }
  return out
})()

function svg(): string {
  const [w, h] = MOCK_PREVIEW_SIZE
  const step = w / 62                                  // ~1 cm at a 62 cm frame
  let dots = ''
  for (let x = step / 2; x < w; x += step) for (let y = step / 2; y < h; y += step) dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="1" fill="#5a6068"/>`
  const leaves = MOCK_BLOBS.map((b, i) => {
    const lobes = [0, 72, 144, 216, 288].map((a) => {
      const rad = ((a + 15 * i) * Math.PI) / 180
      return `<ellipse cx="${(b.cx + b.r * 0.85 * Math.cos(rad)).toFixed(1)}" cy="${(b.cy + b.r * 0.8 * Math.sin(rad)).toFixed(1)}" rx="${(b.r * 0.5).toFixed(1)}" ry="${(b.r * 0.3).toFixed(1)}" transform="rotate(${a + 15 * i} ${(b.cx + b.r * 0.85 * Math.cos(rad)).toFixed(1)} ${(b.cy + b.r * 0.8 * Math.sin(rad)).toFixed(1)})" fill="#46a046"/>`
    }).join('')
    return `<ellipse cx="${b.cx.toFixed(1)}" cy="${b.cy.toFixed(1)}" rx="${(b.r * 1.2).toFixed(1)}" ry="${(b.r * 0.95).toFixed(1)}" fill="#4aa64a"/>${lobes}`
  }).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="${w}" height="${h}" fill="#8e8a84"/>${dots}${leaves}<text x="12" y="36" font-family="monospace" font-size="24" fill="#c8402c">MOCK CAMERA</text></svg>`
}

export const MOCK_PREVIEW_SRC = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg())}`
