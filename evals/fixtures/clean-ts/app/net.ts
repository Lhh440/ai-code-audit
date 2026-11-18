export interface Options {
  readonly timeoutMs: number;
}

export async function getJson<T>(url: string, options: Options): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`${response.status} from ${url}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return null;
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
