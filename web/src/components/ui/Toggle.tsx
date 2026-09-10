export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-12 flex-none items-center rounded-full border transition-colors disabled:opacity-40 ${checked ? 'border-primary bg-primary' : 'border-border bg-sunken'}`}
    >
      <span className={`absolute left-0.5 h-5.5 w-5.5 rounded-full bg-white shadow-1 transition-transform duration-[var(--dur-base)] ${checked ? 'translate-x-5' : 'translate-x-0'}`} style={{ width: 22, height: 22 }} />
    </button>
  )
}
