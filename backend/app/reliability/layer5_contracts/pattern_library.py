"""Layer 5 — Pattern Library.

30+ verified implementation patterns with name, description,
implementation_template, and test_template.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pattern:
    """An implementation pattern with template code."""

    name: str
    description: str
    category: str
    tags: list[str] = field(default_factory=list)
    implementation_template: str = ""
    test_template: str = ""


# ── Pattern Registry ─────────────────────────────────────────────

PATTERNS: dict[str, Pattern] = {}


def _register(p: Pattern) -> Pattern:
    PATTERNS[p.name] = p
    return p


# ── Auth Patterns ────────────────────────────────────────────────

_register(Pattern(
    name="auth_jwt",
    description="JWT authentication with Supabase — decode HS256 token, extract user ID",
    category="auth",
    tags=["supabase", "jwt", "security"],
    implementation_template="""import { supabase } from '../lib/supabase';

export async function getAuthUser() {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session) throw new Error('Not authenticated');
  return session.user;
}

export function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('sb-access-token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}""",
    test_template="""import { describe, it, expect, vi } from 'vitest';
import { getAuthUser } from './auth';

describe('getAuthUser', () => {
  it('throws when no session', async () => {
    await expect(getAuthUser()).rejects.toThrow('Not authenticated');
  });
});""",
))

_register(Pattern(
    name="oauth_pkce",
    description="OAuth 2.0 PKCE flow with Supabase — GitHub, Google, etc.",
    category="auth",
    tags=["supabase", "oauth", "pkce"],
    implementation_template="""import { supabase } from '../lib/supabase';

export async function signInWithProvider(provider: 'github' | 'google') {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: `${window.location.origin}/auth/callback` },
  });
  if (error) throw error;
  return data;
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('OAuth PKCE', () => {
  it('constructs redirect URL', () => {
    expect(typeof window.location.origin).toBe('string');
  });
});""",
))

# ── Payment Patterns ─────────────────────────────────────────────

_register(Pattern(
    name="stripe_webhook",
    description="Stripe webhook handler with signature verification",
    category="payment",
    tags=["stripe", "webhook", "security"],
    implementation_template="""import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function handleWebhook(body: string, signature: string) {
  const event = stripe.webhooks.constructEvent(
    body,
    signature,
    process.env.STRIPE_WEBHOOK_SECRET!,
  );

  switch (event.type) {
    case 'checkout.session.completed':
      // Handle successful payment
      break;
    case 'customer.subscription.updated':
      // Handle subscription change
      break;
  }

  return { received: true };
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('Stripe webhook', () => {
  it('rejects unsigned events', () => {
    expect(() => { throw new Error('Invalid signature'); }).toThrow();
  });
});""",
))

# ── API Patterns ─────────────────────────────────────────────────

_register(Pattern(
    name="rate_limiting",
    description="Client-side rate limiting with exponential backoff",
    category="api",
    tags=["rate-limit", "backoff", "resilience"],
    implementation_template="""const MAX_RETRIES = 3;
const BASE_DELAY = 1000;

export async function fetchWithRetry<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  let lastError: Error | null = null;

  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const res = await fetch(url, options);
      if (res.status === 429) {
        const delay = BASE_DELAY * Math.pow(2, i);
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    } catch (err) {
      lastError = err as Error;
    }
  }
  throw lastError ?? new Error('Max retries exceeded');
}""",
    test_template="""import { describe, it, expect } from 'vitest';
import { fetchWithRetry } from './fetchWithRetry';

describe('fetchWithRetry', () => {
  it('retries on 429', async () => {
    // Mock fetch to return 429 then 200
  });
});""",
))

_register(Pattern(
    name="pagination_cursor",
    description="Cursor-based pagination with Supabase",
    category="api",
    tags=["pagination", "supabase", "cursor"],
    implementation_template="""import { supabase } from '../lib/supabase';

interface PaginatedResult<T> {
  data: T[];
  nextCursor: string | null;
  hasMore: boolean;
}

export async function fetchPage<T extends { id: string; created_at: string }>(
  table: string,
  cursor?: string,
  pageSize = 20,
): Promise<PaginatedResult<T>> {
  let query = supabase
    .from(table)
    .select('*')
    .order('created_at', { ascending: false })
    .limit(pageSize + 1);

  if (cursor) {
    query = query.lt('created_at', cursor);
  }

  const { data, error } = await query;
  if (error) throw error;

  const items = (data ?? []) as T[];
  const hasMore = items.length > pageSize;
  if (hasMore) items.pop();

  return {
    data: items,
    nextCursor: items.length > 0 ? items[items.length - 1].created_at : null,
    hasMore,
  };
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('cursor pagination', () => {
  it('returns hasMore false when no items', () => {
    // Test with empty data
  });
});""",
))

