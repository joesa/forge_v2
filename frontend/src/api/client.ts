import axios from 'axios'

const client = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL ?? '') + '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Shared refresh promise to prevent race conditions when multiple
// requests hit 401 simultaneously — only one refresh call at a time.
let refreshPromise: Promise<string> | null = null

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          if (!refreshPromise) {
            refreshPromise = axios.post(
              (import.meta.env.VITE_API_BASE_URL ?? '') + '/api/v1/auth/refresh',
              { refresh_token: refreshToken },
            ).then(({ data }) => {
              localStorage.setItem('access_token', data.access_token as string)
              localStorage.setItem('refresh_token', data.refresh_token as string)
              return data.access_token as string
            }).finally(() => { refreshPromise = null })
          }
          const newToken = await refreshPromise
          original.headers.Authorization = `Bearer ${newToken}`
          return client(original)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
          return Promise.reject(error)
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default client
