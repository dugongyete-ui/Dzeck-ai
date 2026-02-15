import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import useStore from './store'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'

function App() {
  const darkMode = useStore((s) => s.darkMode)

  return (
    <div className={darkMode ? 'dark' : ''}>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 transition-colors">
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </BrowserRouter>
      </div>
    </div>
  )
}

export default App
