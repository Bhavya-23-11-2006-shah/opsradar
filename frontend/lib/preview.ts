"use client";

import Papa from "papaparse";
import * as XLSX from "xlsx";

export interface LocalPreview {
  name: string;
  columns: string[];
  rows: Record<string, string>[];
  totalRows: number;
  kind: "csv" | "excel";
}

function coerce(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

export async function previewFile(file: File): Promise<LocalPreview> {
  const extension = file.name.split(".").pop()?.toLowerCase();

  if (extension === "csv") {
    return new Promise((resolve, reject) => {
      Papa.parse<Record<string, unknown>>(file, {
        header: true,
        skipEmptyLines: true,
        preview: 6,
        complete: (result) => {
          const columns = (result.meta.fields ?? []).filter(Boolean);
          resolve({
            name: file.name,
            columns,
            rows: result.data.slice(0, 5).map((row) => {
              const mapped: Record<string, string> = {};
              for (const column of columns) mapped[column] = coerce(row[column]);
              return mapped;
            }),
            totalRows: Math.max(result.data.length, 0),
            kind: "csv",
          });
        },
        error: (error) => reject(error),
      });
    });
  }

  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];
  const matrix = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, blankrows: false });
  const headerRow = (matrix[0] ?? []).map(coerce);
  const columns = headerRow.filter((column) => column !== "");
  const rows = matrix.slice(1, 6).map((row) => {
    const mapped: Record<string, string> = {};
    columns.forEach((column, index) => {
      mapped[column] = coerce(row[index]);
    });
    return mapped;
  });
  return {
    name: file.name,
    columns,
    rows,
    totalRows: Math.max(matrix.length - 1, 0),
    kind: "excel",
  };
}
