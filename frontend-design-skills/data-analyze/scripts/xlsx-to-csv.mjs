#!/usr/bin/env node
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const SUPPORTED_INPUT = new Set([".xlsx", ".xls"]);

function usage() {
  console.log(`Usage:
  node scripts/xlsx-to-csv.mjs <input.xlsx|input.xls> [--project-root .] [--out public/data] [--sheet Sheet1] [--force]

Examples:
  node /path/to/data-analyze/scripts/xlsx-to-csv.mjs public/data/sales.xlsx
  node /path/to/data-analyze/scripts/xlsx-to-csv.mjs raw/sales.xls --out public/data --sheet Sheet1

Notes:
  - Run from the target Vite project, or pass --project-root.
  - The target project must have xlsx installed: pnpm install xlsx
  - Multiple sheets produce basename-sheetname.csv files.
`);
}

function parseArgs(argv) {
  const args = {
    input: null,
    projectRoot: process.cwd(),
    outDir: "public/data",
    sheet: null,
    force: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--help" || token === "-h") {
      args.help = true;
    } else if (token === "--project-root") {
      args.projectRoot = argv[++index];
    } else if (token === "--out") {
      args.outDir = argv[++index];
    } else if (token === "--sheet") {
      args.sheet = argv[++index];
    } else if (token === "--force") {
      args.force = true;
    } else if (!args.input) {
      args.input = token;
    } else {
      throw new Error(`Unexpected argument: ${token}`);
    }
  }

  return args;
}

function loadXlsx(projectRoot) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) {
    throw new Error(`No package.json found at ${projectRoot}. Pass --project-root for the target Vite project.`);
  }

  const requireFromProject = createRequire(packageJson);
  try {
    return requireFromProject("xlsx");
  } catch {
    throw new Error(`The target project does not have xlsx installed. Run this in the project root: pnpm install xlsx`);
  }
}

function sanitizeName(name) {
  return name
    .trim()
    .replace(/[\\/:"*?<>|]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "") || "sheet";
}

function resolvePath(projectRoot, value) {
  return path.isAbsolute(value) ? value : path.join(projectRoot, value);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.input) {
    usage();
    process.exit(args.help ? 0 : 1);
  }

  const projectRoot = path.resolve(args.projectRoot);
  const inputPath = resolvePath(projectRoot, args.input);
  const outDir = resolvePath(projectRoot, args.outDir);
  const ext = path.extname(inputPath).toLowerCase();

  if (!SUPPORTED_INPUT.has(ext)) {
    throw new Error(`Unsupported input format: ${ext}. Expected .xlsx or .xls.`);
  }
  if (!fs.existsSync(inputPath)) {
    throw new Error(`Input file does not exist: ${inputPath}`);
  }

  const XLSX = loadXlsx(projectRoot);
  const workbook = XLSX.readFile(inputPath, { cellDates: true });
  const sheetNames = args.sheet ? [args.sheet] : workbook.SheetNames;
  const missingSheet = sheetNames.find((sheetName) => !workbook.Sheets[sheetName]);
  if (missingSheet) {
    throw new Error(`Sheet not found: ${missingSheet}. Available sheets: ${workbook.SheetNames.join(", ")}`);
  }

  fs.mkdirSync(outDir, { recursive: true });
  const baseName = sanitizeName(path.basename(inputPath, ext));
  const outputs = [];

  for (const sheetName of sheetNames) {
    const sheet = workbook.Sheets[sheetName];
    const csv = XLSX.utils.sheet_to_csv(sheet, { blankrows: false });
    const suffix = sheetNames.length === 1 ? "" : `-${sanitizeName(sheetName)}`;
    const outputPath = path.join(outDir, `${baseName}${suffix}.csv`);

    if (fs.existsSync(outputPath) && !args.force) {
      throw new Error(`Output already exists: ${outputPath}. Use --force to overwrite.`);
    }

    fs.writeFileSync(outputPath, csv, "utf8");
    outputs.push(path.relative(projectRoot, outputPath));
  }

  console.log("Excel 转 CSV 完成：");
  for (const output of outputs) {
    console.log(`- ${output}`);
  }
}

try {
  main();
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
