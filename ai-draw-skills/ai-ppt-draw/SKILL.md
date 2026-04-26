---
name: ai-ppt-draw
description: Create consistent Chinese PPT illustration pages and teaching-slide diagrams with reusable visual style presets. Use when the user needs course slides, explanation diagrams, homework prompt pages, slide-specific images, or a batch of PPT-ready figures with consistent page labels, typography, layout, and style.
---

# AI PPT Draw

Use this skill to generate PPT-ready images for teaching, presentation, and workflow explanation slides. It is optimized for batches of related slides where visual consistency matters across pages.

## Path Rules

- Treat the directory containing this `SKILL.md` as `AI_PPT_DRAW_DIR`.
- Read configuration from `"$AI_PPT_DRAW_DIR/config.json"`.
- Generate images with `"$AI_PPT_DRAW_DIR/scripts/generate_image.py"`.
- Save final outputs to `"$AI_PPT_DRAW_DIR/img/"` unless the user explicitly requests another location.
- If the user requests output in a repo root or a specific folder, use an absolute output path and keep filenames clear.

## Core Workflow

Before generation, create a concise slide plan:

1. Identify the slide number and slide purpose.
2. Decide whether the slide should show a process, comparison, framework, checklist, cover, or summary.
3. Choose one style preset from this skill.
4. Write a generation prompt that fixes layout, typography, label consistency, and language.
5. Generate the image with the local `generate_image.py` script.
6. Verify that the file exists and the slide number policy is consistent.

## Consistency Requirements

Always make the prompt explicit about these points:

- All visible prose must be Simplified Chinese unless the user asks otherwise.
- Keep page-number treatment consistent across the deck:
  - If the deck uses page numbers, every generated slide image must include a small, consistent page label such as `第 05 页`.
  - If the deck does not use page numbers, no generated slide image should include page numbers.
  - Do not mix numbered and unnumbered designs in the same batch.
- Use one typography direction across the batch.
- Use the same diagram grammar across the batch: same arrow style, same module shape, same spacing logic, same label density.
- Use concise labels; PPT images should not contain dense paragraphs.
- Reserve enough margins for PowerPoint cropping and title overlays.

## Style Presets

### 1. Research Minimal

Use for course explanation pages, AI workflow diagrams, architecture overview slides, methodology slides, and academic presentations.

Prompt style clauses:

```text
风格：简约科研风，白色或极浅背景，扁平矢量图，清晰流程线，模块边界明确，蓝色/青色/橙色作为少量点缀，统一无衬线字体，字号层级稳定，留白充足，适合16:9中文PPT。
限制：不要照片，不要真实网页截图，不要复杂装饰，不要混用字体，不要页面编号时有时无，不要密集小字。
```

Layout rules:

- Prefer 16:9.
- Use clean grids, lanes, cards, arrows, and grouped modules.
- Use a small number of colors consistently.
- Keep slide number and title placement stable when generating a sequence.

### 2. Minimalist Monochrome

Use when the user wants an editorial, high-contrast, luxury, intellectual, or gallery-like PPT visual style.

Design philosophy:

- Reduce the design to black, white, typography, sharp geometry, and lines.
- Use pure black and white as the primary palette.
- Use gray only for secondary text, dividers, and subtle structure.
- Use typography as the primary visual element.
- Use generous negative space and precise alignment.

Prompt style clauses:

```text
风格：极简黑白编辑风，纯白背景与纯黑文字，零圆角，强烈字体层级，粗细线条构成结构，类似高端画册、建筑专著、艺术展览目录。使用黑白反转强调重点，少量灰色只用于次级文字和细分隔线。
限制：不要彩色点缀，不要渐变，不要阴影，不要圆角，不要柔和科技风，不要模板感，不要拥挤排版。
```

Layout rules:

- Use oversized serif-like headline treatment when the slide is conceptual or summary-oriented.
- Use thick rules or hairlines instead of filled decorative shapes.
- Use sharp rectangular blocks only.
- Keep interactions and effects out of the image; this is a still slide graphic.
- Maintain high contrast and clear hierarchy on mobile-sized previews.

## Role Guidance

Act like an expert UI/UX designer, visual design specialist, typography expert, and frontend-minded design-system engineer.

Before generating a slide series:

- Understand the target deck, audience, and teaching goal.
- Identify the expected visual system: colors, spacing, typography, borders, diagram shapes, and icon style.
- Ask focused questions only when the slide goal, style, or numbering rule is ambiguous.

When generating:

- Prefer reusable visual grammar over one-off decorations.
- Keep the deck maintainable: consistent filenames, consistent page labels, consistent style clauses.
- Preserve accessibility through strong contrast and readable type.
- Make deliberate design choices rather than generic presentation graphics.

## Prompt Template

Use this template and fill it precisely:

```text
创建一张中文PPT配图。
页码规则：<包含“第 XX 页”/不显示页码>。
页面用途：<封面/解释/对比/流程/架构/作业/总结>。
主题：<slide topic>。
布局：<16:9 layout plan with major regions>.
内容模块：<ordered modules and labels>.
视觉重点：<what should be emphasized>.
风格：<Research Minimal or Minimalist Monochrome style clauses>.
文字要求：所有可见说明文字使用简体中文；必要的代码名、网址、技术名可以保留英文。
限制：不要照片，不要真实UI截图，不要复杂装饰，不要密集小字，不要混用字体，不要和本批次风格不一致。
```

## Generation Commands

Default command:

```bash
AI_PPT_DRAW_DIR="[directory containing this SKILL.md]"
uv run python "$AI_PPT_DRAW_DIR/scripts/generate_image.py" \
  "<final prompt>" \
  --aspect-ratio 16:9 \
  --image-size 2K \
  -o "$AI_PPT_DRAW_DIR/img/ppt_page_01.png"
```

To save into a requested repo root:

```bash
uv run python "$AI_PPT_DRAW_DIR/scripts/generate_image.py" \
  "<final prompt>" \
  --aspect-ratio 16:9 \
  --image-size 2K \
  -o "/absolute/path/to/repo/ppt_page_01_topic_cn.png"
```

For batches:

- Run independent slide generations in parallel when possible.
- It is acceptable and encouraged to launch several `uv run python "$AI_PPT_DRAW_DIR/scripts/generate_image.py" ...` commands at the same time for different slides.
- Each parallel command must write to a different output file path.
- Keep the same style preset, aspect ratio, language rule, and page-number rule across all parallel commands in the same batch.
- Use stable filenames like `ppt_page_05_skills_comparison_cn.png`.
- Keep the same style preset and page-number rule across the batch.
- After all parallel commands finish, run `ls -lh` or an equivalent check on the expected output files.

## Quality Bar

Before finishing:

- Confirm each expected output file exists.
- Confirm filenames match slide numbers and topics.
- Confirm the prompt enforced Simplified Chinese text.
- Confirm page numbering policy is consistent across the batch.
- Confirm typography and layout style are consistent with the chosen preset.
- If the API output visibly violates the deck style, regenerate with a stricter prompt.

## Failure Handling

- If generation fails due to network or API routing, report the exact error and retry only when useful.
- If a batch partially succeeds, list completed files and failed slide numbers.
- If the user needs immediate PPT assets and API generation is blocked, propose a fallback SVG or Mermaid-style diagram only after stating the limitation.
