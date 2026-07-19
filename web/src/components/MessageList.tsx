import { useEffect, useRef, useState } from 'react'
import type { ChatItem } from '../types'
import { MessageBubble } from './MessageBubble'
import { ActionCard } from './ActionCard'
import { ConfirmationCard } from './ConfirmationCard'
import { EscalationCard } from './EscalationCard'
import { ErrorNotice } from './ErrorNotice'
import { TypingIndicator } from './TypingIndicator'

interface Props {
  items: ChatItem[]
  isWaitingForFirstToken: boolean
  onConfirm: (id: string) => void
  onCancel: (id: string) => void
  onSuggestion?: (text: string) => void
}

const NEAR_BOTTOM_PX = 80

const SUGGESTIONS = [
  "Where's my order?",
  'Start a refund',
  'Warranty question',
  'Change my address',
]

export function MessageList({ items, isWaitingForFirstToken, onConfirm, onCancel, onSuggestion }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [stuckToBottom, setStuckToBottom] = useState(true)

  useEffect(() => {
    const el = containerRef.current
    if (!el || !stuckToBottom) return
    el.scrollTop = el.scrollHeight
  }, [items, isWaitingForFirstToken, stuckToBottom])

  function handleScroll() {
    const el = containerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setStuckToBottom(distanceFromBottom < NEAR_BOTTOM_PX)
  }

  function jumpToLatest() {
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    setStuckToBottom(true)
  }

  if (items.length === 0 && !isWaitingForFirstToken) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-4">
        <p className="text-sm text-ink-soft">How can we help today?</p>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onSuggestion?.(s)}
              className="rounded-full border border-brand/40 px-4 py-1.5 text-sm font-medium text-brand transition hover:border-brand hover:bg-brand/5"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex-1 overflow-hidden">
      <div ref={containerRef} onScroll={handleScroll} className="h-full space-y-3 overflow-y-auto px-4 py-6 sm:px-6">
        {items.map((item) => {
          switch (item.kind) {
            case 'user':
              return <MessageBubble key={item.id} role="user" text={item.text} animate={false} />
            case 'assistant':
              return <MessageBubble key={item.id} role="assistant" text={item.text} animate={item.animate} />
            case 'action':
              return <ActionCard key={item.id} actionType={item.actionType} payload={item.payload} />
            case 'confirmation':
              return (
                <ConfirmationCard
                  key={item.id}
                  tool={item.tool}
                  arguments={item.arguments}
                  status={item.status}
                  onConfirm={() => onConfirm(item.id)}
                  onCancel={() => onCancel(item.id)}
                />
              )
            case 'escalation':
              return <EscalationCard key={item.id} message={item.message} />
            case 'error':
              return <ErrorNotice key={item.id} code={item.code} message={item.message} />
            default:
              return null
          }
        })}
        {isWaitingForFirstToken && <TypingIndicator />}
      </div>

      {!stuckToBottom && (
        <button
          type="button"
          onClick={jumpToLatest}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-ink px-4 py-1.5 text-sm font-medium text-white shadow-lg transition hover:opacity-90"
        >
          Jump to latest ↓
        </button>
      )}
    </div>
  )
}
