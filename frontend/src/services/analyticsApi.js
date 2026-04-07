import api from './api'

export const uploadFile     = (formData) => api.post('/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const listFiles      = ()         => api.get('/upload/files')
export const deleteFile     = (id)       => api.delete(`/upload/files/${id}`)
export const previewFile    = (id, rows=10) => api.get(`/upload/preview/${id}?rows=${rows}`)
export const validateFile   = (id)       => api.get(`/upload/validate/${id}`)

export const getAnalytics   = (id)       => api.get(`/analytics/${id}`)
export const getKPIs        = (id)       => api.get(`/analytics/${id}/kpis`)
export const getMonthlySales= (id)       => api.get(`/analytics/${id}/monthly`)
export const getTopProducts = (id, limit=10) => api.get(`/analytics/${id}/products?limit=${limit}`)
export const getRegions     = (id)       => api.get(`/analytics/${id}/regions`)
export const getSummary     = (id)       => api.get(`/analytics/${id}/summary`)

export const getAllCharts    = (id)       => api.get(`/visualize/${id}`)
export const getTrendChart  = (id)       => api.get(`/visualize/${id}/trend`)
export const getProductsChart=(id,limit=8)=>api.get(`/visualize/${id}/products?limit=${limit}`)
export const getCategoryChart=(id)       => api.get(`/visualize/${id}/category`)
export const getRegionsChart = (id)      => api.get(`/visualize/${id}/regions`)
