import React from 'react'
import { Routes, Route } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import { NewsPage, FactorPage, DataPage, PredictionPage, AgentPage, MacroSignalLogPage, SelectStrategyPage, StrategyListPage, ChangePage } from './components/Pages'

function App() {
  return (
    <div className="app-container min-h-screen">
      <MainLayout>
        <Routes>
          <Route path="/" element={<NewsPage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/factors" element={<FactorPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/prediction" element={<PredictionPage />} />
          <Route path="/agents" element={<AgentPage />} />
          <Route path="/macro-signal-logs" element={<MacroSignalLogPage />} />
          <Route path="/select-strategy" element={<SelectStrategyPage />} />
          <Route path="/strategies" element={<StrategyListPage />} />
          <Route path="/change" element={<ChangePage />} />
        </Routes>
      </MainLayout>
    </div>
  )
}

export default App
