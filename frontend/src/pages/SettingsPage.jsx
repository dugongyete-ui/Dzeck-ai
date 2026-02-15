import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, Moon, Sun, Globe } from 'lucide-react'
import useStore from '../store'

function SettingsPage() {
  const { darkMode, toggleDarkMode, apiEndpoint, setApiEndpoint } = useStore()
  const [endpoint, setEndpoint] = useState(apiEndpoint)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setApiEndpoint(endpoint)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="min-h-screen">
      <header className="h-14 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex items-center px-4 gap-3">
        <Link to="/" className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
          <ChevronLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-lg font-semibold">Settings</h1>
      </header>

      <div className="max-w-2xl mx-auto p-6 space-y-8">
        <section>
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">Appearance</h2>
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {darkMode ? <Moon className="w-5 h-5 text-primary-500" /> : <Sun className="w-5 h-5 text-yellow-500" />}
                <div>
                  <p className="font-medium">Theme</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {darkMode ? 'Dark mode' : 'Light mode'}
                  </p>
                </div>
              </div>
              <button
                onClick={toggleDarkMode}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${darkMode ? 'bg-primary-500' : 'bg-gray-300'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${darkMode ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">API Configuration</h2>
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Globe className="w-4 h-4 text-primary-500" />
                <label className="font-medium text-sm">API Endpoint (Optional)</label>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Override the default API endpoint. Leave empty to use the built-in endpoint.
              </p>
              <input
                type="url"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="https://magma-api.biz.id/ai/copilot"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {saved ? 'Saved!' : 'Save'}
            </button>
          </div>
        </section>

        <section>
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">About</h2>
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              AI Agent v1.0 - An autonomous AI agent that can search the web, run terminal commands, and create/edit files to complete complex tasks.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}

export default SettingsPage
