/** F-007's `POST /auth/demo` takes a customer_id but has no endpoint to list
 * customer names — there's no API this picker can call to discover who's
 * seeded. These ids/names/order-counts are read directly from data/seed.py
 * (the reproducible source of truth per CLAUDE.md) and must be kept in sync
 * with it by hand. Flagged to the user: only 2 demo customers exist today,
 * not the 3-4 the spec assumed. */
export interface DemoCustomer {
  id: number
  name: string
  orderCount: number
}

export const DEMO_CUSTOMERS: DemoCustomer[] = [
  { id: 1, name: 'Aditi Rao', orderCount: 2 },
  { id: 2, name: 'Rahul Shah', orderCount: 1 },
]
