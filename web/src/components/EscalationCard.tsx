interface Props {
  message: string
}

function HandoffIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
      <path d="M10 2a1 1 0 011 1v.09a7.001 7.001 0 015.91 5.91H17a1 1 0 110 2h-.09A7.001 7.001 0 0111 16.91V17a1 1 0 11-2 0v-.09A7.001 7.001 0 013.09 11H3a1 1 0 110-2h.09A7.001 7.001 0 019 3.09V3a1 1 0 011-1zm0 4a4 4 0 100 8 4 4 0 000-8z" />
    </svg>
  )
}

export function EscalationCard({ message }: Props) {
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[85%] items-start gap-3 rounded-2xl border border-amber/30 bg-amber-soft px-4 py-3 sm:max-w-[70%]">
        <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-amber text-white">
          <HandoffIcon />
        </div>
        <p className="font-medium text-ink">{message}</p>
      </div>
    </div>
  )
}
