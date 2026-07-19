/** Single module owning all fetch/SSE traffic with the F-007 chat API. No
 * other file should call fetch() against the backend directly. */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const TOKEN_KEY = 'resolvedesk_token'
const CUSTOMER_ID_KEY = 'resolvedesk_customer_id'
const CUSTOMER_NAME_KEY = 'resolvedesk_customer_name'
const CONVERSATION_ID_KEY = 'resolvedesk_conversation_id'

// In-memory mirror of sessionStorage so a reload keeps the session (per spec)
// while normal navigation doesn't need to round-trip through storage.
let token: string | null = sessionStorage.getItem(TOKEN_KEY)

export interface Session {
  token: string
  customerId: number
  customerName: string
}

export function getStoredSession(): Session | null {
  const storedToken = sessionStorage.getItem(TOKEN_KEY)
  const customerId = sessionStorage.getItem(CUSTOMER_ID_KEY)
  const customerName = sessionStorage.getItem(CUSTOMER_NAME_KEY)
  if (!storedToken || !customerId || !customerName) return null
  return { token: storedToken, customerId: Number(customerId), customerName }
}

export function getStoredConversationId(): number | null {
  const raw = sessionStorage.getItem(CONVERSATION_ID_KEY)
  return raw ? Number(raw) : null
}

export function setStoredConversationId(conversationId: number | null): void {
  if (conversationId === null) {
    sessionStorage.removeItem(CONVERSATION_ID_KEY)
  } else {
    sessionStorage.setItem(CONVERSATION_ID_KEY, String(conversationId))
  }
}

export async function authDemo(customerId: number, customerName: string): Promise<Session> {
  const res = await fetch(`${API_BASE_URL}/auth/demo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ customer_id: customerId }),
  })
  if (!res.ok) throw new Error(`auth/demo failed: ${res.status}`)
  const body = (await res.json()) as { token: string; customer_id: number }

  token = body.token
  sessionStorage.setItem(TOKEN_KEY, body.token)
  sessionStorage.setItem(CUSTOMER_ID_KEY, String(body.customer_id))
  sessionStorage.setItem(CUSTOMER_NAME_KEY, customerName)

  return { token: body.token, customerId: body.customer_id, customerName }
}

export function switchUser(): void {
  token = null
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(CUSTOMER_ID_KEY)
  sessionStorage.removeItem(CUSTOMER_NAME_KEY)
  setStoredConversationId(null)
}

function authHeaders(): HeadersInit {
  if (!token) throw new Error('not signed in')
  return { Authorization: `Bearer ${token}` }
}

export interface SSEEvent {
  event: string
  data: Record<string, unknown>
}

/** Parses `event: x\ndata: {...}\n\n` frames off a fetch Response body. Used
 * instead of EventSource because the chat POST needs a request body, which
 * EventSource cannot send. */
async function* readSSE(resPromise: Response | Promise<Response>): AsyncGenerator<SSEEvent> {
  const res = await resPromise
  if (!res.body) return
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      let eventName = 'message'
      let dataLine = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLine += line.slice(5).trim()
      }
      if (dataLine) {
        yield { event: eventName, data: JSON.parse(dataLine) as Record<string, unknown> }
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}

export function sendMessage(conversationId: number | null, message: string): AsyncGenerator<SSEEvent> {
  return readSSE(
    fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    }).then((res) => {
      if (res.status === 401) throw new Error('session expired — please sign in again')
      return res
    }),
  )
}

export function confirmAction(conversationId: number, nonce: string): AsyncGenerator<SSEEvent> {
  return readSSE(
    fetch(`${API_BASE_URL}/chat/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ conversation_id: conversationId, nonce }),
    }).then((res) => {
      if (res.status === 401) throw new Error('session expired — please sign in again')
      return res
    }),
  )
}

export interface ConversationMessage {
  role: 'user' | 'assistant' | 'tool'
  content: string
  created_at: string
}

export interface ConversationHistory {
  conversation_id: number
  status: string
  messages: ConversationMessage[]
}

export async function getConversation(conversationId: number): Promise<ConversationHistory | null> {
  const res = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
    headers: authHeaders(),
  })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`GET /conversations/${conversationId} failed: ${res.status}`)
  return (await res.json()) as ConversationHistory
}
