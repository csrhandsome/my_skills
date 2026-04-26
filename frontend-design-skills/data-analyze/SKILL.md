---
name: data-analyze
description: Inspect frontend data files for visualization projects and summarize CSV, XLSX, and XLS usability with SheetJS. Use when the user says they placed data, asks to check data files, wants to use CSV/Excel data for a page, or asks what is inside src/assets/data or public/data before building charts.
---

# Data Analyze

Use this skill to confirm that visualization data exists, decide how it should be loaded by a Vite frontend, and understand its structure well enough to recommend charts.

Only support these data formats by default:

- `.csv`
- `.xlsx`
- `.xls`

Use one Node data parsing tool for all three formats: SheetJS via the `xlsx` package.

## Bundled Scripts

Use the scripts in `scripts/` when the user wants repeatable data checks or Excel conversion. Run them from the target Vite project root, or pass the project root as an argument. These scripts load `xlsx` from the target project, so install it there with `pnpm install xlsx` when needed.

- `scripts/data-check.mjs`: scan `src/assets/data/` and `public/data/`, list supported files, sample fields, infer types, report quality signals, and suggest charts.
  ```bash
  node /path/to/data-analyze/scripts/data-check.mjs
  node /path/to/data-analyze/scripts/data-check.mjs ./d3_demo --sample 200
  ```
- `scripts/xlsx-to-csv.mjs`: convert `.xlsx` or `.xls` sheets to `.csv`, usually into `public/data/`.
  ```bash
  node /path/to/data-analyze/scripts/xlsx-to-csv.mjs public/data/sales.xlsx
  node /path/to/data-analyze/scripts/xlsx-to-csv.mjs raw/sales.xls --out public/data --sheet Sheet1
  ```

## Workflow

1. Locate the project root:
   - Prefer the current directory if it contains `package.json`.
   - Otherwise search nearby directories for the Vite project the user named, commonly `d3_demo`.
   - Run data parsing commands from the project root so local dependencies resolve from that project's `node_modules`.
2. Check data directories:
   - `src/assets/data/`
   - `public/data/`
3. Use shell tools first to inspect availability:
   ```bash
   ls -lah src/assets/data public/data
   find src/assets/data public/data -maxdepth 2 -type f
   du -h path/to/file
   file path/to/file
   head -n 5 path/to/file
   ```
   Use commands that make sense for existing paths; do not fail the whole workflow just because one data directory is missing.
4. Report every supported file found:
   - Relative path
   - Size
   - Extension
   - Recommended frontend loading method
5. If no supported files exist, tell the user plainly:
   - Put small static example/mock data under `src/assets/data/`.
   - Put larger data or data loaded with `fetch` under `public/data/`.
6. Ensure SheetJS is available in the target project:
   - Check `package.json` for `xlsx`.
   - If absent and the user wants analysis now, install it from the project root:
     ```bash
     pnpm install xlsx
     ```
   - Do not install `xlsx` in the skills repository unless that repository is the target visualization project.
7. Prefer `scripts/data-check.mjs` for a repeatable inspection report.
8. Use `scripts/xlsx-to-csv.mjs` when Excel files should be converted before frontend use.
9. Summarize field types, quality issues, and chart suggestions.

## Loading Recommendation Rules

Recommend `import` for:

- Files in `src/assets/data/`
- Small files under a few hundred KB
- Example data, mock data, and stable frontend fixtures

Recommend `fetch` for:

- Files in `public/data/`
- Files several MB or larger
- Files the app should load by URL, such as `/data/file.csv`

When a file is misplaced, say so and explain the better location. Example: a 10 MB CSV under `src/assets/data/` should usually move to `public/data/`.

## SheetJS Sampling

Use SheetJS to read `.csv`, `.xlsx`, and `.xls` consistently.

Use this pattern for quick inspection:

```js
import * as XLSX from "xlsx";

const workbook = XLSX.readFile(filePath, { cellDates: true });

for (const sheetName of workbook.SheetNames) {
  const sheet = workbook.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json(sheet, {
    defval: null,
    raw: false,
  });
  const preview = rows.slice(0, 100);
}
```

For Excel files, inspect every sheet name and row count. For CSV, SheetJS exposes the file as a workbook with a sheet; treat it the same way.

Avoid fully loading huge files into user-facing output. Sample enough rows to infer fields and quality, usually the first 100 rows plus basic row count when available.

## Field Type Inference

Infer each column as one of:

- `time`: date/time strings or Excel date cells.
- `number`: values that are mostly numeric after trimming commas, currency symbols, and percent signs.
- `category`: repeated strings with moderate unique count.
- `geo`: country, province, city, latitude/longitude, address, or region-like fields.
- `id`: unique or nearly unique identifiers, especially columns named `id`, `uuid`, `code`, `编号`, `学号`, or similar.
- `text`: long free-form text, notes, descriptions, or comments.
- `unknown`: too sparse or inconsistent to classify.

Mention uncertainty when sampling is too small or fields are mixed.

## Data Quality Checks

Check and report:

- Empty files or sheets.
- Missing values by important column.
- Duplicate rows or duplicate IDs when an ID-like field exists.
- Obvious outliers in numeric columns.
- Mixed date formats.
- Columns with mostly empty values.
- Excel workbooks with multiple sheets and which sheet appears most useful.

Keep findings practical for visualization. Do not overdo statistical analysis unless the user asks.

## Visualization Suggestions

Recommend charts based on inferred fields:

- Time + number: line chart or area chart.
- Category + number: bar chart.
- Category composition: horizontal bar chart first; pie chart only for a small number of categories.
- Two numbers: scatter plot.
- Geo field + number: map if the project supports geography; otherwise ranked bar chart.
- ID + many attributes: table with filters.
- Text-heavy data: table, search, tags, or aggregation before charting.

Prefer Recharts for standard charts. Mention D3 only when custom layouts, special interactions, or nonstandard visual encodings are needed.

## Output Format

Use this structure:

```text
数据检查结果：
- 找到 N 个支持的数据文件
- src/assets/data/demo.csv，48 KB，建议 import
- public/data/sales.xlsx，3.2 MB，建议 fetch('/data/sales.xlsx') 后解析，或在构建前转换为 JSON/CSV

数据结构理解：
- sales.xlsx / Sheet1：约 1200 行，12 列
- date：time，适合做 x 轴
- revenue：number，适合做指标和趋势
- category：category，适合分组对比

潜在问题：
- region 缺失较多
- amount 有少量异常大值

可视化建议：
- 收入趋势：折线图
- 品类对比：柱状图
- 明细查看：可筛选表格
```

If no data is present:

```text
没有发现可用的 .csv/.xlsx/.xls 数据文件。
小型示例数据放到 src/assets/data/。
较大或需要 fetch 的数据放到 public/data/。
```

## Boundaries

- Do not support Parquet, Arrow, SQLite, Zip, GeoPackage, or database connections in this skill.
- Do not silently add unrelated parsing libraries.
- Do not move or rewrite the user's data files unless explicitly asked.
- Do not treat a successful parse as proof the data is semantically correct; report sampling limits.
