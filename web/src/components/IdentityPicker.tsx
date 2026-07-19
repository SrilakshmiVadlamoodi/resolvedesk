import { DEMO_CUSTOMERS } from '../demoCustomers'

interface Props {
  onPick: (customerId: number, name: string) => void
  pending: boolean
}

export function IdentityPicker({ onPick, pending }: Props) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mb-2 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-lg font-semibold text-white">
            V
          </div>
          <h1 className="text-xl font-semibold text-ink">VoltKart Support</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Demo mode — pick a customer to sign in as. No password required.
          </p>
        </div>

        <div className="space-y-2">
          {DEMO_CUSTOMERS.map((customer) => (
            <button
              key={customer.id}
              type="button"
              disabled={pending}
              onClick={() => onPick(customer.id, customer.name)}
              className="flex w-full items-center justify-between rounded-xl border border-border bg-surface-raised px-4 py-3 text-left shadow-sm transition hover:border-brand hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span>
                <span className="block font-medium text-ink">Sign in as {customer.name}</span>
                <span className="block text-sm text-ink-soft">
                  {customer.orderCount} order{customer.orderCount === 1 ? '' : 's'}
                </span>
              </span>
              <span aria-hidden className="text-ink-soft">
                &rarr;
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
