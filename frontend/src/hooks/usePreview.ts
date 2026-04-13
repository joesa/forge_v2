import { useEffect, useRef, useCallback, useState } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import apiClient from '@/api/client'

const HEALTH_POLL_INTERVAL = 30_000

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

  const { selectedSnapshot, snapshots } = useEditorStore()

  const healthTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

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
          setHealthy(!!data.preview_url)
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

  // Poll health every 30s
  useEffect(() => {
    if (!sandboxId) return

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
  }, [sandboxId])

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
    error,
    snapshotImageUrl,
    refresh,
  }
}