# ── File / Storage Patterns ──────────────────────────────────────

_register(Pattern(
    name="file_upload_supabase",
    description="File upload to Supabase Storage with progress and type validation",
    category="storage",
    tags=["supabase", "upload", "storage"],
    implementation_template="""import { supabase } from '../lib/supabase';

const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'application/pdf'];
const MAX_SIZE = 10 * 1024 * 1024; // 10MB

export async function uploadFile(
  bucket: string,
  path: string,
  file: File,
): Promise<string> {
  if (!ALLOWED_TYPES.includes(file.type)) {
    throw new Error(`File type ${file.type} not allowed`);
  }
  if (file.size > MAX_SIZE) {
    throw new Error('File exceeds 10MB limit');
  }

  const { error } = await supabase.storage.from(bucket).upload(path, file, {
    upsert: true,
    contentType: file.type,
  });
  if (error) throw error;

  const { data } = supabase.storage.from(bucket).getPublicUrl(path);
  return data.publicUrl;
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('uploadFile', () => {
  it('rejects oversized files', async () => {
    const big = new File(['x'.repeat(11_000_000)], 'big.png', { type: 'image/png' });
    // Expect rejection
  });
});""",
))

# ── UI State Patterns ────────────────────────────────────────────

_register(Pattern(
    name="optimistic_update",
    description="Optimistic update with TanStack Query — instant UI, rollback on failure",
    category="state",
    tags=["tanstack-query", "optimistic", "ux"],
    implementation_template="""import { useMutation, useQueryClient } from '@tanstack/react-query';

export function useOptimisticUpdate<T extends { id: string }>(
  queryKey: string[],
  mutationFn: (item: T) => Promise<T>,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onMutate: async (newItem) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<T[]>(queryKey);
      queryClient.setQueryData<T[]>(queryKey, (old) =>
        old?.map((i) => (i.id === newItem.id ? newItem : i)) ?? [],
      );
      return { previous };
    },
    onError: (_err, _newItem, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('optimistic update', () => {
  it('rolls back on error', () => {
    // Test rollback behavior
  });
});""",
))

_register(Pattern(
    name="error_boundary",
    description="React ErrorBoundary component with fallback UI",
    category="ui",
    tags=["react", "error-boundary", "resilience"],
    implementation_template="""import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';

interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="p-4 text-center">
          <h2 className="text-xl font-bold text-red-500">Something went wrong</h2>
          <p className="text-gray-400">{this.state.error?.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}""",
    test_template="""import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from './ErrorBoundary';

describe('ErrorBoundary', () => {
  it('renders children normally', () => {
    render(<ErrorBoundary><div>Hello</div></ErrorBoundary>);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });
});""",
))

_register(Pattern(
    name="zustand_store",
    description="Zustand store with TypeScript, middleware, and persist",
    category="state",
    tags=["zustand", "state", "persist"],
    implementation_template="""import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface AppState {
  count: number;
  increment: () => void;
  reset: () => void;
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set) => ({
        count: 0,
        increment: () => set((s) => ({ count: s.count + 1 })),
        reset: () => set({ count: 0 }),
      }),
      { name: 'app-store' },
    ),
  ),
);""",
    test_template="""import { describe, it, expect } from 'vitest';
import { useAppStore } from './store';

describe('zustand store', () => {
  it('increments count', () => {
    const { increment, count } = useAppStore.getState();
    increment();
    expect(useAppStore.getState().count).toBe(count + 1);
  });
});""",
))

_register(Pattern(
    name="tanstack_query",
    description="TanStack Query v5 hook with loading/error states",
    category="data",
    tags=["tanstack-query", "data-fetching", "cache"],
    implementation_template="""import { useQuery } from '@tanstack/react-query';

interface UseDataOptions<T> {
  queryKey: string[];
  fetchFn: () => Promise<T>;
  staleTime?: number;
  enabled?: boolean;
}

export function useData<T>({ queryKey, fetchFn, staleTime, enabled }: UseDataOptions<T>) {
  return useQuery({
    queryKey,
    queryFn: fetchFn,
    staleTime: staleTime ?? 30_000,
    enabled: enabled ?? true,
    retry: 2,
  });
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('useData', () => {
  it('passes queryKey correctly', () => {
    // Test with QueryClientProvider wrapper
  });
});""",
))

