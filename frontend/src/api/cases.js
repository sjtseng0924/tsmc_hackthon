const mockCases = [
  {
    id: 'INC-20240215-01',
    title: 'Payment gateway timeout during peak traffic',
    category: 'Payments',
    severity: 'high',
    rootCause: 'Upstream gateway rate limit triggered cascading retries.',
    tags: ['payment', 'latency', 'rate-limit'],
    summary: 'Peak-hour traffic overwhelmed the payment gateway, causing request timeouts.',
    timeline: [
      '13:02 - Alerts fired for increased timeout rate.',
      '13:05 - On-call identified gateway 429 responses.',
      '13:12 - Retry policy adjusted to backoff.',
      '13:30 - Error rate returned to baseline.',
    ],
    immediateFix: 'Reduce retry aggressiveness and enable request jitter.',
    longTermFix: 'Implement circuit breaker + negotiate higher quota with provider.',
    references: [
      { label: 'Gateway status incident', url: 'https://status.example.com/incident/123' },
    ],
  },
  {
    id: 'INC-20240128-04',
    title: 'Batch job stalled on nightly inventory sync',
    category: 'Data Pipeline',
    severity: 'medium',
    rootCause: 'Deadlock in inventory update transaction.',
    tags: ['batch', 'database', 'deadlock'],
    summary: 'Nightly batch stalled, causing inventory lag for 2 hours.',
    timeline: [
      '01:00 - Batch job started.',
      '01:12 - Deadlock detected, retries began.',
      '01:40 - Job still blocked, escalation triggered.',
      '02:05 - Manual rollback executed.',
    ],
    immediateFix: 'Killed deadlocked transaction and reran job.',
    longTermFix: 'Add index and refactor transaction order to avoid locking.',
    references: [
      { label: 'Postmortem doc', url: 'https://confluence.example.com/postmortem/456' },
    ],
  },
  {
    id: 'INC-20240105-02',
    title: 'User login latency spike',
    category: 'Authentication',
    severity: 'low',
    rootCause: 'Cache warm-up after deployment increased auth lookup time.',
    tags: ['auth', 'cache', 'deploy'],
    summary: 'Login latency spiked briefly after rollout but recovered quickly.',
    timeline: [
      '09:00 - Deployment completed.',
      '09:03 - Latency alert triggered.',
      '09:10 - Cache warmed, latency normalized.',
    ],
    immediateFix: 'Scaled auth service during warm-up window.',
    longTermFix: 'Introduce pre-warm step before deployment cutover.',
    references: [
      { label: 'Runbook - Auth latency', url: 'https://runbooks.example.com/auth-latency' },
    ],
  },
]

export const getCases = () => {
  // TODO: Replace mock data with backend API
  return mockCases
}

export const getCaseById = (id) => {
  // TODO: Replace mock data with backend API
  return mockCases.find((item) => item.id === id)
}

export const getCategories = () => {
  // TODO: Replace mock data with backend API
  return [...new Set(mockCases.map((item) => item.category))]
}