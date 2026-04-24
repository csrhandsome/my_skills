---
name: ai-draw-skills
description: Create publication-style AI research figures and architecture diagrams for CCF/AI conference papers. Use when the user needs a clean system diagram, method overview, training-vs-inference pipeline, module interaction figure, or a small set of scientific illustrations generated from a textual description.
---

# AI Draw Skills

Use this skill when:
- The user wants a paper-style architecture diagram, pipeline figure, framework overview, or method illustration.
- The target style is close to CCF / AI conference figures: clean, structured, white background, readable labels, restrained color palette.
- The result should be generated from a textual description and saved under this skill's local `img/` directory.

# Path Rules

- Treat the directory containing this `SKILL.md` as `AI_DRAW_SKILL_DIR`.
- Read configuration from `"$AI_DRAW_SKILL_DIR/config.json"`.
- Generate images with `"$AI_DRAW_SKILL_DIR/scripts/generate_image.py"`.
- Save all final outputs to `"$AI_DRAW_SKILL_DIR/img/"`.
- Do not write final images to the repo root or other temporary folders unless the user explicitly asks for that.

# Core Workflow

## 1. Analyze the architecture before drawing

Convert the user's description into a structured diagram plan before writing any image prompt.

You must identify:
- The main goal of the figure.
- The major modules or stages.
- Input and output artifacts.
- Data / feature / control flow directions.
- Whether training and inference should be separated.
- Whether the figure is one overview or a small set of related subfigures.

If the description is incomplete, infer the missing pieces from standard AI paper patterns and state the assumptions briefly.

## 2. Choose the diagram form

Pick the diagram family that matches the content:
- End-to-end pipeline: left-to-right flow with clear stage boundaries.
- Framework overview: grouped blocks with one central method and side components.
- Training vs inference: two aligned lanes with shared modules highlighted.
- Multi-branch model: parallel towers, fusion block, and output heads.
- Agent / planner / executor system: controller at top, tools or workers below, arrows for dispatch and feedback.

## 3. Choose ratio and visual parameters

Adjust the figure shape to the content instead of using one fixed ratio.

Use these defaults unless the user requests otherwise:
- Wide pipeline: `16:9`
- Balanced overview: `4:3` or `3:2`
- Tall staged workflow: `3:4`
- Square concept figure: `1:1`

For publication-style results:
- Use a white or very light background.
- Use flat vector-like shapes, not photorealistic rendering.
- Keep the palette restrained: 2-4 accent colors plus neutral grays.
- Keep arrows and connectors consistent.
- Prefer high legibility over decoration.
- Avoid fake UI chrome, glossy effects, 3D gimmicks, and dense text walls.

## 4. Build the generation prompt

The prompt should contain:
- Figure purpose.
- Exact modules and their order.
- Relative layout.
- Arrow semantics.
- Style constraints.
- Ratio / size hints.
- Explicit negative constraints.

Prompt template:

```text
Create a clean AI research architecture diagram for a conference paper.
Goal: <what this figure explains>.
Layout: <left-to-right / top-down / two-lane / multi-branch>.
Modules: <ordered list of blocks>.
Flow: <how information moves between blocks>.
Emphasis: <core module or novelty>.
Style: white background, vector-like scientific illustration, flat design, publication-ready, clear labels, consistent arrows, restrained blue/teal/orange palette, no photorealism, no mock UI, no extra decoration.
Aspect ratio: <ratio>.
```

## 5. Generate into `img/`

Default command:

```bash
AI_DRAW_SKILL_DIR="[directory containing this SKILL.md]"
uv run python "$AI_DRAW_SKILL_DIR/scripts/generate_image.py" \
  "<final prompt>" \
  -o "$AI_DRAW_SKILL_DIR/img/architecture_v1.png"
```

The script reads `config.json` as `defaults + targets`.
- `defaults.target` selects the route used when no target is specified.
- Use `--target <name>` to switch relays or providers.
- `--model` is kept as a compatibility alias for `--target`.

If the user wants Gemini:

```bash
AI_DRAW_SKILL_DIR="[directory containing this SKILL.md]"
uv run python "$AI_DRAW_SKILL_DIR/scripts/generate_image.py" \
  "<final prompt>" \
  --target gemini-3-pro-preview \
  --aspect-ratio 16:9 \
  --image-size 2K \
  -o "$AI_DRAW_SKILL_DIR/img/architecture_v1.png"
```

For OpenAI-compatible models, tune with:
- `--size`
- `--quality`
- `--output-format`

For Gemini, tune with:
- `--aspect-ratio`
- `--image-size`

# Output Rules

- Final output paths must be inside `ai_draw_skills/img/`.
- Use clear file names such as:
  - `method_overview_v1.png`
  - `training_inference_split_v1.png`
  - `multi_agent_architecture_v2.png`
- If the user asks for a set, generate a small consistent series rather than unrelated variants.

# Quality Bar

Before finishing, check:
- The module order matches the user description.
- The main contribution is visually emphasized.
- Labels are not tiny or overcrowded.
- The ratio matches the content density.
- The figure reads like a paper figure, not a poster ad or concept art.
- The file is present in `ai_draw_skills/img/`.

# Failure Handling

- If the request is too vague to identify modules, ask for the missing structure.
- If generation fails, report the exact API or routing error.
- If the first image is structurally wrong, revise the prompt based on architecture errors first, not cosmetic tweaks.
