import { useState, type FormEvent, type KeyboardEvent } from 'react'

interface Props {
  disabled: boolean
  placeholder: string
  onSend: (message: string) => void
}

export function ChatInput({ disabled, placeholder, onSend }: Props) {
  const [value, setValue] = useState('')

  function submit(e?: FormEvent) {
    e?.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form onSubmit={submit} className="border-t border-border bg-surface-raised px-4 py-3 sm:px-6">
      <div className="flex items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          rows={1}
          className="max-h-32 flex-1 resize-none rounded-lg border border-border bg-surface px-3.5 py-2.5 text-[15px] text-ink placeholder:text-ink-soft focus:border-brand focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="flex h-10 items-center justify-center rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </form>
  )
}
