# Application Tracking and Ranking Learning

## Application snapshot

Record:

- Opportunity ID and full JD snapshot
- Job Session ID
- Pinned Base revision
- Actual resume artifact and content hash
- Submission time and source
- Current stage
- Event timeline
- Notes and next action

Do not mark a prepared resume as submitted.

## Supported stages

| Stage | Learning signal | Eligible |
|---|---:|---:|
| `PREPARING` | 0 | No |
| `APPLIED` | 0 | No |
| `VIEWED` | +0.5 | Yes |
| `CONTACTED` | +1 | Yes |
| `WRITTEN_TEST` | +2 | Yes |
| `INTERVIEW_1` | +3 | Yes |
| `INTERVIEW_2` | +3.5 | Yes |
| `FINAL_INTERVIEW` | +4 | Yes |
| `OFFER` | +5 | Yes |
| `REJECTED_SCREEN` | -1 | Yes |
| `REJECTED_AFTER_INTERVIEW` | 0 | No |
| `NO_RESPONSE` | -0.5 | Yes after the configured wait |
| `WITHDRAWN` | 0 | No |
| `JOB_CLOSED` | 0 | No |

Do not infer `NO_RESPONSE` before the wait period. Do not interpret an interview-stage rejection as proof that the resume or role match was poor.

## Learnable features

- Role match
- Skill match
- Evidence strength
- Domain match
- Impact match
- Job freshness
- Source quality
- Location fit

Do not learn or modify hard eligibility, facts, evidence status, resume claims, or user preferences presented as constraints.

## Update protections

- Start automatic adjustment after three eligible applications.
- Use the latest eligible event per application.
- Apply Bayesian prior smoothing.
- Limit each feature's relative movement to 10% per revision.
- Normalize weights to 100%.
- Create an immutable scoring revision with reason and sample count.
- Allow activation of any earlier scoring revision.

Show “collecting samples” before the threshold rather than pretending the model has learned.

## Dashboard

Keep the backend read-only in V1. Use CLI or a verified source sync to record state changes. Show:

- Total applications and funnel stages
- Company, job, source, dates, current stage
- Actual resume path and pinned Base revision
- Opportunity scores
- Current weights, sample count, reason, and version
