import axios from 'axios'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '') + '/api/v1'

/**
 * Return a valid access token, refreshing if the current one is expired.
 * Returns null when no session exists.
 */
export async function getValidToken(): Promise<string | null> {
  const token = localStorage.getItem('access_token')
  if (!token) return null

  // Quick JWT expiry check (avoid network call when clearly valid)
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    const exp = (payload.exp as number) ?? 0
    if (exp > Date.now() / 1000 + 30) return token // still valid with 30s buffer
  } catch {
    // malformed token — try refresh
  }

  // Token expired or nearly expired — refresh
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null

  try {
    const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
      refresh_token: refreshToken,
    })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    return data.access_token as string
  } catch {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    return null
  }
}
