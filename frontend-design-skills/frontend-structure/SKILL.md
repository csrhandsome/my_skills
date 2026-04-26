---
name: frontend-structure
description: Create and enforce the source structure for data visualization pages in Vite React TypeScript projects using Tailwind CSS, Recharts-first charts, clear data hooks, and standard component boundaries. Use after requirements and data analysis are available, or when the user asks to structure the visualization page, wire data into components, or create the standard frontend files.
---

# Frontend Structure

Use this skill to create the source structure and file boundaries for the visualization page after the design direction and data shape are known.

Default stack:

- React + TypeScript
- Tailwind CSS for all styling
- Recharts for standard charts
- D3 only when Recharts cannot reasonably handle the required layout, scale, geometry, or interaction

## Required Project Structure

Create this structure before implementation if it is missing:

```text
src/
  components/
    charts/
    filters/
    layout/
  hook/
  lib/
    data/
  page/
  types/
  assets/
    data/
```

Do not store project template files inside this skill. This skill only defines the target structure and file responsibilities. When the skill is used, create the directories and files inside the target Vite project, then fill them according to the confirmed requirements and data-analysis results.

## Structure Workflow

1. Confirm the target project root:
   - It should contain `package.json`, `src/`, and Vite config.
   - If the environment is missing, use `environment-build-up` first.
2. Read prior context:
   - Use the confirmed brief from `design-requirements` if available.
   - Use field, file, and loading recommendations from `data-analyze` if available.
3. Ensure dependencies:
   - `recharts`
   - `react-is`
   - Tailwind already configured via `@tailwindcss/vite`
   - `xlsx` only if the frontend must parse CSV/XLS/XLSX directly at runtime; otherwise keep SheetJS in analysis/build scripts.
4. Create the required directories with `mkdir -p`.
5. Create these structure files in the target project if equivalent files do not already exist:
   - `src/page/DataVizPage.tsx`
   - `src/hook/useVisualizationData.ts`
   - `src/components/charts/TrendChart.tsx`
   - `src/components/charts/CategoryBarChart.tsx`
   - `src/components/filters/FilterBar.tsx`
   - `src/components/layout/PageShell.tsx`
   - `src/lib/data/normalize.ts`
   - `src/types/visualization.ts`
6. Update `src/App.tsx` to render `DataVizPage` unless the project already has routing.
7. Fill the files with the actual data model, chart requirements, and page content from prior analysis.
8. Run verification:
   - `pnpm run build`
   - Start the Vite dev server when the user needs a preview.

## Data Loading Rules

Keep data loading explicit and easy to audit:

- Small files in `src/assets/data/`: import them directly or use a typed local module.
- Larger files in `public/data/`: fetch them from `/data/file.ext`.
- Put normalization, aggregation, and field coercion in `src/lib/data/`.
- Put React loading state, filter state, and view-model assembly in `src/hook/useVisualizationData.ts`.
- Pass prepared arrays into chart components; do not make chart components parse raw files.

The hook is the bridge between prior data analysis and the UI. It should expose:

- Raw or normalized rows.
- Filter state and setters.
- Chart-ready series.
- Metric summaries.
- Loading and error states when data is fetched.

## Component Responsibilities

- `src/page/DataVizPage.tsx`: main page composition. It calls the hook and passes prepared data to components.
- `src/hook/useVisualizationData.ts`: data loading, filtering, aggregation, and chart view models.
- `src/components/charts/`: presentational Recharts components. No file parsing here.
- `src/components/filters/`: filter controls, search, toggles, selects, date range controls.
- `src/components/layout/`: page shell, sections, metric rows, responsive layout primitives.
- `src/lib/data/`: pure data utilities, no React.
- `src/types/`: shared TypeScript types.

## Styling Rules

- Use Tailwind classes as the primary styling mechanism.
- Avoid separate CSS files except for Tailwind import, reset needs, or third-party fixes.
- Build a real data product surface, not a marketing landing page.
- Keep dashboards dense but readable.
- Use chart titles, axis labels, units, legends, and tooltips when they improve understanding.
- Include loading, empty, and error states for fetched data.
- Avoid card nesting and decorative clutter.

## Structure Creation Rules

When creating files in the target project:

- Create directories with `mkdir -p`.
- Create only files that are needed for the current page.
- Use `src/page/DataVizPage.tsx` as the main page that calls hooks and composes components.
- Use `src/hook/useVisualizationData.ts` to load, normalize, filter, and expose data to components.
- Keep chart components presentational and typed.
- Rename titles, labels, metrics, and field names to match the user's data.
- Add filters only when they answer the brief.
- Prefer fewer meaningful charts over many weak charts.
- Keep implementation local to the visualization app unless the user asks for shared packages.

## Handoff

After implementation, report:

- Files created or changed.
- How data is loaded.
- Which charts were implemented.
- Verification result.
- Dev server URL if started.
