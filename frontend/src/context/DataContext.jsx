import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { listFiles, getAnalytics, getAllCharts } from '../services/analyticsApi'

const DataContext = createContext(null)

export function DataProvider({ children }) {
  const [selectedFileId, setSelectedFileId] = useState(null)
  const [files,    setFiles]    = useState([])
  const [analytics,setAnalytics]= useState(null)
  const [charts,   setCharts]   = useState(null)
  const [loadingFiles,     setLoadingFiles]     = useState(false)
  const [loadingAnalytics, setLoadingAnalytics] = useState(false)
  const [error, setError] = useState(null)

  const loadAnalytics = useCallback(async (fileId) => {
    if (!fileId) return
    setLoadingAnalytics(true)
    setAnalytics(null)
    setCharts(null)
    setError(null)
    try {
      const [analyticsData, chartsData] = await Promise.all([
        getAnalytics(fileId),
        getAllCharts(fileId),
      ])
      setAnalytics(analyticsData)
      setCharts(chartsData)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingAnalytics(false)
    }
  }, [])

  const refreshFiles = useCallback(async () => {
    setLoadingFiles(true)
    setError(null)
    try {
      const data = await listFiles()
      setFiles(data)
      if (data.length > 0) {
        const firstId = data[0].id
        setSelectedFileId(firstId)
        await loadAnalytics(firstId)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingFiles(false)
    }
  }, [loadAnalytics])

  const selectFile = useCallback(async (fileId) => {
    setSelectedFileId(fileId)
    await loadAnalytics(fileId)
  }, [loadAnalytics])

  useEffect(() => {
    refreshFiles()
  }, [])

  const clearError = () => setError(null)

  return (
    <DataContext.Provider value={{
      selectedFileId, setSelectedFileId,
      files, refreshFiles, loadingFiles,
      analytics, charts, loadingAnalytics,
      error, clearError, selectFile,
    }}>
      {children}
    </DataContext.Provider>
  )
}

export const useData = () => {
  const ctx = useContext(DataContext)
  if (!ctx) throw new Error('useData must be used inside <DataProvider>')
  return ctx
}
