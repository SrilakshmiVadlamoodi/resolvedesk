# F-004 — Intelligent Escalation & Handoff

## Goal
When the agent can't or shouldn't act, it hands a human everything they need to resolve the ticket in one touch — escalation as a feature, not a failure.

## Triggers
1. Policy returns ESCALATE (over-limit refund, expired window, duplicate).
2. Retrieval low-confidence on a policy/product question the customer insists on.
3. Customer explicitly asks for a human.
4. Sentiment: two consecutive messages classified negative/angry (single extra LLM classification call, cheap). *(cut-line candidate)*
5. Loop safety: 6 tool steps without resolution.

## Handoff packet (one structured LLM call at escalation time)
```json
{
  "reason": "OVER_LIMIT",
  "summary": "Customer wants ₹8,499 refund on order VK-1042 (delivered 4 days ago, within window). Amount exceeds auto-approve ceiling.",
  "sentiment": "frustrated",
  "attempted_actions": ["get_order_details", "check_refund → ESCALATE(OVER_LIMIT)"],
  "suggested_action": "Approve manually — order qualifies on every rule except amount."
}
```

## Behavior
- On escalation: conversation status → `escalated`; row in `escalations`; customer gets an honest message ("I've raised this with our support team with full context — reference #E-107; expect a response within 4 business hours"). Agent stays available for *other* questions in the same chat.
- Queue UI (in admin dashboard): open escalations, packet visible, "Claim" button flips status (no human-side chat — out of scope).
- Attempted actions in the packet come from the `events` table, not from the LLM's memory — guaranteed accurate.

## Acceptance criteria
1. ₹8,000+ refund request → escalation with reason OVER_LIMIT and a correct suggested action.
2. "talk to a human" → immediate escalation, no argument from the agent.
3. Packet's `attempted_actions` exactly matches logged events for that conversation.
4. After escalation, the customer can still ask an unrelated question and get a normal answer.

## Out of scope
Human reply UI, SLA timers, notifications/email, reassignment.
