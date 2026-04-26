---
name: start-data-viz
description: Start the data visualization page workflow after the frontend environment already exists. Use when the user wants to make a data visualization webpage from placed data, needs guidance from requirements through data analysis, page structure, visual design, and verification, and does not need Node/Vite/Tailwind environment setup.
---

# Start Data Viz

Use this skill as the entry point for building a data visualization page when the project environment is already prepared. Do not use this skill for installing Node, creating the Vite app, configuring Tailwind, or setting up pnpm.

## Assumption

Assume the target project already has:

- Vite + React + TypeScript
- Tailwind CSS configured
- Recharts and `react-is`
- Data directories such as `src/assets/data/` and `public/data/`

If the environment is missing, tell the user that `environment-build-up` is needed first, but do not run environment setup unless the user explicitly asks.

## Workflow

Run the workflow in this order:

1. Clarify requirements with `design-requirements`:
   - Confirm the page goal, audience, core message, style, interaction needs, and delivery context.
   - Produce a concise page design brief.
   - Ask the user to confirm the brief before implementation if major choices are still unclear.
2. Analyze data with `data-analyze`:
   - Check `src/assets/data/` and `public/data/`.
   - Use `scripts/data-check.mjs` when useful.
   - Confirm supported files: `.csv`, `.xlsx`, `.xls`.
   - Report loading method: small data import, larger data fetch.
   - Infer fields, data quality, and chart opportunities.
3. Create page structure with `frontend-structure`:
   - Create the standard directories and files in the target project.
   - Use `src/page/DataVizPage.tsx` as the main page.
   - Use `src/hook/useVisualizationData.ts` for loading, filtering, aggregation, and chart-ready data.
   - Keep charts, filters, layout, data utilities, and types separated.
4. Apply visual design with `frontend-design`:
   - Make the page feel like a real data product or presentation page according to the confirmed brief.
   - Use Tailwind as the styling system.
   - Keep charts readable, labeled, and purposeful.
5. Verify:
   - Run `pnpm run build`.
   - Start the dev server if the user needs to preview.
   - Check for broken data loading, empty charts, TypeScript errors, and obvious layout issues.

## Conversation Rules

- Do not skip directly to coding when the user's goal, audience, or data story is unclear.
- Do not re-run environment setup just because this workflow started.
- If the user says data is already placed, check the data directories before asking broad data questions.
- If no data is found, stop and tell the user where to place it:
  - Small example/mock data: `src/assets/data/`
  - Larger fetch-loaded data: `public/data/`
- If data is found but requirements are vague, use the data summary to ask more concrete design questions.

## Output Contract

At the end of a successful run, report:

- Confirmed page brief.
- Data files used and loading method.
- Main files created or changed.
- Charts and interactions implemented.
- Verification result.
- Dev server URL if started.

## Boundaries

- Do not install Node, pnpm, Vite, Tailwind, or Recharts in this skill.
- Do not create a new Vite project in this skill.
- Do not parse unsupported formats beyond `.csv`, `.xlsx`, and `.xls`.
- Do not make unrelated visual redesigns outside the data visualization page.
