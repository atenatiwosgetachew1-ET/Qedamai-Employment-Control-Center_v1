import { useEffect, useState } from 'react'
import './App.css'
import {
  createOrganization,
  createPlan,
  createSubscription,
  deleteOrganization,
  deletePlan,
  deleteSubscription,
  fetchDashboard,
  fetchEvents,
  fetchMe,
  fetchOrganizations,
  fetchPlans,
  fetchSubscriptions,
  fetchSyncJobs,
  fetchSyncKeys,
  login,
  logout,
  requestOrganizationSuperadminPasswordReset,
  retryDueSyncJobs,
  retrySyncJob,
  rotateSyncKey
} from './api'

const emptyOrg = {
  name: '',
  slug: '',
  portal_base_url: '',
  portal_api_base_url: '',
  superadmin_username: '',
  superadmin_email: '',
  superadmin_password: '',
  billing_contact_name: '',
  billing_contact_email: '',
  reputation_tier: 'standard',
  status: 'pending',
  read_only_mode: false,
  notes: ''
}

const emptyPlan = {
  code: '',
  name: '',
  description: '',
  monthly_price: '0.00',
  currency: 'USD',
  max_superadmins: 1,
  max_admins: 1,
  max_staff: 4,
  max_customers: 5,
  feature_flags: '{}',
  is_active: true
}

const emptySubscription = {
  organization: '',
  plan: '',
  status: 'trial',
  starts_at: '',
  renews_at: '',
  grace_ends_at: '',
  cancelled_at: '',
  last_payment_status: 'pending',
  notes: ''
}

function toIso(value) {
  return value ? new Date(value).toISOString() : null
}

function isAuthError(message) {
  return (
    message === 'Session expired. Please sign in again.' ||
    message === 'Authentication credentials were not provided.' ||
    message === 'Not authenticated'
  )
}

