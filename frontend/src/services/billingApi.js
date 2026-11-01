/**
 * billingApi.js — thin wrappers over /api/billing/*.
 * (`api` already unwraps response.data and throws Error(message) on failure.)
 */
import api from './api'

export const getPlans          = () => api.get('/billing/plans')
export const getBillingStatus  = () => api.get('/billing/status')
export const getBillingHistory = () => api.get('/billing/history')
export const startCheckout     = (plan) => api.post('/billing/checkout', { plan })
export const changePlan        = (plan) => api.post('/billing/change-plan', { plan })
export const cancelSubscription = () => api.post('/billing/cancel')
export const resumeSubscription = () => api.post('/billing/resume')
export const openBillingPortal  = () => api.post('/billing/portal')
export const syncBilling        = () => api.post('/billing/sync')
