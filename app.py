"""
PULSE — Post-Order Trust Layer (Prototype)
Scenario A: Delayed order, no communication.

This is a single-file Streamlit prototype simulating the trigger logic,
user-facing messaging, and resolution path designed in the assignment deck.
It uses a simulated order + a manually-advanceable clock so a reviewer can
step through every state without waiting in real time.

v2 additions over the original prototype:
  - "Delivered but not received" dispute path (courier says delivered,
    user disagrees) instead of treating "Delivered" as an unconditionally
    terminal, clean state.
  - Recovery path: a "critical" / stuck-scan order can recover back to
    "alert" or "soft" if the courier starts scanning again, instead of
    escalation being one-directional.
  - A real visible SLA countdown on the resolution offer, instead of a
    manual "simulate timeout" button.
  - Delay reason codes (weather, courier exception, address issue,
    warehouse delay) that tailor the message copy and get logged for
    root-cause analytics, not just the generic "this has gone on too
    long" copy.
  - Post-resolution feedback capture ("was this handled well?") so the
    prototype demonstrates the team is tracking outcome quality, not
    just shipping the flow.

Run locally:
    pip install streamlit
    streamlit run app.py

Deploy (free):
    1. Push this file to a public GitHub repo (just this one file is enough).
    2. Go to https://share.streamlit.io -> "New app" -> point it at the repo/app.py.
    3. Done. No other config needed — no external dependencies beyond streamlit itself.
"""

import streamlit as st

# --------------------------------------------------------------------------------------
# Brand tokens (PULSE palette — kept from POP, renamed)
# --------------------------------------------------------------------------------------
ORANGE = "#FF5A1F"
ORANGE_DARK = "#E14A12"
CHAR = "#1C1C1E"
CREAM = "#FFF4EC"
MUTED = "#6B6B70"
GREEN = "#1E8E5A"

st.set_page_config(page_title="PULSE — Post-Order Trust Layer", page_icon="📦", layout="wide")