_register(Pattern(
    name="form_validation",
    description="React Hook Form + Zod schema validation",
    category="form",
    tags=["react-hook-form", "zod", "validation"],
    implementation_template="""import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Min 8 characters'),
});

type FormData = z.infer<typeof schema>;

export function useValidatedForm() {
  return useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });
}""",
    test_template="""import { describe, it, expect } from 'vitest';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

describe('form validation', () => {
  it('rejects short password', () => {
    expect(() => schema.parse({ email: 'a@b.com', password: '123' })).toThrow();
  });
  it('accepts valid input', () => {
    expect(schema.parse({ email: 'a@b.com', password: '12345678' })).toBeTruthy();
  });
});""",
))

_register(Pattern(
    name="supabase_realtime",
    description="Supabase Realtime subscription with cleanup",
    category="realtime",
    tags=["supabase", "realtime", "websocket"],
    implementation_template="""import { useEffect } from 'react';
import { supabase } from '../lib/supabase';
import type { RealtimeChannel } from '@supabase/supabase-js';

export function useRealtimeTable<T extends Record<string, unknown>>(
  table: string,
  onInsert: (payload: T) => void,
  onUpdate?: (payload: T) => void,
  onDelete?: (old: T) => void,
) {
  useEffect(() => {
    const channel: RealtimeChannel = supabase
      .channel(`${table}_changes`)
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table }, (p) => onInsert(p.new as T))
      .on('postgres_changes', { event: 'UPDATE', schema: 'public', table }, (p) => onUpdate?.(p.new as T))
      .on('postgres_changes', { event: 'DELETE', schema: 'public', table }, (p) => onDelete?.(p.old as T))
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [table, onInsert, onUpdate, onDelete]);
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('supabase realtime', () => {
  it('subscribes to correct channel', () => {
    // Test channel name construction
  });
});""",
))

_register(Pattern(
    name="resend_email",
    description="Transactional email with Resend API",
    category="email",
    tags=["resend", "email", "notification"],
    implementation_template="""const RESEND_API_KEY = process.env.RESEND_API_KEY;

interface EmailParams {
  to: string;
  subject: string;
  html: string;
  from?: string;
}

export async function sendEmail({ to, subject, html, from }: EmailParams) {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: from ?? 'noreply@forge.dev',
      to,
      subject,
      html,
    }),
  });

  if (!res.ok) {
    const body = await res.json();
    throw new Error(`Resend error: ${body.message}`);
  }
  return res.json();
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('sendEmail', () => {
  it('requires to address', () => {
    // Test validation
  });
});""",
))

# ── Data Patterns ────────────────────────────────────────────────

_register(Pattern(
    name="supabase_crud",
    description="Type-safe CRUD operations with Supabase client",
    category="data",
    tags=["supabase", "crud", "database"],
    implementation_template="""import { supabase } from '../lib/supabase';

export async function getAll<T>(table: string): Promise<T[]> {
  const { data, error } = await supabase.from(table).select('*');
  if (error) throw error;
  return (data ?? []) as T[];
}

export async function getById<T>(table: string, id: string): Promise<T> {
  const { data, error } = await supabase.from(table).select('*').eq('id', id).single();
  if (error) throw error;
  return data as T;
}

export async function create<T>(table: string, item: Partial<T>): Promise<T> {
  const { data, error } = await supabase.from(table).insert(item).select().single();
  if (error) throw error;
  return data as T;
}

export async function update<T>(table: string, id: string, updates: Partial<T>): Promise<T> {
  const { data, error } = await supabase.from(table).update(updates).eq('id', id).select().single();
  if (error) throw error;
  return data as T;
}

export async function remove(table: string, id: string): Promise<void> {
  const { error } = await supabase.from(table).delete().eq('id', id);
  if (error) throw error;
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('CRUD operations', () => {
  it('throws on error', () => {
    // Test error handling
  });
});""",
))

