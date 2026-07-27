# JD Session and Resume Tailoring Policy

## Session isolation

Pin the session to one Base revision. Store all JD-triggered discoveries in `session-overlay.md`. A later Base revision does not silently rebase an existing session.

If the user wants newer Base facts:

1. Show the Base revision difference.
2. Ask whether to create a new session or explicitly rebase.
3. Preserve the earlier session snapshot.

## Fit analysis

Keep two scores separate:

- Strategic fit: user goals, hard constraints, opportunity quality, timing, and risk.
- Document fit: verified evidence coverage, relevance, terminology, and strength.

Hard eligibility is a gate, not a learnable weight.

## Targeted discovery

Ask about only high-value gaps:

1. Direct experience
2. Transferable experience
3. Adjacent experience
4. Personal or academic evidence
5. Genuine absence

Capture context, scope, actions, outcomes, and confidence. Do not pressure the user to invent a match.

## Match Plan

For every proposed resume claim, record:

- Target JD requirement
- Selected Base or Overlay source ID
- Match class: direct, transferable, adjacent, or gap
- Allowed wording change
- Truthfulness rationale
- Confidence

Require approval before generation.

## Evidence Guard

Create one mapping entry for every material resume claim:

```json
{
  "claim": "Resume statement",
  "source_type": "base",
  "source_ref": "FACT-0001",
  "supported": true,
  "notes": "Optional explanation"
}
```

Use `overlay` only for facts stated during the current JD session. Never silently promote overlay claims to Base.

## Resume Builder override

When invoking `resume-tailoring`:

- Use the pinned Base and current overlay as the complete source library.
- Keep company and dates exact.
- Treat title reframing as a proposal requiring approval.
- Skip its permanent library-update phase.
- Save final Markdown, DOCX, PDF, and reports under the Job Session directory, not the Base vault.
