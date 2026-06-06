---
name: scienticfic-abstract-skills
description: Write or revise top-tier conference paper introductions and abstract-style paper openings, especially for CV/AI papers. Use when the user asks for 顶会引言, introduction writing, abstract/introduction polishing, motivation framing, contribution writing, or Figure 1 motivating-example guidance.
---

# Scientific Abstract And Introduction Writing

Use this skill to write, revise, or critique a top-tier conference paper opening. Despite the skill name, prioritize **conference-style introduction structure** unless the user explicitly asks for only a short abstract.

## Core Structure

Use the progression:

1. **Background**: Open with a field consensus, not a generic statement. In 1-2 sentences, identify the broad area and why the reader should care.
2. **Problem**: Narrow from the broad field to the specific technical problem the paper addresses.
3. **Limitations**: Group prior work into 2-3 categories, acknowledge their contributions, then state their shared limitations.
4. **Solution**: State the key insight first, explaining why the proposed direction should work, then describe how the method implements it.
5. **Contributions**: End with a concise contribution list and a brief paper-organization sentence.

Each paragraph should do exactly one job. The logic must move forward; do not repeat motivation, limitation, or contribution claims across paragraphs.

## Paragraph Rules

- Every paragraph must be narrower and more specific than the previous one.
- Start from a recognized domain consensus and focus toward the paper's concrete research question.
- Use one sentence to explicitly state what existing methods cannot do, so the reader does not have to infer the gap.
- Explain **why** the proposed idea is effective before explaining **how** it is implemented.
- Include one clear **key insight** sentence that captures why the method works at a conceptual level.
- Keep related work lightweight: only discuss prior work that directly supports the motivation. Do not turn the introduction into a Related Work section.
- Acknowledge prior work before pointing out limitations. Avoid dismissive language such as "fail to", "ignore", "simply", "naive", or "obviously".
- For CV papers, consider a Figure 1 that shows either the pipeline or a motivating example. Mention what Figure 1 should reveal if the user asks for figure guidance.

## Citation Rules

- Each introduction paragraph should include at least 1-2 citations.
- Key claims require citations, especially claims about field consensus, dominant paradigms, limitations of prior methods, benchmarks, or empirical trends.
- Prefer citing representative work for each prior-work category instead of listing papers one by one.
- If citations are missing from the user's material, mark placeholders like `[cite: representative diffusion policy work]` rather than inventing bibliographic details.

## Prior Work Grouping

When discussing existing methods:

1. Identify 2-3 method families.
2. For each family, briefly state what it contributed.
3. Then state the common limitation relevant to this paper's motivation.
4. Avoid chronological or paper-by-paper enumeration.

Example pattern:

```text
Existing approaches largely follow three lines: <family A>, <family B>, and <family C>. The first has made progress in <strength>, while the second and third improve <strengths>. However, these lines share a common limitation: <specific missing capability>, which becomes critical when <paper-specific setting>.
```

## Output Template

When drafting an introduction, use this shape unless the target venue or user request requires otherwise:

```markdown
Paragraph 1 - Background:
<field consensus and broad importance, 1-2 attention-locking sentences, with citations>

Paragraph 2 - Problem:
<narrow to the concrete task, setting, bottleneck, or evaluation gap, with citations>

Paragraph 3 - Limitations:
<2-3 categories of prior work, acknowledged strengths, shared limitation, with citations>

Paragraph 4 - Solution:
<key insight first, then proposed method at a high level, optionally referencing Figure 1>

Paragraph 5 - Contributions:
Our contributions are:
1. <contribution 1>
2. <contribution 2>
3. <contribution 3>

The remainder of this paper is organized as follows: <brief organization sentence>.
```

## Revision Checklist

Before finalizing, verify:

- The opening is specific to the domain, not a generic "recent advances have..." start.
- The broad-to-specific narrowing is visible paragraph by paragraph.
- The gap is stated in one direct sentence.
- The key insight appears before method details.
- Prior work is grouped into 2-3 categories and not listed paper by paper.
- Every paragraph has citation support or marked citation placeholders.
- Contributions are concrete, non-overlapping, and testable.
- The ending includes both contribution bullets and paper organization.
- For CV/top-conference papers, Figure 1 is considered as a pipeline or motivating example.