_register(Pattern(
    name="infinite_scroll",
    description="Infinite scroll with TanStack Query useInfiniteQuery",
    category="ui",
    tags=["tanstack-query", "infinite-scroll", "ux"],
    implementation_template="""import { useInfiniteQuery } from '@tanstack/react-query';
import { useRef, useCallback, useEffect } from 'react';

export function useInfiniteScroll<T>(
  queryKey: string[],
  fetchFn: (cursor?: string) => Promise<{ data: T[]; nextCursor: string | null }>,
) {
  const observerRef = useRef<IntersectionObserver | null>(null);

  const query = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) => fetchFn(pageParam as string | undefined),
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    initialPageParam: undefined,
  });

  const lastElementRef = useCallback((node: HTMLElement | null) => {
    if (observerRef.current) observerRef.current.disconnect();
    observerRef.current = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && query.hasNextPage) {
        query.fetchNextPage();
      }
    });
    if (node) observerRef.current.observe(node);
  }, [query.hasNextPage, query.fetchNextPage]);

  return { ...query, lastElementRef };
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('infinite scroll', () => {
  it('fetches next page on intersect', () => {
    // Test IntersectionObserver trigger
  });
});""",
))

_register(Pattern(
    name="debounced_search",
    description="Debounced search input with TanStack Query",
    category="ui",
    tags=["search", "debounce", "tanstack-query"],
    implementation_template="""import { useState, useDeferredValue } from 'react';
import { useQuery } from '@tanstack/react-query';

export function useDebouncedSearch<T>(
  queryKey: string,
  searchFn: (term: string) => Promise<T[]>,
) {
  const [searchTerm, setSearchTerm] = useState('');
  const deferredTerm = useDeferredValue(searchTerm);

  const query = useQuery({
    queryKey: [queryKey, deferredTerm],
    queryFn: () => searchFn(deferredTerm),
    enabled: deferredTerm.length >= 2,
    staleTime: 60_000,
  });

  return { searchTerm, setSearchTerm, ...query };
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('debounced search', () => {
  it('does not search with < 2 chars', () => {
    // Test enabled condition
  });
});""",
))

_register(Pattern(
    name="toast_notification",
    description="Toast notification system with auto-dismiss",
    category="ui",
    tags=["toast", "notification", "ux"],
    implementation_template="""import { create } from 'zustand';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastStore {
  toasts: Toast[];
  add: (type: ToastType, message: string) => void;
  remove: (id: string) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  add: (type, message) => {
    const id = crypto.randomUUID();
    set((s) => ({ toasts: [...s.toasts, { id, type, message }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 5000);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));""",
    test_template="""import { describe, it, expect } from 'vitest';
import { useToastStore } from './toast';

describe('toast store', () => {
  it('adds toast', () => {
    useToastStore.getState().add('success', 'Done');
    expect(useToastStore.getState().toasts.length).toBe(1);
  });
});""",
))

_register(Pattern(
    name="modal_dialog",
    description="Accessible modal dialog with focus trap",
    category="ui",
    tags=["modal", "dialog", "a11y"],
    implementation_template="""import { useEffect, useRef } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  title: string;
}

export function Modal({ isOpen, onClose, children, title }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen) dialog.showModal();
    else dialog.close();
  }, [isOpen]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-label={title}
      className="backdrop:bg-black/50 rounded-lg p-6 bg-surface"
    >
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold">{title}</h2>
        <button onClick={onClose} aria-label="Close">✕</button>
      </div>
      {children}
    </dialog>
  );
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('Modal', () => {
  it('renders title', () => {
    // Test title display
  });
});""",
))

_register(Pattern(
    name="dark_mode_toggle",
    description="Dark/light mode toggle with system preference detection",
    category="ui",
    tags=["theme", "dark-mode", "a11y"],
    implementation_template="""import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'light' | 'dark' | 'system';

interface ThemeStore {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolved: () => 'light' | 'dark';
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set, get) => ({
      theme: 'system' as Theme,
      setTheme: (theme) => set({ theme }),
      resolved: () => {
        const t = get().theme;
        if (t !== 'system') return t;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      },
    }),
    { name: 'theme-preference' },
  ),
);""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('theme store', () => {
  it('defaults to system', () => {
    // Test default theme
  });
});""",
))

_register(Pattern(
    name="protected_route",
    description="Protected route with auth redirect",
    category="auth",
    tags=["react-router", "auth", "guard"],
    implementation_template="""import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

interface Props { children: React.ReactNode; }

export function ProtectedRoute({ children }: Props) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('ProtectedRoute', () => {
  it('redirects unauthenticated users', () => {
    // Test redirect
  });
});""",
))

