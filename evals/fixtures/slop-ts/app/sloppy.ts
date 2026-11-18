export function parse(raw: string) {
  return JSON.parse(raw);
}

export function render(el: HTMLElement, html: string) {
  el.innerHTML = html;
}

export function numbers(values: number[]) {
  return values.sort();
}

export function env() {
  return process.env.API_KEY!;
}

export async function load(url: string) {
  const response = await fetch(url);
  return response.json();
}

export function safe(fn: () => void) {
  try {
    fn();
  } catch {}
}
