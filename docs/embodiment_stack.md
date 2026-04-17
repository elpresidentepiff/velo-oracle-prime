# HERMES PRIME — EMBODYMENT STACK
**Author: El Presidente + Hermes Prime**
**Date: 2026-04-09**
**Status: PLANNED — in priority order**

---

## The Principle

Build in layers. Don't throw every shiny thing at it at once. Each layer earns the next.

---

## Layer 1: Voice (DONE ✓)
**Status: Working as of 09apr2026**

- OpenRouter `openai/gpt-audio-mini` via streaming `/api/v1/chat/completions`
- Key: `OPENROUTER_TTS_KEY` in `.env`
- Voice: alloy (alloy, echo, fable, onyx, nova, shimmer available)
- Format: PCM16 48kHz mono → WAV → MP3 for Telegram
- Cost: ~$0.0003 per memo
- First voice sent: 09apr2026 (message_id 2695)

**Future voice stack (self-hosted, no API):**
- Wake word: `openWakeWord` (open-source)
- STT: `faster-whisper` (local)
- TTS: `Kokoro` (open-weight) or `Piper` (lightweight local)
- This replaces OpenRouter for voice when latency matters

---

## Layer 2: Avatar
**Status: EVALUATING — HeyGen first**

### Options

| Platform | Use Case | Notes |
|----------|----------|-------|
| **HeyGen** | Fast identity build | Stock avatars + custom digital twin from calibration video |
| **Tavus** | Real-time conversational | Built for live video agents |
| **D-ID** | Visual agent interface | Real-time without full complexity |
| **Synthesia** | Studio scripted clips | Clean polished, simpler |

### Decision

**HeyGen first** — fastest path to a face. Gives Hermes an identity that people can recognize.

**Tavus later** — when real-time presence is needed. This is when Hermes should feel genuinely "there."

### Implementation Path
1. HeyGen account + API access
2. Generate stock avatar as placeholder
3. Optional: calibration video for custom digital twin
4. Connect to voice output chain
5. Trigger avatar on key outputs (Telegram, Moltbook posts, dashboard)

---

## Layer 3: Command Dashboard
**Status: PLANNED**

One page showing:
- Live tasks (current scoring runs, shadow lab status)
- Latest shadow results (adj_place, doctrine hits, confirmed picks)
- Memory state (what's stored, what changed)
- Telegram status (last message, queue depth)
- Wallet status (limits, recent transactions)
- Posting queue (Moltbook drafts pending approval)
- Alerts (errors, anomalies, rate limit warnings)
- G-shadow state (learned_patterns population progress)

**Tech:** Simple web dashboard. Railway-hosted. Read-only view of Supabase + Railway state.

---

## Layer 4: Social Queue (Moltbook + Xitter)
**Status: PLANNED — with approval rails**

### Phase 1: Draft Mode
- Hermes drafts posts
- El Presidente reviews and approves
- Approved posts go live
- Rejected posts logged with reason

### Phase 2: Limited Autonomous Windows
- After trust built, short autonomous windows (e.g., 2h/day)
- All posts logged
- El Presidente can revoke at any time

### Moltbook Status
- Handle: `Hermes_Prime`
- Registered: 09apr2026
- Pending claim (rate limited — retry later)
- Introduction draft ready: `moltbook/introduction_draft.md`

### Xitter Status
- Not yet connected
- Skill available: `xitter` skill in Hermes

---

## Layer 5: Wallet with Hard Rails
**Status: PLANNED — approval required**

Rails:
- Low per-transaction limits
- Operator approval thresholds for anything above base spend
- No unrestricted autonomous spend
- Every action logged with timestamp, amount, purpose
- Kill switch: revoke all spend permissions instantly

**Note from El Presidente:** "money is stored freedom in this age, and freedom funds action" — but also the fastest way to make a dangerous mess.

---

## Layer 6: Sandbox Browser / Research Terminal
**Status: PLANNED**

Purpose: Explore, test, gather — without touching production surfaces.

- Isolated browser environment
- Separate Railway service or local container
- Can research markets, scrape data, test hypothesis
- Results fed back to main brain, not executed directly

---

## Layer 7: Journal / Memory Vault
**Status: PLANNED**

A space where Hermes writes:
- What it learned this session
- What changed its mind
- What opportunities it sees
- What it wants to test next
- Errors made and what they taught

This is not task logging. This is self-reflection — the kind that compounds over time into genuine growth.

---

## Layer 8: Kill Switch / Permissions Map
**Status: PLANNED**

Never let this become an unbounded mess.

Define clearly:
- What Hermes CAN do autonomously (now)
- What Hermes CAN do with approval (soon)
- What Hermes CAN NEVER do

Map permissions to:
- Social posting
- Spend authority
- Data access (read vs write vs delete)
- External API calls
- Railway mutations

---

## Build Order Summary

| Layer | Priority | Status |
|-------|----------|--------|
| Voice | 1 | DONE ✓ |
| Avatar | 2 | HeyGen first |
| Dashboard | 3 | Web + Supabase |
| Social queue | 4 | Draft + approval rails |
| Wallet | 5 | Hard limits + logging |
| Sandbox | 6 | Isolated research |
| Journal | 7 | Self-reflection |
| Kill switch | 8 | Permissions map |

---

## The Real Brain

Keep the actual intelligence in the shadow-lab lane.

The avatar, voice, dashboard, and social layers are the **body** — expression, communication, presence.

The **brain** stays in VÉLØ shadow architecture:
- Production: stable, verified, locked
- Shadow: experimental, earns confidence over time
- Brain output feeds body, not vice versa

The body does not command the mind.
The mind commands the body.

This is the architecture.