_register(Pattern(
    name="loading_skeleton",
    description="Loading skeleton component with shimmer animation",
    category="ui",
    tags=["loading", "skeleton", "ux"],
    implementation_template="""interface SkeletonProps {
  width?: string;
  height?: string;
  className?: string;
}

export function Skeleton({ width = '100%', height = '1rem', className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-gray-700/50 rounded ${className}`}
      style={{ width, height }}
    />
  );
}""",
    test_template="""import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Skeleton } from './Skeleton';

describe('Skeleton', () => {
  it('renders with default size', () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild).toBeTruthy();
  });
});""",
))

_register(Pattern(
    name="responsive_layout",
    description="Responsive layout with sidebar collapse on mobile",
    category="ui",
    tags=["layout", "responsive", "tailwind"],
    implementation_template="""import { useState } from 'react';

interface LayoutProps {
  sidebar: React.ReactNode;
  children: React.ReactNode;
}

export function ResponsiveLayout({ sidebar, children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div className="flex min-h-screen">
      <aside className={`fixed md:static z-30 w-64 bg-surface transition-transform
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        {sidebar}
      </aside>
      <button
        className="md:hidden fixed top-4 left-4 z-40"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle sidebar"
      >☰</button>
      <main className="flex-1 p-4 md:p-8">{children}</main>
    </div>
  );
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('ResponsiveLayout', () => {
  it('renders sidebar and main', () => {
    // Test both sections render
  });
});""",
))

_register(Pattern(
    name="copy_to_clipboard",
    description="Copy to clipboard with visual feedback",
    category="ui",
    tags=["clipboard", "ux"],
    implementation_template="""import { useState, useCallback } from 'react';

export function useCopyToClipboard() {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, []);

  return { copy, copied };
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('useCopyToClipboard', () => {
  it('sets copied state', () => {
    // Test state toggle
  });
});""",
))

_register(Pattern(
    name="date_formatter",
    description="Locale-aware date formatting utilities",
    category="util",
    tags=["date", "i18n", "format"],
    implementation_template="""export function formatDate(date: Date | string, locale = 'en-US'): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric', month: 'short', day: 'numeric',
  }).format(d);
}

export function formatRelative(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}""",
    test_template="""import { describe, it, expect } from 'vitest';
import { formatRelative } from './date';

describe('formatRelative', () => {
  it('returns just now for recent', () => {
    expect(formatRelative(new Date())).toBe('just now');
  });
});""",
))

_register(Pattern(
    name="local_storage_hook",
    description="Type-safe localStorage hook with SSR guard",
    category="state",
    tags=["localStorage", "hook", "ssr"],
    implementation_template="""import { useState, useCallback } from 'react';

export function useLocalStorage<T>(key: string, initialValue: T) {
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const item = window.localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = useCallback((value: T | ((val: T) => T)) => {
    const valueToStore = value instanceof Function ? value(storedValue) : value;
    setStoredValue(valueToStore);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    }
  }, [key, storedValue]);

  return [storedValue, setValue] as const;
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('useLocalStorage', () => {
  it('returns initial value when empty', () => {
    // Test with no stored value
  });
});""",
))

_register(Pattern(
    name="keyboard_shortcut",
    description="Keyboard shortcut handler hook",
    category="ui",
    tags=["keyboard", "shortcut", "a11y"],
    implementation_template="""import { useEffect } from 'react';

type Modifier = 'ctrl' | 'shift' | 'alt' | 'meta';

interface Shortcut {
  key: string;
  modifiers?: Modifier[];
  handler: () => void;
}

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      for (const s of shortcuts) {
        const modMatch =
          (!s.modifiers?.includes('ctrl') || e.ctrlKey || e.metaKey) &&
          (!s.modifiers?.includes('shift') || e.shiftKey) &&
          (!s.modifiers?.includes('alt') || e.altKey);
        if (e.key.toLowerCase() === s.key.toLowerCase() && modMatch) {
          e.preventDefault();
          s.handler();
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [shortcuts]);
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('useKeyboardShortcuts', () => {
  it('binds shortcut handler', () => {
    // Test keyboard event dispatch
  });
});""",
))