export default function App() {
  const [user, setUser] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [organizations, setOrganizations] = useState([])
  const [plans, setPlans] = useState([])
  const [subscriptions, setSubscriptions] = useState([])
  const [events, setEvents] = useState([])
  const [syncKeys, setSyncKeys] = useState([])
  const [syncJobs, setSyncJobs] = useState([])
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [orgForm, setOrgForm] = useState(emptyOrg)
  const [planForm, setPlanForm] = useState(emptyPlan)
  const [subscriptionForm, setSubscriptionForm] = useState(emptySubscription)
  const [resetRequestResults, setResetRequestResults] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const resetSession = (message = 'Session expired. Please sign in again.') => {
    setUser(null)
    setDashboard(null)
    setOrganizations([])
    setPlans([])
    setSubscriptions([])
    setEvents([])
    setSyncJobs([])
    setSyncKeys([])
    setError(message)
    setLoading(false)
  }

  const loadAll = async () => {
    const [me, dash, orgs, fetchedPlans, subs, evt, jobs] = await Promise.all([
      fetchMe(),
      fetchDashboard(),
      fetchOrganizations(),
      fetchPlans(),
      fetchSubscriptions(),
      fetchEvents(),
      fetchSyncJobs()
    ])
    const keys = await fetchSyncKeys()
    setUser(me)
    setDashboard(dash)
    setOrganizations(orgs)
    setPlans(fetchedPlans)
    setSubscriptions(subs)
    setEvents(evt)
    setSyncJobs(jobs)
    setSyncKeys(keys)
  }

  useEffect(() => {
    fetchMe()
      .then(async (me) => {
        setUser(me)
        await loadAll()
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const handleLogin = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(loginForm.username, loginForm.password)
      await loadAll()
    } catch (err) {
      setError(err.message || 'Could not sign in')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    setUser(null)
    setDashboard(null)
    setOrganizations([])
    setPlans([])
    setSubscriptions([])
    setEvents([])
    setSyncJobs([])
    setSyncKeys([])
  }

  const refreshData = async () => {
    setError('')
    try {
      await loadAll()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not refresh data')
    }
  }

  const submitOrganization = async (event) => {
    event.preventDefault()
    setError('')
    try {
      await createOrganization(orgForm)
      setOrgForm(emptyOrg)
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not create organization')
    }
  }

  const submitPlan = async (event) => {
    event.preventDefault()
    setError('')
    try {
      await createPlan({
        ...planForm,
        monthly_price: String(planForm.monthly_price),
        feature_flags: JSON.parse(planForm.feature_flags || '{}')
      })
      setPlanForm(emptyPlan)
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not create plan')
    }
  }

  const submitSubscription = async (event) => {
    event.preventDefault()
    setError('')
    try {
      await createSubscription({
        ...subscriptionForm,
        starts_at: toIso(subscriptionForm.starts_at),
        renews_at: toIso(subscriptionForm.renews_at),
        grace_ends_at: toIso(subscriptionForm.grace_ends_at),
        cancelled_at: toIso(subscriptionForm.cancelled_at)
      })
      setSubscriptionForm(emptySubscription)
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not save subscription')
    }
  }

  const handleRotateKey = async () => {
    setError('')
    try {
      await rotateSyncKey()
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not rotate sync key')
    }
  }

  const handleRetryDueJobs = async () => {
    setError('')
    try {
      await retryDueSyncJobs()
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not retry due sync jobs')
    }
  }

  const handleRetryJob = async (jobId) => {
    setError('')
    try {
      await retrySyncJob(jobId)
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not retry sync job')
    }
  }

  const handleDeleteOrganization = async (organization) => {
    if (!window.confirm(`Delete organization "${organization.name}"?`)) return
    setError('')
    try {
      await deleteOrganization(organization.id)
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not delete organization')
    }
  }

  const handleRequestOrganizationPasswordReset = async (organization) => {
    setError('')
    try {
      const result = await requestOrganizationSuperadminPasswordReset(organization.id)
      setResetRequestResults((current) => ({ ...current, [organization.id]: result }))
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not request superadmin password reset')
    }
  }

  const handleDeletePlan = async (plan) => {
    if (!window.confirm(`Delete plan "${plan.name}"?`)) return
    setError('')
    try {
      await deletePlan(plan.id)
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not delete plan')
    }
  }

  const handleDeleteSubscription = async (subscription) => {
    if (!window.confirm(`Delete subscription for "${subscription.organization_name}"?`)) return
    setError('')
    try {
      await deleteSubscription(subscription.id)
      await refreshData()
    } catch (err) {
      if (isAuthError(err.message)) {
        resetSession(err.message)
        return
      }
      setError(err.message || 'Could not delete subscription')
    }
  }

  if (loading && !user) {
    return (
      <main className="shell">
        <section className="hero login">
          <h1>Employment Portal Company Control Center</h1>
          <p>Loading company operator session…</p>
        </section>
      </main>
    )
  }

  if (!user) {
    return (
      <main className="shell">
        <section className="hero login">
          <h1>Employment Portal Company Control Center</h1>
          <p>Sign in with a Django staff or superuser account to manage customer organizations.</p>
          {error && <p className="error">{error}</p>}
          <form onSubmit={handleLogin}>
            <label>
              Username
              <input
                value={loginForm.username}
                onChange={(event) =>
                  setLoginForm((current) => ({ ...current, username: event.target.value }))
                }
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={loginForm.password}
                onChange={(event) =>
                  setLoginForm((current) => ({ ...current, password: event.target.value }))
                }
              />
            </label>
            <button type="submit">Sign in</button>
          </form>
        </section>
      </main>
    )
  }

  return (
    <main className="shell">
      <section className="hero">
        <h1>Employment Portal Company Control Center</h1>
        <p>
          Manage customer organizations, plan allocations, subscription state, and license events
          from a separate deployment.
        </p>
      </section>

      <div className="toolbar">
        <p className="muted">
          Signed in as <strong>{user.username}</strong>
        </p>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="secondary" type="button" onClick={refreshData}>
            Refresh
          </button>
          <button type="button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="grid" style={{ marginBottom: 20 }}>
        <section className="panel">
          <h2>Portfolio snapshot</h2>
          <div className="stats">
            <div className="stat">
              <span className="muted">Organizations</span>
              <strong>{dashboard?.organizations ?? 0}</strong>
            </div>
            <div className="stat">
              <span className="muted">Plans</span>
              <strong>{dashboard?.plans ?? 0}</strong>
            </div>
            <div className="stat">
              <span className="muted">Active</span>
              <strong>{dashboard?.active_subscriptions ?? 0}</strong>
            </div>
            <div className="stat">
              <span className="muted">Grace</span>
              <strong>{dashboard?.grace_subscriptions ?? 0}</strong>
            </div>
            <div className="stat">
              <span className="muted">Suspended</span>
              <strong>{dashboard?.suspended_subscriptions ?? 0}</strong>
            </div>
            <div className="stat">
              <span className="muted">Active keys</span>
              <strong>{syncKeys.filter((key) => key.is_active).length}</strong>
            </div>
            <div className="stat">
              <span className="muted">Failed jobs</span>
              <strong>{syncJobs.filter((job) => job.status === 'failed').length}</strong>
            </div>
          </div>
        </section>
      </div>

      <div className="grid">
        <section className="panel">
          <h2>Sync job outbox</h2>
          <p className="muted">
            Every delivery attempt is recorded here so failed syncs can be retried safely.
          </p>
          <button type="button" onClick={handleRetryDueJobs}>
            Retry due jobs
          </button>
          <div className="list" style={{ marginTop: 12 }}>
            {syncJobs.slice(0, 20).map((job) => (
              <article key={job.id} className="item">
                <h3>
                  {job.target_type} #{job.target_id}
                </h3>
                <p className="muted">
                  {job.status} • attempts {job.attempts}
                </p>
                <p className="muted">{job.endpoint}</p>
                <p>{job.last_error || 'No error recorded'}</p>
                <button type="button" className="secondary" onClick={() => handleRetryJob(job.id)}>
                  Retry now
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Sync trust keys</h2>
          <p className="muted">
            The active private key stays in the company control center. Customer portals fetch the
            matching public key dynamically over HTTPS.
          </p>
          <button type="button" onClick={handleRotateKey}>
            Rotate active key
          </button>
          <div className="list" style={{ marginTop: 12 }}>
            {syncKeys.map((key) => (
              <article key={key.id} className="item">
                <h3>{key.key_id}</h3>
                <p className="muted">
                  {key.algorithm} • {key.is_active ? 'active' : 'inactive'}
                </p>
                <p className="muted">
                  Created: {new Date(key.created_at).toLocaleString()}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Create organization</h2>
          <form onSubmit={submitOrganization}>
            <input placeholder="Name" value={orgForm.name} onChange={(event) => setOrgForm((current) => ({ ...current, name: event.target.value }))} />
            <input placeholder="Slug" value={orgForm.slug} onChange={(event) => setOrgForm((current) => ({ ...current, slug: event.target.value }))} />
            <input placeholder="Portal frontend URL, e.g. localhost:5173 or https://portal.example.com" value={orgForm.portal_base_url} onChange={(event) => setOrgForm((current) => ({ ...current, portal_base_url: event.target.value }))} />
            <input placeholder="Portal backend URL, e.g. localhost:8000 or https://api.portal.example.com" value={orgForm.portal_api_base_url} onChange={(event) => setOrgForm((current) => ({ ...current, portal_api_base_url: event.target.value }))} />
            <input placeholder="Organization super admin username" value={orgForm.superadmin_username} onChange={(event) => setOrgForm((current) => ({ ...current, superadmin_username: event.target.value }))} />
            <input placeholder="Organization super admin email" value={orgForm.superadmin_email} onChange={(event) => setOrgForm((current) => ({ ...current, superadmin_email: event.target.value }))} />
            <input type="password" placeholder="Organization super admin password" value={orgForm.superadmin_password} onChange={(event) => setOrgForm((current) => ({ ...current, superadmin_password: event.target.value }))} />
            <input placeholder="Billing contact name" value={orgForm.billing_contact_name} onChange={(event) => setOrgForm((current) => ({ ...current, billing_contact_name: event.target.value }))} />
            <input placeholder="Billing contact email" value={orgForm.billing_contact_email} onChange={(event) => setOrgForm((current) => ({ ...current, billing_contact_email: event.target.value }))} />
            <select value={orgForm.reputation_tier} onChange={(event) => setOrgForm((current) => ({ ...current, reputation_tier: event.target.value }))}>
              <option value="low">Low reputation</option>
              <option value="standard">Standard reputation</option>
              <option value="trusted">Trusted reputation</option>
            </select>
            <select value={orgForm.status} onChange={(event) => setOrgForm((current) => ({ ...current, status: event.target.value }))}>
              <option value="pending">Pending</option>
              <option value="active">Active</option>
              <option value="grace">Grace</option>
              <option value="suspended">Suspended</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <textarea placeholder="Notes" value={orgForm.notes} onChange={(event) => setOrgForm((current) => ({ ...current, notes: event.target.value }))} />
            <label>
              <input type="checkbox" checked={orgForm.read_only_mode} onChange={(event) => setOrgForm((current) => ({ ...current, read_only_mode: event.target.checked }))} />{' '}
              Read-only mode
            </label>
            <button type="submit">Create organization</button>
          </form>
        </section>

        <section className="panel">
          <h2>Create plan</h2>
          <form onSubmit={submitPlan}>
            <input placeholder="Code" value={planForm.code} onChange={(event) => setPlanForm((current) => ({ ...current, code: event.target.value }))} />
            <input placeholder="Name" value={planForm.name} onChange={(event) => setPlanForm((current) => ({ ...current, name: event.target.value }))} />
            <textarea placeholder="Description" value={planForm.description} onChange={(event) => setPlanForm((current) => ({ ...current, description: event.target.value }))} />
            <input placeholder="Monthly price" value={planForm.monthly_price} onChange={(event) => setPlanForm((current) => ({ ...current, monthly_price: event.target.value }))} />
            <input placeholder="Currency" value={planForm.currency} onChange={(event) => setPlanForm((current) => ({ ...current, currency: event.target.value }))} />
            <input type="number" placeholder="Max superadmins" value={planForm.max_superadmins} onChange={(event) => setPlanForm((current) => ({ ...current, max_superadmins: Number(event.target.value) }))} />
            <input type="number" placeholder="Max admins" value={planForm.max_admins} onChange={(event) => setPlanForm((current) => ({ ...current, max_admins: Number(event.target.value) }))} />
            <input type="number" placeholder="Max staff" value={planForm.max_staff} onChange={(event) => setPlanForm((current) => ({ ...current, max_staff: Number(event.target.value) }))} />
            <input type="number" placeholder="Max customers" value={planForm.max_customers} onChange={(event) => setPlanForm((current) => ({ ...current, max_customers: Number(event.target.value) }))} />
            <textarea placeholder='Feature flags JSON, e.g. {"audit_log_enabled": true}' value={planForm.feature_flags} onChange={(event) => setPlanForm((current) => ({ ...current, feature_flags: event.target.value }))} />
            <label>
              <input type="checkbox" checked={planForm.is_active} onChange={(event) => setPlanForm((current) => ({ ...current, is_active: event.target.checked }))} />{' '}
              Active plan
            </label>
            <button type="submit">Create plan</button>
          </form>
        </section>

        <section className="panel">
          <h2>Create subscription</h2>
          <form onSubmit={submitSubscription}>
            <select value={subscriptionForm.organization} onChange={(event) => setSubscriptionForm((current) => ({ ...current, organization: Number(event.target.value) }))}>
              <option value="">Select organization</option>
              {organizations.map((organization) => (
                <option key={organization.id} value={organization.id}>
                  {organization.name}
                </option>
              ))}
            </select>
            <select value={subscriptionForm.plan} onChange={(event) => setSubscriptionForm((current) => ({ ...current, plan: Number(event.target.value) }))}>
              <option value="">Select plan</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name}
                </option>
              ))}
            </select>
            <select value={subscriptionForm.status} onChange={(event) => setSubscriptionForm((current) => ({ ...current, status: event.target.value }))}>
              <option value="trial">Trial</option>
              <option value="active">Active</option>
              <option value="grace">Grace</option>
              <option value="suspended">Suspended</option>
              <option value="cancelled">Cancelled</option>
              <option value="expired">Expired</option>
            </select>
            <input type="datetime-local" value={subscriptionForm.starts_at} onChange={(event) => setSubscriptionForm((current) => ({ ...current, starts_at: event.target.value }))} />
            <input type="datetime-local" value={subscriptionForm.renews_at} onChange={(event) => setSubscriptionForm((current) => ({ ...current, renews_at: event.target.value }))} />
            <input type="datetime-local" value={subscriptionForm.grace_ends_at} onChange={(event) => setSubscriptionForm((current) => ({ ...current, grace_ends_at: event.target.value }))} />
            <select value={subscriptionForm.last_payment_status} onChange={(event) => setSubscriptionForm((current) => ({ ...current, last_payment_status: event.target.value }))}>
              <option value="pending">Pending payment</option>
              <option value="paid">Paid</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <textarea placeholder="Notes" value={subscriptionForm.notes} onChange={(event) => setSubscriptionForm((current) => ({ ...current, notes: event.target.value }))} />
            <button type="submit">Save subscription</button>
          </form>
        </section>

        <section className="panel">
          <h2>Organizations</h2>
          <div className="list">
            {organizations.map((organization) => (
              <article key={organization.id} className="item">
                <h3>{organization.name}</h3>
                <p className="muted">
                  {organization.status} • {organization.reputation_tier}
                </p>
                <p className="muted">
                  Super admin: {organization.superadmin_username || 'Not configured'}
                </p>
                <p className="muted">
                  Super admin email: {organization.superadmin_email || 'Not configured'}
                </p>
                <p className="muted">
                  Portal backend: {organization.portal_api_base_url || 'Using global fallback'}
                </p>
                <p>{organization.billing_contact_email || 'No billing email set'}</p>
                <p className="muted">
                  {organization.subscription
                    ? `${organization.subscription.plan_name} • ${organization.subscription.status}`
                    : 'No subscription yet'}
                </p>
                <p className="muted">
                  Sync:{' '}
                  {organization.last_synced_at
                    ? new Date(organization.last_synced_at).toLocaleString()
                    : organization.last_sync_error || 'Not synced yet'}
                </p>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => handleRequestOrganizationPasswordReset(organization)}
                    disabled={!organization.superadmin_username || !organization.superadmin_email}
                  >
                    Send reset link
                  </button>
                </div>
                {(!organization.superadmin_username || !organization.superadmin_email) && (
                  <p className="muted">Set both the superadmin username and email before sending a reset link.</p>
                )}
                {resetRequestResults[organization.id] && (
                  <div className="reset-note">
                    <p className="muted">
                      {resetRequestResults[organization.id].email_sent
                        ? 'Reset email sent.'
                        : 'Reset email not confirmed. You can still use the generated link below.'}
                    </p>
                    <p className="muted">{resetRequestResults[organization.id].reset_url}</p>
                    {resetRequestResults[organization.id].delivery_error && (
                      <p className="error">{resetRequestResults[organization.id].delivery_error}</p>
                    )}
                  </div>
                )}
                <button
                  type="button"
                  className="secondary"
                  onClick={() => handleDeleteOrganization(organization)}
                >
                  Delete organization
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Plans</h2>
          <div className="list">
            {plans.map((plan) => (
              <article key={plan.id} className="item">
                <h3>{plan.name}</h3>
                <p className="muted">
                  {plan.code} • {plan.currency} {plan.monthly_price}
                </p>
                <p>
                  Seats: superadmins {plan.max_superadmins}, admins {plan.max_admins}, staff{' '}
                  {plan.max_staff}, customers {plan.max_customers}
                </p>
                <p className="muted">
                  Sync:{' '}
                  {plan.last_synced_at
                    ? new Date(plan.last_synced_at).toLocaleString()
                    : plan.last_sync_error || 'Not synced yet'}
                </p>
                <button type="button" className="secondary" onClick={() => handleDeletePlan(plan)}>
                  Delete plan
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Subscriptions</h2>
          <div className="list">
            {subscriptions.map((subscription) => (
              <article key={subscription.id} className="item">
                <h3>{subscription.organization_name}</h3>
                <p className="muted">
                  {subscription.plan_name} • {subscription.status} • payment {subscription.last_payment_status}
                </p>
                <p>
                  Renews: {subscription.renews_at ? new Date(subscription.renews_at).toLocaleString() : 'Not set'}
                </p>
                <p className="muted">
                  Sync:{' '}
                  {subscription.last_synced_at
                    ? new Date(subscription.last_synced_at).toLocaleString()
                    : subscription.last_sync_error || 'Not synced yet'}
                </p>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => handleDeleteSubscription(subscription)}
                >
                  Delete subscription
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Recent license events</h2>
          <div className="list">
            {events.slice(0, 12).map((entry) => (
              <article key={entry.id} className="item">
                <h3>{entry.organization_name}</h3>
                <p className="muted">
                  {entry.action} • {entry.old_status || 'n/a'} → {entry.new_status || 'n/a'}
                </p>
                <p>{entry.notes || 'No notes provided'}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
