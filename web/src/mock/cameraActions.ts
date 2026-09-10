/* camera/setup_actions.py ported: every action mutates the config store and returns {msg, status}. */
import { ApiError } from '@/api/client'
import type { ActionResult, Roi } from '@/api/types'
import { CAP, SCALE, gridRois } from './fixtures/config'
import { broadcast } from './live'
import { MOCK_BLOBS } from './preview'
import { addEvent, bumpConfig, cameraStatus, stepDone, type MockState } from './state'
import { Rng } from './synth'

type Body = Record<string, unknown>
const num = (b: Body, k: string, d = 0) => (typeof b[k] === 'number' ? (b[k] as number) : Number(b[k] ?? d) || d)
const g = (v: number) => Number(v.toFixed(2)).toString()

export function runAction(st: MockState, name: string, body: Body): ActionResult {
  const fn = ACTIONS[name]
  if (!fn) throw new ApiError(404, 'unknown_action', `no action '${name}'`)
  let msg: string
  if (!['open', 'close', 'save'].includes(name) && st.cam.opsBusy === 'job') msg = '⚠ capture in progress — setup actions are locked until it finishes'
  else msg = fn(st, body)
  st.setup.level = msg.includes('⚠') ? 'warn' : /완료|저장|기록/.test(msg) ? 'good' : 'info'
  st.setup.msg = msg
  addEvent(st, `setup.${name}`, { msg })
  const status = cameraStatus(st)
  broadcast('camera.setup', { action: name, msg, done: stepDone(st) })
  return { msg, status }
}