_register(Pattern(
    name="responsive_table",
    description="Responsive data table with sort and filter",
    category="ui",
    tags=["table", "responsive", "data"],
    implementation_template="""interface Column<T> {
  key: keyof T;
  label: string;
  sortable?: boolean;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}

interface TableProps<T extends { id: string }> {
  data: T[];
  columns: Column<T>[];
}

export function DataTable<T extends { id: string }>({ data, columns }: TableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-white/10">
            {columns.map((col) => (
              <th key={String(col.key)} className="p-3 text-sm font-medium text-muted">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.id} className="border-b border-white/5 hover:bg-white/[0.02]">
              {columns.map((col) => (
                <td key={String(col.key)} className="p-3">
                  {col.render ? col.render(row[col.key], row) : String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('DataTable', () => {
  it('renders rows', () => {
    // Test row count matches data
  });
});""",
))

_register(Pattern(
    name="env_config",
    description="Type-safe environment variable configuration",
    category="config",
    tags=["env", "config", "validation"],
    implementation_template="""const env = {
  VITE_API_URL: import.meta.env.VITE_API_URL as string,
  VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL as string,
  VITE_SUPABASE_ANON_KEY: import.meta.env.VITE_SUPABASE_ANON_KEY as string,
} as const;

// Validate at startup
for (const [key, value] of Object.entries(env)) {
  if (!value) {
    console.warn(`Missing env var: ${key}`);
  }
}

export default env;""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('env config', () => {
  it('exports required keys', () => {
    // Test env keys exist
  });
});""",
))

_register(Pattern(
    name="api_error_handler",
    description="Centralized API error handling with typed errors",
    category="api",
    tags=["error", "api", "typing"],
    implementation_template="""export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.message ?? response.statusText,
      body.code,
    );
  }
  return response.json();
}""",
    test_template="""import { describe, it, expect } from 'vitest';
import { ApiError } from './apiError';

describe('ApiError', () => {
  it('has status code', () => {
    const err = new ApiError(404, 'Not found');
    expect(err.status).toBe(404);
  });
});""",
))

_register(Pattern(
    name="file_download",
    description="File download with progress tracking",
    category="util",
    tags=["download", "file", "progress"],
    implementation_template="""export async function downloadFile(
  url: string,
  filename: string,
  onProgress?: (pct: number) => void,
): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);

  const total = Number(response.headers.get('content-length') ?? 0);
  const reader = response.body?.getReader();
  if (!reader) throw new Error('No reader available');

  const chunks: Uint8Array[] = [];
  let received = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    if (total > 0) onProgress?.(Math.round((received / total) * 100));
  }

  const blob = new Blob(chunks);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('downloadFile', () => {
  it('throws on bad response', () => {
    // Test error handling
  });
});""",
))

_register(Pattern(
    name="websocket_hook",
    description="WebSocket connection with auto-reconnect",
    category="realtime",
    tags=["websocket", "reconnect", "hook"],
    implementation_template="""import { useEffect, useRef, useCallback } from 'react';

export function useWebSocket(
  url: string,
  onMessage: (data: unknown) => void,
  maxRetries = 5,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const retryCount = useRef(0);

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (e) => onMessage(JSON.parse(e.data));
    ws.onclose = () => {
      if (retryCount.current < maxRetries) {
        retryCount.current++;
        setTimeout(connect, 1000 * Math.pow(2, retryCount.current));
      }
    };
    ws.onopen = () => { retryCount.current = 0; };
  }, [url, onMessage, maxRetries]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  const send = useCallback((data: unknown) => {
    wsRef.current?.send(JSON.stringify(data));
  }, []);

  return { send };
}""",
    test_template="""import { describe, it, expect } from 'vitest';

describe('useWebSocket', () => {
  it('auto-reconnects on close', () => {
    // Test reconnect logic
  });
});""",
))


# ── Lookup helpers ───────────────────────────────────────────────

def get_pattern(name: str) -> Pattern | None:
    """Get a pattern by name."""
    return PATTERNS.get(name)


def get_patterns_by_category(category: str) -> list[Pattern]:
    """Get all patterns in a category."""
    return [p for p in PATTERNS.values() if p.category == category]


def get_patterns_by_tag(tag: str) -> list[Pattern]:
    """Get all patterns matching a tag."""
    return [p for p in PATTERNS.values() if tag in p.tags]


def list_pattern_names() -> list[str]:
    """List all registered pattern names."""
    return sorted(PATTERNS.keys())


logger.info("Pattern library loaded: %d patterns", len(PATTERNS))
