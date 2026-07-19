import { formatInr } from '../format'

interface Props {
  actionType: string
  payload: Record<string, unknown>
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
      <path
        fillRule="evenodd"
        d="M16.704 5.29a1 1 0 010 1.415l-7.5 7.5a1 1 0 01-1.414 0l-3.5-3.5a1 1 0 111.414-1.414l2.793 2.792 6.793-6.793a1 1 0 011.414 0z"
        clipRule="evenodd"
      />
    </svg>
  )
}

function renderContent(actionType: string, payload: Record<string, unknown>) {
  switch (actionType) {
    case 'refund_initiated':
      return {
        title: `Refund of ${formatInr(payload.amount)} initiated`,
        detail: `Order #${payload.order_id} · 5–7 business days to your original payment method`,
      }
    case 'address_updated':
      return {
        title: 'Shipping address updated',
        detail: `Order #${payload.order_id} → ${String(payload.new_address ?? '')}`,
      }
    case 'warranty_claim_filed':
      return {
        title: 'Warranty claim filed',
        detail: `Order #${payload.order_id} · Claim #${payload.claim_id ?? payload.refund_id ?? ''}`,
      }
    default:
      return { title: actionType.replace(/_/g, ' '), detail: '' }
  }
}

export function ActionCard({ actionType, payload }: Props) {
  const { title, detail } = renderContent(actionType, payload)

  return (
    <div className="flex justify-start">
      <div className="flex max-w-[85%] items-start gap-3 rounded-2xl border border-success/30 bg-success-soft px-4 py-3 sm:max-w-[70%]">
        <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-success text-white">
          <CheckIcon />
        </div>
        <div>
          <p className="font-medium text-ink">{title}</p>
          {detail && <p className="mt-0.5 text-sm text-ink-soft">{detail}</p>}
        </div>
      </div>
    </div>
  )
}
