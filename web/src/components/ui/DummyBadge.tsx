import { ko } from '@/i18n/ko'

export function DummyBadge({ label = ko.dummy.badge }: { label?: string }) {
  return <span className="badge-dummy" title="가상 데이터 — 노드 연결 시 실측값으로 바뀝니다">{label}</span>
}
