import { useTypewriter } from '../hooks/useTypewriter'

interface Props {
  role: 'user' | 'assistant'
  text: string
  animate: boolean
}

export function MessageBubble({ role, text, animate }: Props) {
  const { visibleText } = useTypewriter(animate ? text : '')
  const shown = animate ? visibleText : text
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed sm:max-w-[65%] ${
          isUser
            ? 'rounded-br-sm bg-brand text-white'
            : 'rounded-bl-sm border border-border border-l-2 border-l-brand bg-surface-raised text-ink'
        }`}
      >
        {shown}
        {animate && shown.length < text.length && (
          <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-ink-soft align-middle" aria-hidden />
        )}
      </div>
    </div>
  )
}
