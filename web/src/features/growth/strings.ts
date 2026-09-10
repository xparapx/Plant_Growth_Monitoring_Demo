/** Extra copy local to the growth page (ko.ts is shared and not edited here). */
export const G = {
  seriesSub: '새벽(dawn) 프레임만 — 정오 처짐이 섞이지 않은 면적입니다.',
  forestSub: '점 = 화분별 RGR, 가로선 = 95 % 신뢰구간, 점선 = 군 평균.',
  forestNone: 'RGR 을 계산할 새벽 프레임이 아직 부족합니다 (화분당 3장 이상).',
  exportSub: '원본 표를 CSV 로 내려받습니다 — 보고서 부록용.',
  effect: (e: string) => ({ large: 'large effect', medium: 'medium effect', small: 'small effect' }[e] ?? e),
} as const
