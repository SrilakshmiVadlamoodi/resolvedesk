export type ChatItem =
  | { kind: 'user'; id: string; text: string }
  | { kind: 'assistant'; id: string; text: string; animate: boolean }
  | { kind: 'action'; id: string; actionType: string; payload: Record<string, unknown> }
  | {
      kind: 'confirmation'
      id: string
      conversationId: number
      nonce: string
      tool: string
      arguments: Record<string, unknown>
      status: 'pending' | 'confirmed' | 'cancelled' | 'error'
      resultMessage?: string
    }
  | { kind: 'escalation'; id: string; message: string; reason: string | null }
  | { kind: 'error'; id: string; code: string | null; message: string }
