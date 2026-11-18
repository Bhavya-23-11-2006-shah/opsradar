import { z, type ZodTypeAny } from "zod";

const ENUM_FALLBACKS: Record<string, string> = {
  severity: "low",
  status: "open",
  type: "anomaly",
  fileType: "unknown",
  detectedType: "unknown",
  group: "city",
  priority: "normal",
  decision: "status_changed",
  llmMode: "template",
  step: "Cleaning",
};

function warn(path: string, message: string) {
  // eslint-disable-next-line no-console
  console.warn(`[normalize] ${path || "<root>"}: ${message}`);
}

function walk(schema: ZodTypeAny, value: unknown, path: string): unknown {
  if (schema instanceof z.ZodNullable) {
    if (value === null || value === undefined) return null;
    return walk(schema.unwrap() as ZodTypeAny, value, path);
  }

  if (schema instanceof z.ZodOptional) {
    if (value === undefined) return undefined;
    return walk(schema.unwrap() as ZodTypeAny, value, path);
  }

  if (schema instanceof z.ZodDefault) {
    if (value === undefined) return value;
    const inner = (schema._def as { innerType: ZodTypeAny }).innerType;
    return walk(inner, value, path);
  }

  if (schema instanceof z.ZodArray) {
    if (value === null || value === undefined) {
      warn(path, "array was null; using []");
      return [];
    }
    if (!Array.isArray(value)) {
      warn(path, `expected an array, received ${typeof value}; using []`);
      return [];
    }
    return value.map((item, index) =>
      walk(schema.element as ZodTypeAny, item, `${path}[${index}]`),
    );
  }

  if (schema instanceof z.ZodObject) {
    if (value === null || value === undefined || typeof value !== "object") return value;
    const shape = schema.shape as Record<string, ZodTypeAny>;
    const result: Record<string, unknown> = { ...(value as Record<string, unknown>) };
    for (const key of Object.keys(shape)) {
      if (!(key in result)) continue;
      result[key] = walk(shape[key], result[key], path ? `${path}.${key}` : key);
    }
    return result;
  }

  if (schema instanceof z.ZodNumber) {
    if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) {
      warn(path, `numeric string "${value}" converted to number`);
      return Number(value);
    }
    return value;
  }

  if (schema instanceof z.ZodEnum) {
    const options = schema.options as string[];
    if (typeof value === "string" && !options.includes(value)) {
      const field = path.split(".").pop() ?? "";
      const fallback = ENUM_FALLBACKS[field] ?? options[0];
      warn(path, `unknown enum value "${value}" replaced with "${fallback}"`);
      return fallback;
    }
    return value;
  }

  if (schema instanceof z.ZodRecord) {
    if (value === null || value === undefined || typeof value !== "object" || Array.isArray(value)) {
      return value;
    }
    const valueSchema = (schema._def as { valueType: ZodTypeAny }).valueType;
    const result: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      result[key] = walk(valueSchema, item, `${path}.${key}`);
    }
    return result;
  }

  if (schema instanceof z.ZodUnion) {
    const options = schema.options as ZodTypeAny[];
    for (const option of options) {
      if (option.safeParse(value).success) {
        return walk(option, value, path);
      }
    }
    return value;
  }

  return value;
}

/** Normalise a payload against the zod schema before validation. */
export function normalizePayload(schema: ZodTypeAny, payload: unknown): unknown {
  return walk(schema, payload, "");
}
