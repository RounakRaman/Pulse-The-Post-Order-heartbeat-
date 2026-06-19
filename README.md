# Pulse-The-Post-Order-heartbeat-

A deterministic prototype simulating the post-purchase communication layer for delayed orders — the fix for the WISMO ("Where is my order") ticket category. It's not the customer-facing app itself; it's a reviewer tool with a manual clock so you can step through every state the system can be in.

Core logic, unchanged from v1: the trigger fires on real signal — elapsed time past the promised window plus live courier state — not a single hard deadline. A 4-hour grace buffer absorbs last-mile noise. If the courier shows "out for delivery" with a recent scan, the system suppresses the alert because the order is actively progressing. Past that, severity escalates: soft nudge → WISMO-style alert at 24h → resolution offer (credit or refund) at 48h, or immediately if the courier flags an exception.
What's new in this version:

Delivered-but-not-received dispute path. "Delivered" per the courier and "received" per the user aren't the same fact. A checkbox simulates the user disputing delivery, which routes to its own critical-urgency state with a replacement/refund path — instead of the original version treating "Delivered" as unconditionally clean.
Recovery, not just escalation. The trigger function is stateless and re-evaluates from current signals on every render. Simulate the courier resuming scans after a stuck exception, and the order naturally de-escalates back down — no special-casing needed, no permanent red flag.
Visible SLA countdown with real auto-resolution. Instead of a manual "simulate timeout" button, there's an actual countdown the user can see, and if it hits zero with no response, the system auto-issues a delay credit and escalates to ops on its own.

Delay reason codes. Weather, courier exception, address issue, warehouse delay — selectable once known, feeding both the message copy ("weather conditions are affecting deliveries in your area") and a hook for root-cause analytics on what's actually driving delay volume.
Post-resolution feedback loop. A two-tap "was this handled well?" after any resolution, logged against the order. This is the cheap addition that turns "we shipped a flow" into "we can prove the flow works.
