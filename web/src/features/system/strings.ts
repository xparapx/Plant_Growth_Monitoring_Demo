/* Page-local copy for /system (shared keys live in ko.system / ko.export). */
export const S = {
  noSystemd: 'systemd 없음 — Pi 에서만 표시',
  noJournal: 'journalctl 없음',
  since: '시작', enabled: '부팅 시', sub: '상태',
  host: {
    hostname: 'hostname', platform: 'platform', python: 'python', opencv: 'opencv', picamera2: 'picamera2', gpiozero: 'gpiozero',
    tz: 'tz', time: '서버 시각', uptime: '호스트 가동', serviceUptime: '서비스 가동', cpu: 'CPU 온도', disk: '디스크', dataDir: 'data_dir',
    version: '버전', gitRev: 'git', camera: '카메라', led: 'LED', mqtt: 'MQTT', wsClients: 'WS 클라이언트', dummyFill: 'dummy_fill', pid: 'pid',
  },
  db: { table: '테이블', rows: '행', maxTs: '마지막 ts', path: '경로', size: '크기', exists: '존재', photos: '사진', yes: '있음', no: '없음' },
  config: {
    form: '폼', json: 'JSON', reset: '되돌리기', noChange: '변경된 항목이 없습니다', saved: '저장했습니다', jsonBad: (m: string) => `JSON 오류: ${m}`,
    stale: '설정이 그 사이에 바뀌었습니다 — 새로고침', confirmTitle: '설정을 저장할까요?', confirmBody: '변경된 섹션만 PATCH 로 보냅니다. 카메라가 열려 있으면 촬영 조건이 바로 적용됩니다.',
    warnings: 'config.json 경고', checkBad: '설정 점검 — 실패', checkWarn: '설정 점검 — 주의',
    sections: { capture: '촬영 조건', layout: '배치', qc: '품질 기준', analysis: '분석', led: 'LED', schedule: '스케줄', mqtt: 'MQTT', tz: '시간대', rois: 'ROI (읽기 전용)', treatMode: '배정 방식' },
    sizeRO: '해상도 (읽기 전용)', roiCols: ['plant_id', 'treat', 'x', 'y', 'w', 'h'], modeNone: '미배정',
  },
  export: { hint: 'plant.db 의 원본 행을 CSV 로 내려받습니다. dummy 표시가 있으면 가상 데이터입니다.', tables: { readings: 'readings (환경)', soil: 'soil (토양수분)', pump_log: 'pump_log (급수)', growth: 'growth (캐노피)' } },
  replay: { hint: 'growth.jsonl 에 기록됐지만 MQTT 로 나가지 못한 측정을 다시 발행합니다.', sent: '발행', skipped: '건너뜀', errors: '오류', lastDb: 'DB 마지막 ts' },
  logs: { events: '최근 이벤트', noEvents: '이벤트가 아직 없습니다', lines: (n: number) => `${n}줄` },
} as const
