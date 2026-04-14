import { useEffect, useRef, useCallback, useState } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import apiClient from '@/api/client'

const HEALTH_POLL_INTERVAL = 30_000
const BOOT_POLL_INTERVAL = 5_000  // Poll every 5s while sandbox is booting
const MAX_BOOT_POLLS = 40         // Stop after ~200s

interface PreviewUrlResponse {
  preview_url: string | null
  sandbox_id: string
}

interface HealthResponse {
  status: string
  sandbox_id: string
}

export function usePreview(sandboxId: string | null) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [healthy, setHealthy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [booting, setBooting] = useState(false)

  const { selectedSnapshot, snapshots } = useEditorStore()

  const healthTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const bootTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bootPollCount = useRef(0)

  // Fetch preview URL on mount when sandboxId is available
  useEffect(() => {
    if (!sandboxId) return
    let cancelled = false

    async function fetchUrl() {
      setLoading(true)
      setError(null)
      try {
        const { data } = await apiClient.get<PreviewUrlResponse>(
          `/sandbox/${sandboxId}/preview-url`,
        )
        if (!cancelled) {
          setPreviewUrl(data.preview_url)
          if (data.preview_url) {
            // Start boot polling to wait for the sandbox to become ready 
            setBooting(true)
            bootPollCount.current = 0
          } else {
            setHealthy(false)
          }
        }
      } catch {
        if (!cancelled) {
          setError('Failed to load preview URL')
          setHealthy(false)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void fetchUrl()
    return () => { cancelled = true }
  }, [sandboxId])

  // Boot polling: aggressively check if the sandbox dev server is reachable
  useEffect(() => {
    if (!booting || !previewUrl) return

    let cancelled = false

    async function poll() {
      if (cancelled || bootPollCount.current >= MAX_BOOT_POLLS) {
        setBooting(false)
        return
      }
      bootPollCount.current++
      try {
        // Try to reach the sandbox directly via a HEAD/fetch to the preview URL
        const resp = await fetch(previewUrl!, { mode: 'no-cors', cache: 'no-store' })
        // no-cors: opaque response, but if we get here without error the server is up.
        // For same-origin requests, check status
        if (resp.type === 'opaque' || resp.ok) {
          if (!cancelled) {
            setHealthy(true)
            setBooting(false)
          }
          return
        }
      } catch {
        // Network error — sandbox not ready yet
      }

      // Also check via backend health endpoint
      if (sandboxId) {
        try {
          const { data } = await apiClient.get<HealthResponse>(
            `/sandbox/${sandboxId}/preview/health`,
          )
          if (data.status === 'healthy' && !cancelled) {
            setHealthy(true)
            setBooting(false)
            return
          }
        } catch {
          // Not ready yet
        }
      }

      if (!cancelled) {
        bootTimerRef.current = setTimeout(poll, BOOT_POLL_INTERVAL)
      }
    }

    void poll()

    return () => {
      cancelled = true
      if (bootTimerRef.current) {
        clearTimeout(bootTimerRef.current)
        bootTimerRef.current = null
      }
    }
  }, [booting, previewUrl, sandboxId])

  // Steady-state health polling (every 30s once sandbox is running)
  useEffect(() => {
    if (!sandboxId || booting) return

    async function checkHealth() {
      try {
        const { data } = await apiClient.get<HealthResponse>(
          `/sandbox/${sandboxId}/preview/health`,
        )
        setHealthy(data.status === 'healthy')
      } catch {
        setHealthy(false)
      }
    }

    healthTimerRef.current = setInterval(() => void checkHealth(), HEALTH_POLL_INTERVAL)

    return () => {
      if (healthTimerRef.current !== null) {
        clearInterval(healthTimerRef.current)
        healthTimerRef.current = null
      }
    }
  }, [sandboxId, booting])

  // selectedSnapshot → show snapshot image instead of iframe
  const snapshotImageUrl = selectedSnapshot
    ? snapshots.find((s) => s.id === selectedSnapshot)?.url ?? null
    : null

  const refresh = useCallback(() => {
    if (!sandboxId) return
    setLoading(true)
    apiClient
      .get<PreviewUrlResponse>(`/sandbox/${sandboxId}/preview-url`)
      .then(({ data }) => {
        setPreviewUrl(data.preview_url)
        setHealthy(true)
      })
      .catch(() => {
        setError('Failed to refresh preview')
      })
      .finally(() => setLoading(false))
  }, [sandboxId])

  return {
    previewUrl,
    loading,
    healthy,
    booting,
    error,
    snapshotImageUrl,
    refresh,
  }
}