st.markdown(f"""
<style>
.stApp {{ background-color: #FFFFFF; }}
.pop-header {{
    background-color: {CHAR}; padding: 28px 32px; border-radius: 14px; margin-bottom: 24px;
}}
.pop-header h1 {{ color: white; font-size: 26px; margin: 0; font-weight: 700; }}
.pop-header p {{ color: #C9C9CC; font-size: 14px; margin: 6px 0 0 0; }}
.pop-badge {{ color: {ORANGE}; font-weight: 700; letter-spacing: 1px; font-size: 13px; }}
.status-card {{
    background-color: {CREAM}; border-radius: 12px; padding: 22px 24px; margin-bottom: 14px;
}}
.dark-card {{
    background-color: {CHAR}; border-radius: 12px; padding: 22px 24px; margin-bottom: 14px; color: white;
}}
.green-card {{
    background-color: #EAF7EF; border-radius: 12px; padding: 22px 24px; margin-bottom: 14px;
}}
.tag-soft {{ background:#E8E8EA; color:#444; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }}
.tag-warn {{ background:#FFE4D6; color:{ORANGE_DARK}; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }}
.tag-crit {{ background:{ORANGE}; color:white; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }}
.tag-good {{ background:{GREEN}; color:white; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }}
.small-muted {{ color: {MUTED}; font-size: 13px; }}
hr {{ border-color: #EDE3DC; }}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------------------
# Simulated order state
# --------------------------------------------------------------------------------------
DEFAULTS = {
    "hours_late": 0,
    "last_scan_minutes_ago": 45,
    "courier_status": "In transit",
    "delay_reason": "None / on time",
    "user_disputes_delivery": False,
    "resolution_choice": None,
    "notify_opt_in": False,
    "escalated": False,
    "sla_minutes_remaining": 30,
    "feedback_submitted": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

ORDER = {
    "id": "PULSE-58213940",
    "item": "Cotton Block-Print Kurta (M)",
    "category": "Fashion",
    "promised_by": "Today, 8:00 PM",
    "placed_with": "RapidShip Logistics",
}

# --------------------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------------------
st.markdown(f"""
<div class="pop-header">
    <div class="pop-badge">PULSE</div>
    <h1>Post-Order Trust Layer — Prototype</h1>
    <p>Scenario A: Delayed order, no communication · simulating trigger logic → user messaging → resolution path → feedback loop</p>
</div>
""", unsafe_allow_html=True)

st.caption(
    "This is a reviewer tool, not the end-user app. Use the controls on the left to move the order "
    "forward in time and watch how the trigger, message, resolution path, and feedback loop change at each stage."
)

# --------------------------------------------------------------------------------------
# Sidebar — simulation controls (the "admin" view)
# --------------------------------------------------------------------------------------
with st.sidebar:
    st.subheader("⚙️ Simulation controls")
    st.markdown("**Order**")
    st.write(f"`{ORDER['id']}` — {ORDER['item']}")
    st.caption(f"{ORDER['category']} · Promised by {ORDER['promised_by']} · Carrier: {ORDER['placed_with']}")

    st.markdown("---")
    st.session_state.hours_late = st.slider(
        "Hours past promised delivery window", min_value=-6, max_value=80, value=st.session_state.hours_late, step=1,
        help="Negative = order is still within its promised window. Positive = order is late by this many hours."
    )
    st.session_state.last_scan_minutes_ago = st.slider(
        "Minutes since last courier scan", min_value=5, max_value=300, value=st.session_state.last_scan_minutes_ago, step=5
    )
    st.session_state.courier_status = st.selectbox(
        "Courier-reported status", ["In transit", "Out for delivery", "Exception / stuck", "Delivered"],
        index=["In transit", "Out for delivery", "Exception / stuck", "Delivered"].index(st.session_state.courier_status)
    )

    if st.session_state.courier_status == "Delivered":
        st.session_state.user_disputes_delivery = st.checkbox(
            "🙅 User says: \"I never received this\"",
            value=st.session_state.user_disputes_delivery,
            help="Simulates the courier marking delivered while the user disputes it — a common real-world WISMO case the original prototype didn't model."
        )

    if st.session_state.courier_status in ("In transit", "Out for delivery", "Exception / stuck") and st.session_state.hours_late > 4:
        st.session_state.delay_reason = st.selectbox(
            "Delay reason (once known)",
            ["None / on time", "Weather disruption", "Courier exception", "Address issue", "Warehouse dispatch delay"],
            index=["None / on time", "Weather disruption", "Courier exception", "Address issue", "Warehouse dispatch delay"].index(st.session_state.delay_reason)
            if st.session_state.delay_reason in ["None / on time", "Weather disruption", "Courier exception", "Address issue", "Warehouse dispatch delay"] else 0,
            help="Tailors the message copy and gets logged for root-cause analytics — not shown to the user as raw text, just used to write the right message."
        )

    st.markdown("---")
    st.caption("**Recovery simulation:** if the order is in a critical/stuck state, you can simulate the courier recovering (e.g. exception clears, scan comes back) to see the de-escalation path.")
    if st.session_state.courier_status == "Exception / stuck":
        if st.button("✅ Simulate: courier resumes scanning"):
            st.session_state.courier_status = "In transit"
            st.session_state.last_scan_minutes_ago = 5
            st.rerun()

    if st.button("🔄 Reset simulation"):
        for k in DEFAULTS:
            del st.session_state[k]
        st.rerun()

# --------------------------------------------------------------------------------------
# TRIGGER LOGIC — the deterministic rules engine from the design
# --------------------------------------------------------------------------------------
hours_late = st.session_state.hours_late
status = st.session_state.courier_status
scan_age = st.session_state.last_scan_minutes_ago

def evaluate_trigger():
    """
    Mirrors the trigger logic from the design doc, extended for v2:
      - Fires at promised window + 4h grace (not at the deadline itself).
      - Suppressed if courier shows 'out for delivery' AND last scan < 2h old.
      - Severity bands: 0-24h soft nudge, 24h+ WISMO-style alert, 48h+ resolution offer.
      - Exception/stuck scan escalates regardless of hour band once past grace.
      - NEW: "Delivered" is only a clean terminal state if the user does not
        dispute it. A dispute routes to its own "delivery_dispute" state,
        which is treated with the same urgency as "critical" since the
        package may be lost, stolen, or misdelivered.
      - NEW: recovery is possible — this function is stateless and re-evaluates
        from current signals every render, so a previously-critical order that
        starts scanning again naturally falls back to a lower-severity state
        without any special-casing required.
    """
    if status == "Delivered":
        if st.session_state.user_disputes_delivery:
            return "delivery_dispute", "disputed"
        return "delivered", None

    if hours_late <= 0:
        return "on_track", None

    in_grace = hours_late <= 4
    if in_grace:
        return "grace_period", None

    suppressed = (status == "Out for delivery" and scan_age < 120)
    if suppressed and hours_late < 24:
        return "suppressed_progressing", None

    if status == "Exception / stuck":
        return "critical", "stuck_scan"
    if hours_late >= 48:
        return "critical", "48h"
    if hours_late >= 24:
        return "alert", "24h"
    return "soft", "early_late"

state, reason = evaluate_trigger()

REASON_COPY = {
    "Weather disruption": "weather conditions are affecting deliveries in your area",
    "Courier exception": "the courier flagged an issue in transit",
    "Address issue": "there's a question about the delivery address",
    "Warehouse dispatch delay": "the item was dispatched later than planned",
}

# --------------------------------------------------------------------------------------
# Two-column layout: left = trigger engine view, right = what the user sees
# --------------------------------------------------------------------------------------
left, right = st.columns([1, 1.3], gap="large")

with left:
    st.subheader("🔧 Trigger engine (internal view)")

    if state == "delivered":
        st.markdown('<span class="tag-good">DELIVERED — CONFIRMED</span>', unsafe_allow_html=True)
        st.write("Order delivered, no dispute raised. Terminal, clean state.")
    elif state == "delivery_dispute":
        st.markdown('<span class="tag-crit">DELIVERY DISPUTE</span>', unsafe_allow_html=True)
        st.write(
            "Courier marked **Delivered**, but the user says they never received it. "
            "Treated with the same urgency as a critical delay — package may be lost, "
            "stolen, or misdelivered. **Not** treated as resolved."
        )
    elif state == "on_track":
        st.markdown('<span class="tag-soft">ON TRACK</span>', unsafe_allow_html=True)
        st.write(f"Within promised window. {abs(hours_late)}h remaining before deadline.")
    elif state == "grace_period":
        st.markdown('<span class="tag-soft">GRACE PERIOD</span>', unsafe_allow_html=True)
        st.write(f"{hours_late}h past promised window — inside the 4h grace buffer. **No message sent.** Avoids false alarms from last-mile noise.")
    elif state == "suppressed_progressing":
        st.markdown('<span class="tag-soft">SUPPRESSED</span>', unsafe_allow_html=True)
        st.write(
            f"{hours_late}h late, but courier shows **Out for delivery** with a scan "
            f"{scan_age} min ago (< 2h). Trigger suppressed — order is actively progressing."
        )
    elif state == "soft":
        st.markdown('<span class="tag-warn">SOFT NUDGE</span>', unsafe_allow_html=True)
        st.write(f"{hours_late}h late. Past grace period. Soft, self-serve nudge triggered.")
    elif state == "alert":
        st.markdown('<span class="tag-warn">WISMO-STYLE ALERT</span>', unsafe_allow_html=True)
        st.write(f"{hours_late}h late. This is the threshold that, left unhandled, becomes a 'Where is my order' ticket — Task 1's diagnosis target.")
    elif state == "critical":
        st.markdown('<span class="tag-crit">RESOLUTION OFFER</span>', unsafe_allow_html=True)
        if reason == "stuck_scan":
            st.write("Courier status is **Exception / stuck** — escalating regardless of elapsed hours.")
        else:
            st.write(f"{hours_late}h late. Crossed the resolution threshold — system now offers a concrete choice, not just an apology.")
        st.caption(
            "**Recovery path:** if the courier resumes scanning (sidebar button), this order "
            "re-evaluates down to a lower-severity state on the next render — escalation is "
            "not one-directional."
        )

    if st.session_state.delay_reason != "None / on time" and state in ("soft", "alert", "critical"):
        st.caption(f"**Logged delay reason:** {st.session_state.delay_reason} (feeds root-cause analytics, tailors message copy)")

    st.markdown("---")
    st.caption("**Why this design:** the trigger reacts to real signal (elapsed time + courier state + delivery confirmation), "
                "not a single hard deadline. That's what keeps false alarms down without staying silent too long.")

    with st.expander("See raw signals feeding the trigger"):
        st.json({
            "hours_past_promised_window": hours_late,
            "courier_status": status,
            "minutes_since_last_scan": scan_age,
            "user_disputes_delivery": st.session_state.user_disputes_delivery,
            "delay_reason_code": st.session_state.delay_reason,
            "evaluated_state": state,
            "reason_code": reason,
        })

with right:
    st.subheader("📱 What the user sees")

    if state in ("delivered", "on_track", "grace_period", "suppressed_progressing"):
        st.markdown(f"""
        <div class="status-card">
            <b>{ORDER['item']}</b><br>
            <span class="small-muted">Order {ORDER['id']}</span><br><br>
            { "✅ Delivered" if state=="delivered" else f"🚚 On the way — arriving by {ORDER['promised_by']}" }
        </div>
        """, unsafe_allow_html=True)
        if state == "suppressed_progressing":
            st.caption("No proactive message shown — the order is moving, so silence here is correct, not a gap.")

    elif state == "delivery_dispute":
        st.markdown(f"""
        <div class="dark-card">
            <b>Let's sort this out — we'll make it right</b><br><br>
            <span style="color:#C9C9CC;font-size:13px;">{ORDER['item']} · Order {ORDER['id']}</span><br><br>
            Our records show this was delivered, but you've told us it didn't arrive. We're not
            asking you to prove anything right now — we're opening an investigation with the
            carrier and protecting your order in the meantime.
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.button("📸 Add a photo of the delivery area", use_container_width=True)
        with c2:
            st.button("💳 Get an instant replacement or refund", use_container_width=True)
        st.caption("**Design note:** disputes get a resolution path immediately, not after a multi-day investigation queue. Risk/cost tradeoff is a policy lever, not a UX one.")

    elif state == "soft":
        st.markdown(f"""
        <div class="status-card">
            <b>Your order is taking a bit longer than expected</b><br><br>
            <span class="small-muted">{ORDER['item']} · Order {ORDER['id']}</span><br><br>
            We're tracking it closely. Current status: <b>{status}</b>, last update {scan_age} min ago.<br>
            Updated estimate: <b>likely within the next few hours.</b>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.notify_opt_in = st.checkbox("🔔 Notify me on the next update", value=st.session_state.notify_opt_in)
        st.button("Track order")

    elif state == "alert":
        reason_clause = f" — {REASON_COPY[st.session_state.delay_reason]}" if st.session_state.delay_reason in REASON_COPY else ""
        st.markdown(f"""
        <div class="status-card">
            <b>Your order is taking longer than expected — here's what's happening</b><br><br>
            <span class="small-muted">{ORDER['item']} · Order {ORDER['id']}</span><br><br>
            It's been <b>{hours_late} hours</b> past the promised window{reason_clause}. Last known status: <b>{status}</b>
            ({scan_age} min ago).<br>
            Revised estimate: <b>likely today</b> — we'll update you the moment that changes.
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.button("📍 Track order", use_container_width=True)
        with c2:
            st.button("💬 Talk to us", use_container_width=True)

    elif state == "critical":
        if reason == "stuck_scan":
            headline = "We've lost track of your order — here's what we're doing"
            body = "No courier update in a while and the carrier flagged an exception. We've escalated this internally."
        else:
            reason_clause = f" — {REASON_COPY[st.session_state.delay_reason]}" if st.session_state.delay_reason in REASON_COPY else ""
            headline = "This has gone on too long — let's fix it"
            body = f"Your order is {hours_late} hours past the promised window{reason_clause}. We'd rather resolve this than keep asking you to wait."

        st.markdown(f"""
        <div class="dark-card">
            <b>{headline}</b><br><br>
            <span style="color:#C9C9CC;font-size:13px;">{ORDER['item']} · Order {ORDER['id']}</span><br><br>
            {body}
        </div>
        """, unsafe_allow_html=True)

        if not st.session_state.resolution_choice:
            mins_left = st.session_state.sla_minutes_remaining
            bar_pct = max(0, min(100, int((mins_left / 30) * 100)))
            st.markdown(f"""
            <div class="small-muted">⏱ Respond within <b>{mins_left} min</b> or we'll automatically issue a delay credit and keep the order moving — no action needed if you'd rather not choose.</div>
            """, unsafe_allow_html=True)
            st.progress(bar_pct / 100)
            st.session_state.sla_minutes_remaining = st.slider(
                "Simulate SLA clock ticking down (admin)", 0, 30, st.session_state.sla_minutes_remaining,
                label_visibility="collapsed"
            )

        st.write("**Choose how you'd like to resolve this:**")
        choice = st.radio(
            "Resolution",
            ["Wait — and get a delivery-delay credit", "Cancel for an instant refund"],
            index=None,
            label_visibility="collapsed",
        )
        if choice:
            st.session_state.resolution_choice = choice
            st.success(f"Logged: \"{choice}\" — this is now attached to the order. Support will see this choice automatically and won't ask you to repeat it.")
        elif st.session_state.sla_minutes_remaining == 0 and not st.session_state.escalated:
            st.session_state.resolution_choice = "Auto-resolved — delivery-delay credit (SLA timeout)"
            st.session_state.escalated = True
            st.warning("SLA expired with no response. Auto-resolved with a delay credit and escalated to ops with full context — no manual handoff needed.")

        if st.session_state.resolution_choice and not st.session_state.feedback_submitted:
            st.markdown("---")
            st.write("**Quick one before you go — was this handled well?**")
            fb_cols = st.columns(3)
            with fb_cols[0]:
                if st.button("👍 Yes"):
                    st.session_state.feedback_submitted = "positive"
                    st.rerun()
            with fb_cols[1]:
                if st.button("👎 No"):
                    st.session_state.feedback_submitted = "negative"
                    st.rerun()
            with fb_cols[2]:
                if st.button("😐 It's okay"):
                    st.session_state.feedback_submitted = "neutral"
                    st.rerun()

        if st.session_state.feedback_submitted:
            label = {
                "positive": "👍 Marked as well-handled",
                "negative": "👎 Marked as poorly-handled — flagged for support review",
                "neutral": "😐 Marked as neutral",
            }[st.session_state.feedback_submitted]
            st.markdown(f"""
            <div class="green-card">
                <b>Thanks — feedback logged.</b><br>
                <span class="small-muted">{label}. This closes the loop: resolution outcome, delay reason, and
                satisfaction are all attached to order {ORDER['id']} for the post-incident metric, not just the ticket.</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("**Design note:** every state above the grace period has a button. There is no state where the "
                "user just sees a status with nothing to do next.")

# --------------------------------------------------------------------------------------
# Footer — ties back to the written diagnosis
# --------------------------------------------------------------------------------------
st.markdown("---")
with st.expander("Why this scenario, and what's deliberately not built — see full reasoning"):
    st.markdown("""
**Diagnosis (Task 1):** WISMO is 34% of tickets, but most of it is a *communication* gap, not a *delivery* gap —
the order is fine, the user just isn't told anything. This prototype simulates the fix: a trigger that fires on
real signal (elapsed time + courier state + delivery confirmation), not a single deadline, so it neither stays
silent too long nor fires false alarms.

**What v2 adds over the first pass:**
- A delivery-dispute path, because "Delivered" per the courier and "received" per the user are not the same
  fact, and treating them as the same fact is exactly the kind of silent gap this tool exists to close.
- Recovery: severity is re-evaluated from live signal every render, so a stuck order that starts moving again
  naturally de-escalates instead of staying flagged as critical forever.
- A visible SLA countdown with a real auto-resolution behavior, instead of a manual "simulate timeout" button —
  this is what actually builds trust: the user can see the clock, not just be told one exists.
- Delay reason codes that tailor the message and get logged — this is the seed of root-cause analytics
  (which carrier, which lane, which failure mode is driving WISMO volume) without overbuilding it.
- A two-tap feedback capture after resolution — cheap to build, and it's the difference between shipping a flow
  and shipping a flow you can prove is working.

**Still not built in this prototype (and not in v1, deliberately):**
- Predictive delay detection *before* the window is breached (Task 3's AI opportunity) — this prototype is
  the deterministic v1 + dispute/recovery/feedback layer; prediction is a v2.5/v3 layer once the reactive
  trigger and feedback loop are proven in production.
- Compensation tiers beyond a flat delay credit, and any tuning of the credit amount by order value.
- Multi-language message variants.

The goal of this version is still to never leave a user silently waiting — and now also to never let a
"resolved" ticket close without knowing whether it was actually resolved well.
""")
