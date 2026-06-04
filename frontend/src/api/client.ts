function getCsrfToken(): string {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : ''
}

type RequestOptions = RequestInit & { params?: Record<string, string | number | boolean | undefined> }

async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...init } = options

  let fullUrl = url
  if (params) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== '') qs.set(k, String(v))
    }
    const str = qs.toString()
    if (str) fullUrl += (url.includes('?') ? '&' : '?') + str
  }

  const method = (init.method ?? 'GET').toUpperCase()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(init.headers as Record<string, string>),
  }

  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    headers['X-CSRFToken'] = getCsrfToken()
  }

  const res = await fetch(fullUrl, { ...init, headers, credentials: 'include' })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, text)
  }

  if (res.status === 204) return undefined as T

  return res.json() as Promise<T>
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`HTTP ${status}: ${body}`)
    this.name = 'ApiError'
  }
}

/** Разбирает тело ответа DRF ({ error, detail, field errors }). */
export function parseApiError(err: unknown, fallback = 'Произошла ошибка'): string {
  if (err instanceof ApiError) {
    try {
      const data = JSON.parse(err.body) as Record<string, unknown>
      if (typeof data.error === 'string') return data.error
      if (typeof data.detail === 'string') return data.detail
      if (Array.isArray(data.non_field_errors) && data.non_field_errors[0]) {
        return String(data.non_field_errors[0])
      }
      const firstField = Object.values(data).find(v => Array.isArray(v) && v.length)
      if (firstField && Array.isArray(firstField)) return String(firstField[0])
    } catch {
      if (err.body) return err.body
    }
    if (err.status === 404) return 'Не найдено'
    if (err.status === 429) return 'Слишком много запросов. Подождите немного.'
    if (err.status >= 500) return 'Ошибка сервера. Попробуйте позже.'
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

export const api = {
  get: <T>(url: string, params?: RequestOptions['params']) =>
    request<T>(url, { method: 'GET', params }),

  post: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: 'POST', body: JSON.stringify(body) }),

  patch: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: 'PATCH', body: JSON.stringify(body) }),

  delete: <T = void>(url: string) =>
    request<T>(url, { method: 'DELETE' }),
}
