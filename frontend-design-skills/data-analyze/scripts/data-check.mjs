#!/usr/bin/env node
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const DATA_DIRS = ["src/assets/data", "public/data"];
const SUPPORTED_EXTENSIONS = new Set([".csv", ".xlsx", ".xls"]);
const SMALL_FILE_LIMIT = 300 * 1024;

function usage() {
  console.log(`Usage:
  node scripts/data-check.mjs [project-root] [--sample 100]

Examples:
  node /path/to/data-analyze/scripts/data-check.mjs
  node /path/to/data-analyze/scripts/data-check.mjs ./d3_demo --sample 200

Notes:
  - Checks src/assets/data and public/data.
  - Supports .csv, .xlsx, and .xls.
  - Uses the target project's xlsx dependency: pnpm install xlsx
`);
}

function parseArgs(argv) {
  const args = {
    projectRoot: process.cwd(),
    sampleSize: 100,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--help" || token === "-h") {
      args.help = true;
    } else if (token === "--sample") {
      args.sampleSize = Number(argv[++index]);
    } else if (!token.startsWith("-")) {
      args.projectRoot = token;
    } else {
      throw new Error(`Unexpected argument: ${token}`);
    }
  }

  if (!Number.isInteger(args.sampleSize) || args.sampleSize < 1) {
    throw new Error("--sample must be a positive integer.");
  }

  return args;
}

function loadXlsx(projectRoot) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) {
    throw new Error(`No package.json found at ${projectRoot}. Pass the target Vite project root.`);
  }

  const requireFromProject = createRequire(packageJson);
  try {
    return requireFromProject("xlsx");
  } catch {
    throw new Error(`The target project does not have xlsx installed. Run this in the project root: pnpm install xlsx`);
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function walkFiles(root, maxDepth = 2) {
  if (!fs.existsSync(root)) return [];
  const results = [];

  function walk(current, depth) {
    if (depth > maxDepth) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath, depth + 1);
      } else if (entry.isFile()) {
        results.push(fullPath);
      }
    }
  }

  walk(root, 0);
  return results;
}

function recommendLoading(relativePath, size) {
  if (relativePath.startsWith("src/assets/data/") && size <= SMALL_FILE_LIMIT) {
    return "建议 import";
  }
  if (relativePath.startsWith("src/assets/data/") && size > SMALL_FILE_LIMIT) {
    return "文件偏大，建议移到 public/data 并 fetch";
  }
  if (relativePath.startsWith("public/data/")) {
    const url = `/${relativePath.replace(/^public\//, "")}`;
    return `建议 fetch('${url}')`;
  }
  return "位置未知，建议放到 src/assets/data 或 public/data";
}

function getSheetRowCount(XLSX, sheet) {
  if (!sheet["!ref"]) return 0;
  const range = XLSX.utils.decode_range(sheet["!ref"]);
  return Math.max(range.e.r - range.s.r, 0);
}

function normalizeValue(value) {
  if (value == null || value === "") return null;
  if (typeof value === "string") return value.trim();
  return value;
}

function looksNumeric(value) {
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value !== "string" || value.trim() === "") return false;
  const normalized = value.replace(/[$,%\s,]/g, "");
  return normalized !== "" && Number.isFinite(Number(normalized));
}

function looksDate(value) {
  if (value instanceof Date) return !Number.isNaN(value.getTime());
  if (typeof value !== "string") return false;
  const text = value.trim();
  if (!text) return false;
  if (/^\d{4}[-/]\d{1,2}[-/]\d{1,2}/.test(text)) return true;
  if (/^\d{4}[-/]\d{1,2}$/.test(text)) return true;
  const parsed = Date.parse(text);
  return !Number.isNaN(parsed) && /\d/.test(text);
}

function inferFieldType(key, values, rowCount) {
  const lowerKey = key.toLowerCase();
  const present = values.filter((value) => value != null && value !== "");
  const unique = new Set(present.map((value) => String(value))).size;
  if (present.length === 0) return "unknown";

  if (/(^|_)(id|uuid|code|no|number)$/.test(lowerKey) || /编号|学号|代码/.test(key)) {
    return unique >= Math.max(1, present.length * 0.8) ? "id" : "category";
  }
  if (/lat|lng|lon|latitude|longitude|country|city|province|region|address|地区|城市|省|国家/.test(lowerKey + key)) {
    return "geo";
  }

  const numericRatio = present.filter(looksNumeric).length / present.length;
  const dateRatio = present.filter(looksDate).length / present.length;
  const longTextRatio = present.filter((value) => String(value).length > 60).length / present.length;

  if (dateRatio >= 0.7) return "time";
  if (numericRatio >= 0.8) return "number";
  if (unique >= Math.max(1, present.length * 0.8) && rowCount > 10) return "id";
  if (longTextRatio >= 0.3) return "text";
  if (unique <= Math.max(20, present.length * 0.5)) return "category";
  return "text";
}

