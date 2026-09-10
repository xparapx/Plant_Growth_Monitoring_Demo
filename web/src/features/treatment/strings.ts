import { fmtNum } from '@/lib/format'

/** Extra copy local to the treatment page (ko.ts is shared and not edited here). */
export const T = {
  histSub: '측정된 분포 — 두 군의 중심은 같고 폭만 다른지 확인합니다.',
  histNone: '토양수분 표본이 아직 없습니다.',
  howtoChord: (p05: number, p95: number, mean: number | null) =>
    `점선 현(chord): w = ${fmtNum(p05, 1)} → ${fmtNum(p95, 1)} % (측정 p05–p95). 세로 막대: w = ${fmtNum(mean, 1)} % 에서 곡선과 현의 차이 — Jensen 부등식이 예측하는 변동군의 손해(∩) 또는 이득(∪).`,
  howtoNoRef: '참고 구간(p05–p95)은 토양수분 표본이 쌓이면 표시됩니다. 곡선은 데이터에 맞춘 것이 아닙니다.',
  alignSub: 'ISO 주 단위 군 평균 — 두 선이 겹쳐야 처리가 유효합니다.',
  alignNone: '주 단위 평균을 계산할 표본이 아직 없습니다.',
  droopSub: 'dawn·pm 이 짝을 이룬 최근 날짜 기준.',
  droopDay: (day: string) => `${day} — dawn·pm 짝 기준`,
} as const
