/**
 * API client with Telegram initData authentication.
 */

const API_BASE = '/api'

/**
 * Get Telegram initData for authentication.
 */
function getInitData(): string {
  return window.Telegram?.WebApp?.initData || ''
}

/**
 * Generic fetch wrapper with authentication.
 */
async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData()

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.detail || error.error || `HTTP ${response.status}`)
  }

  return response.json()
}

// ============== Types ==============

export interface RecurrenceRule {
  type: 'daily' | 'weekly' | 'monthly'
  interval: number  // Every N days/weeks/months
  days?: number[]   // For weekly: [0-6] where 0=Monday
  end_date?: string // ISO date string or null
}

export interface Item {
  id: number
  type: 'task' | 'idea' | 'note' | 'resource' | 'contact'
  status: 'processing' | 'inbox' | 'active' | 'done' | 'archived'
  title: string
  content?: string
  original_input?: string
  due_at?: string
  due_at_raw?: string
  tags: string[]
  project_id?: number
  priority?: 'high' | 'medium' | 'low'
  recurrence?: RecurrenceRule  // Recurrence rule for recurring tasks
  attachment_file_id?: string
  attachment_type?: string
  attachment_filename?: string
  origin_user_name?: string
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface CompleteItemResponse {
  completed: Item
  next_recurring: Item | null
}

export interface ItemsListResponse {
  items: Item[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface TaskGroup {
  label: string
  items: Item[]
}

export interface TasksListResponse {
  groups: TaskGroup[]
  total: number
}

export interface CalendarDay {
  date: string
  count: number
}

export interface CalendarResponse {
  days: CalendarDay[]
  tasks: Item[]
}

export interface Project {
  id: number
  name: string
  color?: string
  emoji?: string
  item_count: number
  created_at: string
}

export interface ProjectsListResponse {
  projects: Project[]
  total: number
}

export interface SearchResult {
  items: Item[]
  total: number
  has_more: boolean
  query: string
}

// ============== Items API ==============

export async function fetchItems(params: {
  type?: string
  status?: string
  project_id?: number
  limit?: number
  offset?: number
}): Promise<ItemsListResponse> {
  const searchParams = new URLSearchParams()
  if (params.type) searchParams.set('type', params.type)
  if (params.status) searchParams.set('status', params.status)
  if (params.project_id) searchParams.set('project_id', params.project_id.toString())
  if (params.limit) searchParams.set('limit', params.limit.toString())
  if (params.offset) searchParams.set('offset', params.offset.toString())

  const query = searchParams.toString()
  return fetchApi<ItemsListResponse>(`/items${query ? `?${query}` : ''}`)
}

export async function fetchItem(id: number): Promise<Item> {
  return fetchApi<Item>(`/items/${id}`)
}

export async function updateItem(id: number, data: Partial<Item>): Promise<Item> {
  return fetchApi<Item>(`/items/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteItem(id: number): Promise<void> {
  await fetchApi(`/items/${id}`, { method: 'DELETE' })
}

export async function completeItem(id: number): Promise<CompleteItemResponse> {
  return fetchApi<CompleteItemResponse>(`/items/${id}/complete`, { method: 'PATCH' })
}

export async function moveItem(id: number, projectId: number | null): Promise<Item> {
  return fetchApi<Item>(`/items/${id}/move`, {
    method: 'PATCH',
    body: JSON.stringify({ project_id: projectId }),
  })
}

export async function sendToChat(id: number): Promise<void> {
  await fetchApi(`/items/${id}/send-to-chat`, { method: 'POST' })
}

// ============== Tasks API ==============

export async function fetchTasks(includeCompleted = false): Promise<TasksListResponse> {
  const params = includeCompleted ? '?include_completed=true' : ''
  return fetchApi<TasksListResponse>(`/tasks${params}`)
}

export async function fetchCalendarTasks(year: number, month: number): Promise<CalendarResponse> {
  return fetchApi<CalendarResponse>(`/tasks/calendar?year=${year}&month=${month}`)
}

// ============== Projects API ==============

export async function fetchProjects(): Promise<ProjectsListResponse> {
  return fetchApi<ProjectsListResponse>('/projects')
}

export async function createProject(data: { name: string; color?: string; emoji?: string }): Promise<Project> {
  return fetchApi<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateProject(id: number, data: Partial<Project>): Promise<Project> {
  return fetchApi<Project>(`/projects/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteProject(id: number): Promise<void> {
  await fetchApi(`/projects/${id}`, { method: 'DELETE' })
}

// ============== Search API ==============

export async function searchItems(
  query: string,
  params: { type?: string; status?: string; limit?: number } = {}
): Promise<SearchResult> {
  const searchParams = new URLSearchParams({ q: query })
  if (params.type) searchParams.set('type', params.type)
  if (params.status) searchParams.set('status', params.status)
  if (params.limit) searchParams.set('limit', params.limit.toString())

  return fetchApi<SearchResult>(`/search?${searchParams.toString()}`)
}

// ============== User Settings API ==============

export interface NotificationSettings {
  task_reminders: boolean
  daily_digest: boolean
  weekly_review: boolean
  dnd_enabled: boolean
  dnd_start: string  // HH:MM format
  dnd_end: string    // HH:MM format
}

export interface UserSettings {
  notifications: NotificationSettings
}

export interface UserSettingsResponse {
  timezone: string
  language: string
  settings: UserSettings
  onboarding_done: boolean
}

export interface UserSettingsUpdate {
  timezone?: string
  language?: string
  notifications?: NotificationSettings
}

export async function fetchUserSettings(): Promise<UserSettingsResponse> {
  return fetchApi<UserSettingsResponse>('/user/settings')
}

export async function updateUserSettings(data: UserSettingsUpdate): Promise<UserSettingsResponse> {
  return fetchApi<UserSettingsResponse>('/user/settings', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function completeOnboarding(): Promise<void> {
  await fetchApi('/user/onboarding/complete', { method: 'POST' })
}