function analyzeRows(rows, rowCount) {
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  return keys.map((key) => {
    const values = rows.map((row) => normalizeValue(row[key]));
    const present = values.filter((value) => value != null && value !== "");
    const missing = values.length - present.length;
    const unique = new Set(present.map((value) => String(value))).size;
    return {
      key,
      type: inferFieldType(key, values, rowCount),
      missing,
      unique,
    };
  });
}

function chartSuggestions(fields) {
  const hasTime = fields.some((field) => field.type === "time");
  const hasNumber = fields.some((field) => field.type === "number");
  const hasCategory = fields.some((field) => field.type === "category");
  const hasGeo = fields.some((field) => field.type === "geo");
  const suggestions = [];

  if (hasTime && hasNumber) suggestions.push("时间趋势：折线图或面积图");
  if (hasCategory && hasNumber) suggestions.push("分类对比：柱状图，类别较多时用横向柱状图");
  if (hasGeo && hasNumber) suggestions.push("地理维度：地图或地区排名条形图");
  if (!suggestions.length && hasNumber) suggestions.push("数值分布：指标卡、排序表格或散点图");
  if (!suggestions.length) suggestions.push("字段结构偏文本/类别，先做可筛选表格或聚合后再画图");

  return suggestions;
}

function analyzeFile(XLSX, projectRoot, filePath, sampleSize) {
  const relativePath = path.relative(projectRoot, filePath).split(path.sep).join("/");
  const stat = fs.statSync(filePath);
  const ext = path.extname(filePath).toLowerCase();
  const workbook = XLSX.readFile(filePath, { cellDates: true });
  const sheets = workbook.SheetNames.map((sheetName) => {
    const sheet = workbook.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(sheet, { defval: null, raw: false }).slice(0, sampleSize);
    const rowCount = getSheetRowCount(XLSX, sheet);
    const fields = analyzeRows(rows, rowCount);
    return {
      sheetName,
      rowCount,
      columnCount: fields.length,
      fields,
      suggestions: chartSuggestions(fields),
    };
  });

  return {
    relativePath,
    size: stat.size,
    sizeLabel: formatBytes(stat.size),
    ext,
    recommendation: recommendLoading(relativePath, stat.size),
    sheets,
  };
}

function printReport(projectRoot, files, analyses) {
  console.log("数据检查结果：");
  if (!files.length) {
    console.log("- 没有发现可用的 .csv/.xlsx/.xls 数据文件。");
    console.log("- 小型示例数据放到 src/assets/data/。");
    console.log("- 较大或需要 fetch 的数据放到 public/data/。");
    return;
  }

  console.log(`- 找到 ${files.length} 个支持的数据文件`);
  for (const analysis of analyses) {
    console.log(`- ${analysis.relativePath}，${analysis.sizeLabel}，${analysis.recommendation}`);
  }

  console.log("\n数据结构理解：");
  for (const analysis of analyses) {
    for (const sheet of analysis.sheets) {
      console.log(`- ${analysis.relativePath} / ${sheet.sheetName}：约 ${sheet.rowCount} 行，${sheet.columnCount} 列`);
      for (const field of sheet.fields.slice(0, 12)) {
        const missingText = field.missing > 0 ? `，采样缺失 ${field.missing}` : "";
        console.log(`  - ${field.key}：${field.type}，唯一值 ${field.unique}${missingText}`);
      }
      if (sheet.fields.length > 12) {
        console.log(`  - 还有 ${sheet.fields.length - 12} 个字段未展开显示`);
      }
    }
  }

  console.log("\n可视化建议：");
  const seen = new Set();
  for (const analysis of analyses) {
    for (const sheet of analysis.sheets) {
      for (const suggestion of sheet.suggestions) {
        if (!seen.has(suggestion)) {
          seen.add(suggestion);
          console.log(`- ${suggestion}`);
        }
      }
    }
  }

  console.log(`\n项目根目录：${projectRoot}`);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    usage();
    return;
  }

  const projectRoot = path.resolve(args.projectRoot);
  const XLSX = loadXlsx(projectRoot);
  const files = DATA_DIRS.flatMap((dir) => walkFiles(path.join(projectRoot, dir)))
    .filter((filePath) => SUPPORTED_EXTENSIONS.has(path.extname(filePath).toLowerCase()));
  const analyses = files.map((filePath) => analyzeFile(XLSX, projectRoot, filePath, args.sampleSize));

  printReport(projectRoot, files, analyses);
}

try {
  main();
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
