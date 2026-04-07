/**
 * DataContext.jsx
 * ───────────────
 * Global state provider. Stores:
 *   - selectedFileId: the currently active upload
 *   - files: list of all uploaded files
 *   - analytics: cached analytics for the selected file
 *   - charts: cached visualization data
 *   - loading/error states per section
 *
 * Components read from context instead of each making their own API calls,
 * which prevents redundant requests when switching pages.
 */
import React, { createContext, useContext, useState, useCallback } from 'react'
import { listFiles, getAnalytics, getAllCharts } from '../services/analyticsApi'

const DataContext = createContext(null)

export function DataProvider({ children }) {
  const [selectedFileId, setSelectedFileId] = useState(null)
  const [files,    setFiles]    = useState([])
  const [analytics,setAnalytics]= useState(null)
  const [charts,   setCharts]   = useState(null)
  const [loadingFiles,    setLoadingFiles]    = useState(false)
  const [loadingAnalytics,setLoadingAnalytics]= useState(false)
  const [error, setError] = useState(null)

  // ── Fetch file list ────────────────────────────────────────────────────────
  const refreshFiles = useCallback(async () => {
    setLoadingFiles(true)
    setError(null)
    try {
      const data = await listFiles()
      setFiles(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingFiles(false)
    }
  }, [])

  // ── Select a file and load its analytics + charts ─────────────────────────
  const selectFile = useCallback(async (fileId) => {
    if (fileId === selectedFileId) return
    setSelectedFileId(fileId)
    setAnalytics(null)
    setCharts(null)
    setLoadingAnalytics(true)
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
  }, [selectedFileId])

  const clearError = () => setError(null)

  return (
    <DataContext.Provider value={{
      selectedFileId, setSelectedFileId,
      files, refreshFiles, loadingFiles,
      analytics, charts, loadingAnalytics,
      error, clearError,
      selectFile,
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
