export type ToastTone = "info" | "success" | "error" | "warning";

export interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
}

type Listener = (items: ToastItem[]) => void;

let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<Listener>();

function emit() {
  for (const listener of listeners) listener(items);
}

export function toast(message: string, tone: ToastTone = "info") {
  const item: ToastItem = { id: nextId++, message, tone };
  items = [...items, item];
  emit();
  setTimeout(() => {
    items = items.filter((candidate) => candidate.id !== item.id);
    emit();
  }, 5200);
}

export function dismissToast(id: number) {
  items = items.filter((candidate) => candidate.id !== id);
  emit();
}

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener);
  listener(items);
  return () => listeners.delete(listener);
}
