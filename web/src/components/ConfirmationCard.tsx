import { formatInr } from '../format'

interface Props {
  tool: string
  arguments: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'cancelled' | 'error'
  onConfirm: () => void
  onCancel: () => void
}

function describe(tool: string, args: Record<string, unknown>): string {
  switch (tool) {
    case 'initiate_refund':
      return `Confirm refund of ${formatInr(args.amount)} for order #${args.order_id}?`
    case 'update_shipping_address':
      return `Confirm updating the shipping address for order #${args.order_id} to "${String(
        args.new_address ?? '',
      )}"?`
    case 'file_warranty_claim':
      return `Confirm filing a warranty claim for order #${args.order_id}?`
    default:
      return `Confirm this action: ${tool.replace(/_/g, ' ')}?`
  }
}

export function ConfirmationCard({ tool, arguments: args, status, onConfirm, onCancel }: Props) {
  const question = describe(tool, args)

  if (status !== 'pending') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl border border-border bg-surface px-4 py-2.5 text-sm text-ink-soft sm:max-w-[70%]">
          {question}
          <span className="ml-2 font-medium">
            {status === 'confirmed' && '— confirmed'}
            {status === 'cancelled' && '— cancelled'}
            {status === 'error' && '— could not be confirmed'}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl border border-brand/30 bg-brand-soft px-4 py-3 sm:max-w-[70%]">
        <p className="font-medium text-ink">{question}</p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-lg bg-brand px-4 py-1.5 text-sm font-medium text-white transition hover:bg-brand-strong"
          >
            Confirm
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-border bg-surface-raised px-4 py-1.5 text-sm font-medium text-ink transition hover:bg-surface"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
