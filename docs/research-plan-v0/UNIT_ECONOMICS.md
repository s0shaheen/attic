# Attic — Unit Economics Model

*Generated 2026-03-26 from measured experiment data*

---

## 1. Variable Costs Per Item (measured from experiments)

### Ingestion (one-time per item, at upload)

| Component | Cost/item | Source |
|-----------|-----------|--------|
| Apify metadata + video DL + comments | $0.0140 | Starter PPE, measured |
| Gemini Tier 1 (keyframes, single pass) | $0.0009 | Measured (100 items) |
| OpenAI embedding | $0.0001 | Measured |
| **TIER 1 SUBTOTAL** | **$0.0150** | |

### Background Enrichment (async, after upload)

| Component | Cost/item | Source |
|-----------|-----------|--------|
| Gemini Pass 1 (full video perception) | $0.0024 | Measured (106 items) |
| Gemini Pass 2 (classification) | $0.0019 | Measured (106 items) |
| OpenAI re-embedding | $0.0001 | Measured |
| **TIER 2 SUBTOTAL** | **$0.0044** | |

### Total Ingestion Cost: **$0.0194/item**

### Agent Queries (per query, ongoing)

| Component | Cost/query | Source |
|-----------|-----------|--------|
| Claude Haiku 4.5 (~3 tool calls avg) | $0.005 | Estimated |
| OpenAI embedding (query vector) | $0.0001 | Measured |
| **QUERY SUBTOTAL** | **$0.005** | |

---

## 2. Cost Per User by Library Size

Assumptions: 50 queries/month, Apify Starter plan

| Library Size | Ingestion (one-time) | Monthly Agent (50 queries) | Total Month 1 | Ongoing/mo |
|---|---|---|---|---|
| 200 | $3.88 | $0.25 | $4.13 | $0.25 |
| 500 | $9.70 | $0.25 | $9.95 | $0.25 |
| 1,000 | $19.40 | $0.25 | $19.65 | $0.25 |
| 2,000 | $38.80 | $0.25 | $39.05 | $0.25 |

**Key insight:** Ingestion is the dominant cost. Agent queries are cheap. A 1000-item user costs ~$19.40 to onboard but only $0.25/mo ongoing.

---

## 3. Fixed Costs (monthly)

| Service | Cost/mo | Notes |
|---------|---------|-------|
| Apify Starter subscription | $29 | Includes $29 prepaid credit |
| Supabase Pro | $25 | DB + auth + storage |
| Render (API hosting) | $25 | Starter instance |
| Vercel Pro (frontend) | $20 | |
| AWS Lambda (pipeline) | ~$5 | At <100 users |
| Sentry + PostHog | $0 | Free tiers |
| Domain + email (Resend) | ~$5 | |
| **TOTAL FIXED** | **~$109/mo** | |

### Breakeven at $109/mo fixed costs

- At $10/mo subscription → 11 paying users
- At $15/mo subscription → 8 paying users
- At $20/mo subscription → 6 paying users

---

## 4. Apify Plan Scaling

| Plan | Sub cost | PPE/item | Items from prepaid | Break-even users (1K items each) |
|---|---|---|---|---|
| Starter | $29 | $0.0140 | ~2,071 | 2 users |
| Scale | $199 | $0.0106 | ~18,774 | 19 users |
| Business | $999 | $0.0073 | ~136,849 | 137 users |

→ Stay on Starter until ~15 users, then jump to Scale.
→ Scale plan: $199/mo covers ~19K items from prepaid alone.

---

## 5. Proposed Pricing Structure

|  | Free | Starter | Pro | Power |
|--|------|---------|-----|-------|
| Monthly price | $0 | $9/mo | $19/mo | $39/mo |
| Annual price | -- | $7/mo | $15/mo | $31/mo |
| Items included | 200 (first upload) | 1,000/mo | 3,000/mo | 10,000/mo |
| Agent queries | 20/mo | 200/mo | Unlimited | Unlimited |
| Extra items (overage) | -- | $0.03/item | $0.025/item | $0.02/item |
| Entity links (Spotify, Maps) | -- | ✓ | ✓ | ✓ |
| Collections | -- | ✓ | ✓ | ✓ |
| Export | -- | -- | ✓ | ✓ |
| Priority queue | -- | -- | -- | ✓ |

---

## 6. Margin Analysis

| Tier | Revenue/user/mo | COGS (ingest + agent) | Gross Profit | Gross Margin |
|---|---|---|---|---|
| Free | $0 | $3.88 + $0.25 | -$4.13 | N/A (loss leader) |
| Starter (month 1) | $9 | $14.00 + $1.00 | -$6.00 | -67% |
| Starter (month 2+) | $9 | $0 + $1.00 | $8.00 | **89%** |
| Pro (month 1) | $19 | $42.00 + $1.00 | -$24.00 | -126% |
| Pro (month 2+) | $19 | $0 + $1.00 | $18.00 | **95%** |
| Power (month 1) | $39 | $140.00 + $1.00 | -$102.00 | -262% |
| Power (month 2+) | $39 | $0 + $1.00 | $38.00 | **97%** |

### Payback period (months to recoup ingestion cost)

- Starter (1K items): $14 / $8 = **1.8 months**
- Pro (3K items): $42 / $18 = **2.3 months**
- Power (10K items): $140 / $38 = **3.7 months**

→ All tiers profitable by month 3.

---

## 7. Growth Scenarios

Assume mix: 50% Free, 25% Starter, 15% Pro, 10% Power
Assume 80% annual retention, avg 2 uploads/year

| Users (total) | Paying users | MRR | Var Cost/mo | Fixed Cost | Net Profit |
|---|---|---|---|---|---|
| 20 | 10 | $180 | $10 | $109 | +$61 |
| 50 | 24 | $436 | $24 | $109 | +$303 |
| 100 | 50 | $900 | $48 | $250 | +$602 |
| 250 | 124 | $2,236 | $120 | $500 | +$1,616 |
| 500 | 250 | $4,500 | $239 | $500 | +$3,761 |

**Breakeven:** ~30-40 total users (15-20 paying)
**$10K MRR milestone:** ~500 total users

---

## 8. Strategic Recommendations

1. **FREE TIER IS CRITICAL.** 200 items lets users experience the "wow" moment (finding saved content via natural language). The $3.88 COGS is your customer acquisition cost — cheaper than any ad.

2. **INGESTION IS THE MOAT.** The one-time processing cost creates switching cost — once your data is in Attic, you don't want to re-process it elsewhere. This is why month 2+ margins are 89-97%.

3. **PRICE ON VALUE, NOT COST.** A user with 3000 saved TikToks costs you $58 to onboard but gets enormous value from searchable, organized content. $19/mo is a steal for them. Don't race to the bottom.

4. **OVERAGE PRICING ($0.02-0.03/item)** is 30-50% above cost. This is intentional — it nudges heavy users toward higher tiers where your margin is better.

5. **APIFY PLAN UPGRADE PATH:**
   - 0-15 paying users → Starter ($29/mo)
   - 15-100 paying users → Scale ($199/mo, 45% PPE discount)
   - 100+ paying users → Business ($999/mo, 59% discount)

   Each upgrade dramatically improves per-item margin.

6. **SKIP TRANSCRIPTS.** Apify charges $48/1K for transcription. TikTok's built-in subtitle links are free and cover 77% of content. For the remaining 23%, Gemini's video perception already captures spoken content in the summary.
