import type { CanonicalField, FileType, Status } from "@/types/contract";

export const CANONICAL_FIELDS: { key: CanonicalField; label: string; hint: string }[] = [
  { key: "orderId", label: "Order ID", hint: "Joins orders, deliveries and complaints" },
  { key: "productId", label: "Product ID", hint: "Links products across files" },
  { key: "customerId", label: "Customer ID", hint: "Counts affected customers" },
  { key: "date", label: "Order date", hint: "Time axis for trends" },
  { key: "promisedDate", label: "Promised date", hint: "Delivery promise" },
  { key: "shippedDate", label: "Shipped date", hint: "Dispatch timestamp" },
  { key: "deliveredDate", label: "Delivered date", hint: "Actual delivery" },
  { key: "warehouse", label: "Warehouse", hint: "Fulfilment site" },
  { key: "city", label: "City", hint: "Destination city" },
  { key: "courier", label: "Courier", hint: "Carrier or delivery partner" },
  { key: "status", label: "Status", hint: "Order or shipment status" },
  { key: "complaintText", label: "Complaint text", hint: "Free-text complaint" },
  { key: "category", label: "Category", hint: "Product or complaint category" },
  { key: "stock", label: "Stock on hand", hint: "Units available" },
  { key: "dailySalesRate", label: "Daily sales rate", hint: "Units sold per day" },
  { key: "reorderLevel", label: "Reorder level", hint: "Replenishment threshold" },
  { key: "quantity", label: "Quantity", hint: "Units sold or ordered" },
  { key: "amount", label: "Amount", hint: "Order or sales value" },
  { key: "productName", label: "Product name", hint: "Display label" },
  { key: "rating", label: "Rating", hint: "Review score 1-5" },
];

export const FILE_TYPE_LABELS: Record<FileType, string> = {
  orders: "Orders",
  deliveries: "Deliveries",
  complaints: "Complaints",
  reviews: "Reviews",
  inventory: "Inventory",
  sales: "Sales",
  unknown: "Unknown",
};

export const ANALYSIS_STEPS = [
  "Cleaning",
  "Linking datasets",
  "Detecting patterns",
  "Assessing risks",
  "Generating recommendations",
] as const;

export const KANBAN_COLUMNS: { status: Status; label: string }[] = [
  { status: "open", label: "Open" },
  { status: "investigating", label: "Investigating" },
  { status: "escalated", label: "Escalated" },
  { status: "resolved", label: "Resolved" },
];

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function confidenceTone(value: number | undefined): string {
  if (value === undefined) return "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400";
  if (value < 0.5) return "bg-red-50 text-critical dark:bg-red-950/40 dark:text-red-300";
  if (value <= 0.8) return "bg-amber-50 text-medium dark:bg-amber-950/40 dark:text-amber-300";
  return "bg-teal-50 text-verified dark:bg-teal-950/40 dark:text-teal-300";
}

export function shortId(value: string, length = 8): string {
  return value.length > length ? value.slice(-length) : value;
}
