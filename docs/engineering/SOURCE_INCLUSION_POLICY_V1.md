# Source Inclusion Policy V1

## Purpose

VÉLØ uses multiple racing data sources, but it does not blindly merge them. Every source has a lane.

## Source Roles

| Source | Role | Live Scoring |
| --- | --- | --- |
| Racing Post account archive | Deep context, dossiers, comments, pedigree, entries, quotes, notes, newspaper/tip heat. | No |
| Racing API | Identity, race/result structure, IDs, fallback/cross-check. | Only existing approved structured fields |
| VÉLØ | Independent probability, tiers, MDS, improvement, router outputs. | Yes |
| Sigma | Outcome truth and miss taxonomy. | Post-race only |
| RPDC | Memory and historical horse behaviour. | Shadow/research unless already approved |

## Explicit Field Policy

| Field / Group | Policy |
| --- | --- |
| RPR | `ARCHIVE_ONLY`; banned from live VÉLØ scoring and VP/improvement/model/router/staking/Telegram picks. |
| RP comments / Spotlight / Newspaper Form | Archive/context only; useful for explanation, watchlists, and contradiction intelligence. |
| Tip count | Archive/context/hype warning only; not a truth signal. |
| Trainer / jockey / owner / sire / dam | Archive/context; shadow research only until proven and approved. |
| Headgear / wind surgery | Archive/context; shadow research candidate. |
| Racing API IDs/results | Identity/truth layer. |
| VÉLØ scores | Independent decision layer. |
| Sigma result | Post-race truth only. |

## Promotion Gates

No archive field can enter live scoring without:

1. Evidence from archive context value tests.
2. Leakage audit.
3. Shadow-only trial.
4. Operator/Council approval.
5. Explicit code review confirming no RPR or RP opinion leakage.

## Current Decision

Racing Post archive data prepares, challenges, and explains VÉLØ. It does not steer the engine.
