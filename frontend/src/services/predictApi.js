import api from './api'

export const getPredictions   = (id) => api.get(`/predict/${id}`)
export const retrainModel     = (id) => api.post(`/predict/${id}/retrain`)
export const getModelMetrics  = (id) => api.get(`/predict/${id}/metrics`)
export const getPredictChart  = (id) => api.get(`/predict/${id}/chart`)
