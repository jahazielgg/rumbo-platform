export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message)
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    let message = `Error ${response.status}`
    try {
      const payload = await response.json()
      message = payload.detail ?? message
    } catch {
      // Ignore malformed error payloads.
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function assetUrl(path: string): string {
  return path.startsWith('http') ? path : `${API_URL}${path}`
}