const ACTIONS: Record<string, (st: MockState, p: Body) => string> = {
  open(st) { st.cam.state = 'open'; st.cam.clients = 1; broadcast('camera.state', { state: 'open' }); return '카메라 열림' },
  close(st) { st.cam.state = 'closed'; st.cam.clients = 0; broadcast('camera.state', { state: 'closed' }); return '카메라 닫음 — 예약 촬영이 쓸 수 있습니다' },
  save(st) { bumpConfig(st); return '현재 설정을 다시 저장했습니다' },

  auto(st) {
    const r = new Rng(Date.now() & 0xffff)
    const vals = { exposure_us: Math.round(r.uniform(17000, 21000) / 100) * 100, gain: Number(r.uniform(1.6, 2.4).toFixed(2)), colour_gains: [Number(r.uniform(1.8, 2.0).toFixed(2)), Number(r.uniform(1.5, 1.65).toFixed(2))] as [number, number], lens_position: Number(r.uniform(1.75, 1.9).toFixed(2)) }
    st.setup.lastAuto = vals
    bumpConfig(st, (c) => { c.capture = { ...c.capture, ...vals } })
    const warn = vals.gain > 4 ? `  ⚠ gain ${vals.gain.toFixed(1)} 은 높습니다 — 조명을 밝게 하고 다시 측정하세요(노이즈)` : vals.gain > 2 ? '  · 조명을 더 밝게 하면 노이즈가 줄어듭니다' : ''
    return `exp ${vals.exposure_us} · gain ${vals.gain.toFixed(2)} · WB ${vals.colour_gains[0].toFixed(2)}/${vals.colour_gains[1].toFixed(2)} · lens ${vals.lens_position.toFixed(2)}  — 고정·저장 완료${warn}`
  },

  point(st, p) {
    const x = num(p, 'x'), y = num(p, 'y'), cm = num(p, 'cm', st.setup.cm || 10)
    const pts = st.setup.pts.length < 2 ? st.setup.pts : []
    pts.push([x, y])
    st.setup.pts = pts
    st.setup.cm = cm
    if (pts.length < 2) return '첫 점 찍음 — 반대쪽 끝을 한 번 더 클릭하세요'
    const dPrev = Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]), dCap = dPrev / SCALE
    if (cm <= 0 || dCap <= 0) return '길이가 0입니다'
    const ppc = dCap / cm
    st.setup.ppcFixed = ppc
    bumpConfig(st, (c) => { c.qc.px_per_cm_ref = Math.round(ppc * 10) / 10 })
    const frameCm = CAP[0] / ppc, lay = st.cfg.layout, need = lay.cols * lay.pot_cm + (lay.cols - 1) * lay.gap_cm
    let warn = ''
    if (lay.pot_cm && frameCm < need) warn = `   ⚠ 프레임 폭 ${frameCm.toFixed(0)}cm 가 배치 ${need.toFixed(0)}cm 보다 좁습니다 — 다시 재세요`
    else if (lay.pot_cm && frameCm > need * 3) warn = `   ⚠ 프레임 폭 ${frameCm.toFixed(0)}cm 는 배치 ${need.toFixed(0)}cm 의 3배가 넘습니다 — 길이 입력칸을 확인하세요`
    return `${dCap.toFixed(0)}px(원본) / ${g(cm)}cm  ->  ${ppc.toFixed(1)} px/cm  · 프레임 폭 ${frameCm.toFixed(0)}cm · 기록${warn}`
  },
  clearpoints(st) { st.setup.pts = []; return '배율 측정점 초기화' },
  setpot(st, p) {
    const cm = num(p, 'pot_cm')
    if (cm <= 0) return '0보다 큰 값을 넣으세요'
    bumpConfig(st, (c) => { c.layout.pot_cm = cm })
    return `화분 지름 ${g(cm)} cm 기록 — 배율 검산에 쓰입니다`
  },
  shoot(st) {
    st.calibExists = true
    st.calibMtime = Math.floor(Date.now() / 1000)
    return `calib.jpg 저장 (${CAP[0]}x${CAP[1]}) — 완료`
  },

  findleaf(st) {
    const blobs = MOCK_BLOBS.map((b) => ({ cx: b.cx, cy: b.cy, w: b.r * 2.7, h: b.r * 2.7 }))
    const existing = st.cfg.rois
    const sides = new Set(existing.map((r) => `${r.w}x${r.h}`))
    const keep = existing.length && sides.size === 1 && existing[0].w === existing[0].h ? existing[0].w : null
    let side = keep ? keep * SCALE : Math.max(...blobs.map((b) => Math.max(b.w, b.h))) * 1.8
    let how = keep ? `기존 크기 ${keep}px 유지` : '새 크기(가장 큰 잎 기준) · 전부 동일'
    const mk = (s: number) => blobs.map((b) => [b.cx - s / 2, b.cy - s / 2, s, s] as const)
    let boxes = mk(side), shrunk = false
    for (let i = 0; i < 12; i++) {
      const over = boxes.some((a, ai) => boxes.slice(ai + 1).some((c) => Math.min(a[0] + a[2], c[0] + c[2]) - Math.max(a[0], c[0]) > 0 && Math.min(a[1] + a[3], c[1] + c[3]) - Math.max(a[1], c[1]) > 0))
      if (!over) break
      side *= 0.9; boxes = mk(side); shrunk = true
    }
    if (shrunk) how += ' (겹쳐서 축소)'
    const rois: Roi[] = boxes.map(([x, y, w, h], i) => {
      const W = Math.min(Math.round(w / SCALE), CAP[0]), H = Math.min(Math.round(h / SCALE), CAP[1])
      const X = Math.max(0, Math.min(Math.round(x / SCALE), CAP[0] - W)), Y = Math.max(0, Math.min(Math.round(y / SCALE), CAP[1] - H))
      const prev = existing[i]
      return { plant_id: prev?.plant_id ?? `p${i + 1}`, treat: existing.length === blobs.length ? prev.treat : '', x: X, y: Y, w: W, h: H }
    })
    const kept = rois.some((r) => r.treat)
    bumpConfig(st, (c) => { c.rois = rois })
    return `잎 ${rois.length}개 — 중심만 이동 · ${how} · 크기 ${new Set(rois.map((r) => r.w)).size === 1 ? '모두 같음' : '★ 다름'} · ${kept ? '처리군 유지됨' : '처리군이 비었습니다 — 다시 배정하세요'} · 저장`
  },
  autoroi(st, p) {
    const cols = num(p, 'cols', st.cfg.layout.cols), rows = num(p, 'rows', st.cfg.layout.rows)
    const rois = gridRois(CAP[0], CAP[1], cols, rows)
    bumpConfig(st, (c) => { c.rois = rois; c.layout.cols = cols; c.layout.rows = rows })
    return `${cols}x${rows} 격자 = ${rois.length}칸 — 처리군은 아직 비어 있습니다 · 저장`
  },

  rename(st) {
    const n = st.cfg.rois.length
    if (!n) return 'ROI 가 없습니다 — 먼저 배치하세요'
    st.setup.order = []
    return `이름을 붙일 순서대로 화면의 박스를 클릭하세요 (0/${n})`
  },
  cancel_naming(st) { st.setup.order = null; return '이름 지정 취소' },
  pickroi(st, p) {
    const order = st.setup.order
    if (order === null) return '먼저 [이름 다시 매기기] 를 누르세요'
    const X = num(p, 'x') / SCALE, Y = num(p, 'y') / SCALE, rois = st.cfg.rois
    const i = rois.findIndex((r) => r.x <= X && X <= r.x + r.w && r.y <= Y && Y <= r.y + r.h)
    if (i < 0) return '박스 안을 클릭하세요'
    if (order.includes(i)) return '이미 고른 박스입니다'
    order.push(i)
    if (order.length < rois.length) return `${order.length}/${rois.length} — 다음 박스를 클릭하세요`
    const renamed = order.map((idx, k) => ({ ...rois[idx], plant_id: `p${k + 1}` }))
    st.setup.order = null
    bumpConfig(st, (c) => { c.rois = renamed })
    return '이름 지정 완료 — ' + renamed.map((r) => `${r.plant_id}(x=${r.x})`).join(' · ')
  },

  settreat(st, p) {
    const pid = String(p.pid), treat = String(p.treat)
    if (treat !== 'stable' && treat !== 'fluct') return `알 수 없는 처리군: ${treat}`
    if (!st.cfg.rois.some((r) => r.plant_id === pid)) return `${pid} 를 찾을 수 없습니다`
    bumpConfig(st, (c) => { c.rois.forEach((r) => { if (r.plant_id === pid) r.treat = treat }); c.treat_mode = 'manual' })
    return `${pid} → ${treat} (직접 지정) · 저장`
  },
  shuffle(st, p) {
    const n = st.cfg.rois.length
    if (!n) return 'ROI 가 없습니다'
    if (n % 2) return `ROI 가 ${n}개(홀수)라 반씩 나눌 수 없습니다`
    const labels = [...Array<string>(n / 2).fill('stable'), ...Array<string>(n / 2).fill('fluct')]
    const r = new Rng(typeof p.seed === 'number' ? p.seed : Date.now() & 0xffffff)
    for (let i = labels.length - 1; i > 0; i--) { const j = Math.floor(r.next() * (i + 1)); [labels[i], labels[j]] = [labels[j], labels[i]] }
    bumpConfig(st, (c) => { c.rois.forEach((roi, i) => { roi.treat = labels[i] }); c.treat_mode = 'random' })
    return '무작위 배정 완료 — ' + st.cfg.rois.map((roi) => `${roi.plant_id}:${roi.treat[0]}`).join(' ')
  },
  centerroi(st, p) {
    if (!st.calibExists) return '사진이 없습니다 — 먼저 [촬영] 하세요'
    if (!st.cfg.rois.length) return 'ROI 가 없습니다'
    if (!p.apply) return '제안 2개 이동 (미적용) — /api/images/data/roi_offset.jpg 에서 확인'
    return 'ROI 재중심 적용 — 2개 이동 · 크기 불변 · 저장'
  },
}
