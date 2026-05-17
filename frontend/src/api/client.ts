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
