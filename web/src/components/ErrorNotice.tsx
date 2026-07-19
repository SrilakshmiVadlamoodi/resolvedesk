interface Props {
  code: string | null
  message: string
}

const FRIENDLY_COPY: Record<string, string> = {
  RATE_LIMITED: "You're sending messages quickly — give it a few seconds.",
}

export function ErrorNotice({ code, message }: Props) {
  const text = (code && FRIENDLY_COPY[code]) || message

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl border border-danger/30 bg-danger-soft px-4 py-2.5 text-sm text-danger sm:max-w-[70%]">
        {text}
      </div>
    </div>
  )
}
