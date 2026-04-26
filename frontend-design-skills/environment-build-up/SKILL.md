---
name: environment-build-up
description: Build a Vite React TypeScript data-visualization workspace with Node 24, pnpm, Tailwind CSS via @tailwindcss/vite, Recharts, react-is, and project guidance files. Use when the user asks to initialize or repair a frontend visualization environment, especially a d3_demo-style Vite project, and wants version checks before installing dependencies.
---

# Environment Build Up

Use this skill to initialize a React + TypeScript + Vite workspace for data visualization. The environment is intended for D3/Recharts-style visualization work, but the project directory name should be confirmed with the user before creation.

## Workflow

1. Confirm the project name before creating anything:
   - Explain briefly: this is a D3/data-visualization style React repository, and the directory name should match the user's topic or dataset.
   - Ask the user what they want to call the project if no name is provided.
   - Offer `d3_demo` only as a fallback example, not as an automatic default.
   - Prefer lowercase kebab-case names such as `sales-dashboard`, `city-data-viz`, or `student-score-viz`.
   - If the user gives a title with spaces or Chinese text, suggest a filesystem-safe kebab-case directory name and ask for confirmation.
   - Do not run `pnpm create vite` until the name is known or confirmed.
2. Inspect the current environment before installing anything:
   - Run `node -v`; if Node is already version 24.x, reuse it.
   - Run `npm -v`; if npm is present and compatible with the installed Node, reuse it.
   - Run `pnpm -v`; if pnpm is present, reuse it.
3. Install only missing or unsuitable tools:
   - On macOS, install `nvm` when needed:
     ```bash
     curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
     . "$HOME/.nvm/nvm.sh"
     nvm install 24
     ```
   - Verify Node and npm after installation:
     ```bash
     node -v
     npm -v
     ```
     Expected target versions from the user workflow are Node `v24.15.0` and npm `11.12.1`; accept newer compatible patch versions in the Node 24 line unless the user requires exact versions.
   - On Windows, direct the user to install Node from https://nodejs.org/en/download with the Windows installer, then verify `node -v` and `npm -v`.
   - Install pnpm only when missing:
     ```bash
     npm install -g pnpm
     pnpm -v
     ```
4. Create the Vite project when it does not already exist:
   ```bash
   pnpm create vite <project-name> --template react-ts --reactCompiler
   ```
   If the project directory already exists, inspect it and continue configuration rather than overwriting user work.
5. Enter the project directory and install visualization and styling dependencies:
   ```bash
   pnpm install recharts react-is
   pnpm install tailwindcss @tailwindcss/vite
   ```
6. Configure Tailwind in `vite.config.ts`:
   ```ts
   import { defineConfig } from 'vite'
   import react from '@vitejs/plugin-react'
   import tailwindcss from '@tailwindcss/vite'

   export default defineConfig({
     plugins: [
       react(),
       tailwindcss(),
     ],
   })
   ```
   Preserve existing Vite config entries such as aliases, server options, and test settings.
7. Import Tailwind in the app CSS file, usually `src/index.css`:
   ```css
   @import "tailwindcss";
   ```
   Make Tailwind CSS the project-wide styling approach. Avoid adding new traditional CSS rules unless they are necessary for resets, third-party integration, or a small unsupported edge case.
8. Ensure data directories exist:
   - `src/assets/data/`
   - `public/data/`
9. Write or update `CLAUDE.md` and `AGENTS.md` in the project root with the guidance in the next section.
10. Run a basic verification:
   - `pnpm install` if dependencies changed and no install was run.
   - `pnpm run build` when practical.
   - Start the Vite dev server if the user asked to preview the app.

## Project Guidance Files

Create both `CLAUDE.md` and `AGENTS.md` with equivalent guidance so Claude-style and Codex-style agents receive the same project rules.

Include these points:

- The environment is a Vite + React + TypeScript data-visualization project using pnpm.
- Styling must use Tailwind CSS as the default and primary styling system.
- The repository's purpose is data visualization. Keep data preparation, placement rules, and visualization-facing mock data in this project when they support frontend chart development.
- Use `src/assets/data/` for static, rarely changing, small data files under a few hundred KB. Vite can process these files, optimize them, and hot reload changes. This is appropriate for example data and development mock data.
- Use `public/data/` for static data that is several MB or larger, or data that should be loaded directly with `fetch`. Vite copies these files unchanged into the dist root, and they are available at URLs such as `/data/file.csv`.
- Prefer Recharts for standard charts. Add D3 only when custom layouts, scales, shapes, interactions, or data transforms justify it.
- Do not commit generated build output unless the user explicitly asks.

## User Data Handoff

After setup, tell the user exactly where to place data:

- Small example/mock data: `src/assets/data/`
- Larger fetch-loaded files: `public/data/`

If the user later says they have placed data, inspect both directories and report what files are present, including file sizes. If data is absent, say so plainly and repeat the placement paths.

## Existing Project Handling

When the project already exists:

- Check `package.json`, `vite.config.ts`, and the main CSS file before editing.
- Add missing dependencies and configuration without replacing unrelated user code.
- Preserve existing React plugin setup while adding `@tailwindcss/vite`.
- Create missing data directories and guidance files.
- Avoid deleting user assets or generated data.
