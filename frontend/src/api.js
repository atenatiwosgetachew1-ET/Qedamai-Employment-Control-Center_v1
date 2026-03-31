const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const CSRF_COOKIE_NAME = 'csrftoken'
const AUTH_ERROR_MESSAGE = 'Session expired. Please sign in again.'

let csrfToken = null

function readCookie(name) {
  const escaped = name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1')
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`))
  if (!match) return null
  try {
    return decodeURIComponent(match[1])
  } catch {
    return match[1]
  }
}

async function ensureCsrfToken() {
  const response = await fetch(`${API_BASE_URL}/api/csrf/`, { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Could not load security token.')
  }
  const data = await response.json()
  csrfToken = readCookie(CSRF_COOKIE_NAME) || data.csrfToken || csrfToken
  return csrfToken
}

export async function apiFetch(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  }
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    if (!csrfToken) {
      await ensureCsrfToken()
    }
    headers['X-CSRFToken'] = readCookie(CSRF_COOKIE_NAME) || csrfToken
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...options,
    headers
  })
  return response
}

function ensureAuthenticated(response, data) {
  if (response.status === 401 || response.status === 403) {
    throw new Error(data?.detail || data?.message || AUTH_ERROR_MESSAGE)
  }
}

async function parseJson(response) {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) {
    const text = await response.text().catch(() => '')
    throw new Error(
      text.startsWith('<!DOCTYPE')
        ? 'Frontend received HTML instead of API JSON. Check the Vite API proxy or VITE_API_BASE_URL.'
        : 'API did not return JSON.'
    )
  }
  return response.json().catch(() => ({}))
}

export async function login(username, password) {
  const response = await apiFetch('/api/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
  const data = await parseJson(response)
  if (!response.ok || !data.success) {
    throw new Error(data.message || 'Login failed')
  }
  return data.user
}

export async function logout() {
  await apiFetch('/api/logout/', { method: 'POST' })
}

export async function fetchMe() {
  const response = await apiFetch('/api/me/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error('Not authenticated')
  }
  return data
}

export async function fetchDashboard() {
  const response = await apiFetch('/api/dashboard/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to load dashboard')
  }
  return data
}

export async function fetchOrganizations() {
  const response = await apiFetch('/api/organizations/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to load organizations')
  }
  return Array.isArray(data) ? data : data.results || []
}

export async function createOrganization(payload) {
  const response = await apiFetch('/api/organizations/', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || JSON.stringify(data))
  }
  return data
}

export async function deleteOrganization(id) {
  const response = await apiFetch(`/api/organizations/${id}/`, { method: 'DELETE' })
  const data = response.status === 204 ? {} : await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to delete organization')
  }
}

export async function resetOrganizationSuperadminPassword(id, newPassword) {
  const response = await apiFetch(`/api/organizations/${id}/reset-superadmin-password/`, {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword })
  })
  const data = await parseJson(response)
  if (!response.ok || !data.success) {
    ensureAuthenticated(response, data)
    throw new Error(data.message || data.detail || 'Failed to reset superadmin password')
  }
  return data.organization
}

export async function requestOrganizationSuperadminPasswordReset(id) {
  const response = await apiFetch(`/api/organizations/${id}/request-superadmin-password-reset/`, {
    method: 'POST'
  })
  const data = await parseJson(response)
  if (!response.ok || !data.success) {
    ensureAuthenticated(response, data)
    throw new Error(data.message || data.detail || 'Failed to request superadmin password reset')
  }
  return data
}

export async function fetchPlans() {
  const response = await apiFetch('/api/plans/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to load plans')
  }
  return Array.isArray(data) ? data : data.results || []
}

export async function createPlan(payload) {
  const response = await apiFetch('/api/plans/', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || JSON.stringify(data))
  }
  return data
}

export async function deletePlan(id) {
  const response = await apiFetch(`/api/plans/${id}/`, { method: 'DELETE' })
  const data = response.status === 204 ? {} : await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to delete plan')
  }
}

export async function fetchSubscriptions() {
  const response = await apiFetch('/api/subscriptions/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to load subscriptions')
  }
  return Array.isArray(data) ? data : data.results || []
}

export async function createSubscription(payload) {
  const response = await apiFetch('/api/subscriptions/', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || JSON.stringify(data))
  }
  return data
}

export async function deleteSubscription(id) {
  const response = await apiFetch(`/api/subscriptions/${id}/`, { method: 'DELETE' })
  const data = response.status === 204 ? {} : await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to delete subscription')
  }
}

export async function fetchEvents() {
  const response = await apiFetch('/api/license-events/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to load license events')
  }
  return Array.isArray(data) ? data : data.results || []
}

export async function fetchSyncKeys() {
  const response = await apiFetch('/api/sync-keys/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to load sync keys')
  }
  return Array.isArray(data) ? data : data.results || []
}

export async function rotateSyncKey() {
  const response = await apiFetch('/api/sync-keys/rotate/', { method: 'POST' })
  const data = await parseJson(response)
  if (!response.ok || !data.success) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to rotate sync key')
  }
  return data.key
}

export async function fetchSyncJobs() {
  const response = await apiFetch('/api/sync-jobs/')
  const data = await parseJson(response)
  if (!response.ok) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to load sync jobs')
  }
  return Array.isArray(data) ? data : data.results || []
}

export async function retrySyncJob(jobId) {
  const response = await apiFetch(`/api/sync-jobs/${jobId}/retry/`, { method: 'POST' })
  const data = await parseJson(response)
  if (!response.ok && !data.success) {
    ensureAuthenticated(response, data)
    throw new Error(data.error || data.detail || 'Failed to retry sync job')
  }
  return data
}

export async function retryDueSyncJobs() {
  const response = await apiFetch('/api/sync-jobs/retry-due/', { method: 'POST' })
  const data = await parseJson(response)
  if (!response.ok || !data.success) {
    ensureAuthenticated(response, data)
    throw new Error(data.detail || 'Failed to retry due sync jobs')
  }
  return data
}
