import { useEffect, useRef, useState } from 'react'
import {
  authDemo,
  confirmAction,
  getConversation,
  getStoredConversationId,
  getStoredSession,
  sendMessage,
  setStoredConversationId,
  switchUser,
  type Session,
} from './api'
import type { ChatItem } from './types'
import { IdentityPicker } from './components/IdentityPicker'
import { ChatHeader } from './components/ChatHeader'
import { MessageList } from './components/MessageList'
import { ChatInput } from './components/ChatInput'

function newId(): string {
  return crypto.randomUUID()
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [signingIn, setSigningIn] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [items, setItems] = useState<ChatItem[]>([])
  const [isWaitingForFirstToken, setIsWaitingForFirstToken] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const conversationIdRef = useRef<number | null>(null)

  useEffect(() => {
    conversationIdRef.current = conversationId
  }, [conversationId])

  // Resume an existing session + conversation on load (proves F-007's
  // persistence claim across a real page reload, per the spec).
  useEffect(() => {
    const storedSession = getStoredSession()
    if (!storedSession) return
    setSession(storedSession)

    const storedConversationId = getStoredConversationId()
    if (storedConversationId === null) return

    setLoadingHistory(true)
    getConversation(storedConversationId)
      .then((history) => {
        if (!history) {
          // Conversation no longer resolvable for this session — start clean
          // rather than getting stuck on a dead id.
          setStoredConversationId(null)
          return
        }
        setConversationId(history.conversation_id)
        setItems(
          history.messages
            .filter((m) => m.role === 'user' || m.role === 'assistant')
            .map((m) => ({
              kind: m.role as 'user' | 'assistant',
              id: newId(),
              text: m.content,
              ...(m.role === 'assistant' ? { animate: false } : {}),
            })) as ChatItem[],
        )
      })
      .finally(() => setLoadingHistory(false))
  }, [])

  async function handlePickIdentity(customerId: number, name: string) {
    setSigningIn(true)
    try {
      const newSession = await authDemo(customerId, name)
      setSession(newSession)
      setConversationId(null)
      setItems([])
    } catch (err) {
      setItems([{ kind: 'error', id: newId(), code: null, message: (err as Error).message }])
    } finally {
      setSigningIn(false)
    }
  }

  function handleSwitchUser() {
    switchUser()
    setSession(null)
    setConversationId(null)
    setItems([])
  }

  function handleNewConversation() {
    setStoredConversationId(null)
    setConversationId(null)
    setItems([])
  }

  const hasPendingConfirmation = items.some((item) => item.kind === 'confirmation' && item.status === 'pending')
  const inputDisabled = isWaitingForFirstToken || hasPendingConfirmation || loadingHistory

  async function handleSend(message: string) {
    setItems((prev) => [...prev, { kind: 'user', id: newId(), text: message }])
    setIsWaitingForFirstToken(true)

    try {
      for await (const evt of sendMessage(conversationIdRef.current, message)) {
        applyEvent(evt)
      }
    } catch (err) {
      setItems((prev) => [...prev, { kind: 'error', id: newId(), code: null, message: (err as Error).message }])
    } finally {
      setIsWaitingForFirstToken(false)
    }
  }

  function applyEvent(evt: { event: string; data: Record<string, unknown> }) {
    switch (evt.event) {
      case 'conversation': {
        const id = evt.data.conversation_id as number
        setConversationId(id)
        setStoredConversationId(id)
        break
      }
      case 'token':
        setIsWaitingForFirstToken(false)
        setItems((prev) => [...prev, { kind: 'assistant', id: newId(), text: evt.data.text as string, animate: true }])
        break
      case 'action':
        setIsWaitingForFirstToken(false)
        setItems((prev) => [
          ...prev,
          { kind: 'action', id: newId(), actionType: evt.data.type as string, payload: evt.data },
        ])
        break
      case 'confirmation_request':
        setIsWaitingForFirstToken(false)
        setItems((prev) => [
          ...prev,
          {
            kind: 'confirmation',
            id: newId(),
            conversationId: evt.data.conversation_id as number,
            nonce: evt.data.nonce as string,
            tool: evt.data.tool as string,
            arguments: evt.data.arguments as Record<string, unknown>,
            status: 'pending',
          },
        ])
        break
      case 'escalated':
        setIsWaitingForFirstToken(false)
        setItems((prev) => [
          ...prev,
          {
            kind: 'escalation',
            id: newId(),
            message: evt.data.message as string,
            reason: (evt.data.reason as string | null) ?? null,
          },
        ])
        break
      case 'error':
        setIsWaitingForFirstToken(false)
        setItems((prev) => [
          ...prev,
          { kind: 'error', id: newId(), code: (evt.data.code as string | null) ?? null, message: evt.data.message as string },
        ])
        break
      case 'done':
        setIsWaitingForFirstToken(false)
        break
    }
  }

  async function handleConfirm(itemId: string) {
    const item = items.find((i) => i.id === itemId)
    if (!item || item.kind !== 'confirmation') return

    setItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'confirmed' } : i)))
    setIsWaitingForFirstToken(true)

    try {
      for await (const evt of confirmAction(item.conversationId, item.nonce)) {
        if (evt.event === 'error') {
          setItems((prev) => prev.map((i) => (i.id === itemId && i.kind === 'confirmation' ? { ...i, status: 'error' } : i)))
        }
        applyEvent(evt)
      }
    } catch (err) {
      setItems((prev) => [...prev, { kind: 'error', id: newId(), code: null, message: (err as Error).message }])
    } finally {
      setIsWaitingForFirstToken(false)
    }
  }

  function handleCancel(itemId: string) {
    setItems((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'cancelled' } : i)))
  }

  if (!session) {
    return <IdentityPicker onPick={handlePickIdentity} pending={signingIn} />
  }

  return (
    <div className="flex h-screen flex-col bg-surface">
      <ChatHeader customerName={session.customerName} onSwitchUser={handleSwitchUser} onNewConversation={handleNewConversation} />
      <MessageList
        items={items}
        isWaitingForFirstToken={isWaitingForFirstToken}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        onSuggestion={handleSend}
      />
      <ChatInput
        disabled={inputDisabled}
        placeholder={hasPendingConfirmation ? 'Respond to the confirmation above to continue…' : 'Ask about an order, refund, or anything else…'}
        onSend={handleSend}
      />
    </div>
  )
}

export default App
