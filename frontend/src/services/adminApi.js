/** adminApi.js — wrappers over /api/admin/*  (every call needs an admin login; the server enforces it). */
import api from './api'

export const getAdminStats    = () => api.get('/admin/stats')
export const listAdminUsers   = (params) => api.get('/admin/users', { params })
export const getAdminUser     = (id) => api.get(`/admin/users/${id}`)
export const suspendUser      = (id) => api.post(`/admin/users/${id}/suspend`)
export const restoreUser      = (id) => api.post(`/admin/users/${id}/restore`)
export const setUserPlan      = (id, plan) => api.put(`/admin/users/${id}/plan`, { plan })
export const deleteUser       = (id) => api.delete(`/admin/users/${id}`)
export const getAdminActivity = (params) => api.get('/admin/activity', { params })
