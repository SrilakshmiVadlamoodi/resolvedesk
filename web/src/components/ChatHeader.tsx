interface Props {
  customerName: string
  onSwitchUser: () => void
  onNewConversation: () => void
}

export function ChatHeader({ customerName, onSwitchUser, onNewConversation }: Props) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-y-2 border-b border-border bg-surface-raised px-4 py-3 shadow-[0_1px_0_0_rgba(0,0,0,0.02),0_2px_6px_-4px_rgba(0,0,0,0.12)] sm:px-6">
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-semibold text-white">
          V
        </div>
        <span className="font-semibold text-ink">VoltKart Support</span>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onNewConversation}
          className="hidden text-sm text-ink-soft hover:text-brand sm:inline"
        >
          New conversation
        </button>
        <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden />
          <span className="text-ink-soft">Signed in as</span>
          <span className="font-medium text-ink">{customerName}</span>
        </div>
        <button
          type="button"
          onClick={onSwitchUser}
          className="text-sm font-medium text-brand hover:text-brand-strong"
        >
          Switch user
        </button>
      </div>
    </header>
  )
}
