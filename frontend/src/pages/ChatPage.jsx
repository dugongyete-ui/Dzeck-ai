import React, { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Settings, Send, Plus, MessageSquare, Bot, User, Terminal, Search, FileText, CheckCircle, Loader2, AlertCircle, ChevronLeft, Menu, X } from 'lucide-react'
import useStore from '../store'
import StatusIndicator from '../components/StatusIndicator'
import MessageBubble from '../components/MessageBubble'

function ChatPage() {
  const [input, setInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  const {
    messages, agentStatus, addMessage, setAgentStatus,
    clearMessages, conversations, startNewConversation,
    saveCurrentConversation, loadConversation, activeConversationId
  } = useStore()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  const sendMessage = async () => {
    const prompt = input.trim()
    if (!prompt || agentStatus === 'running') return

    setInput('')
    addMessage({ role: 'user', type: 'user', content: prompt })
    setAgentStatus('starting')

    try {
      const res = await fetch('/api/v1/agent/start_task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      })

      if (!res.ok) throw new Error('Failed to start task')

      const { task_id } = await res.json()

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws/agent/stream/${task_id}`)

      ws.onopen = () => setAgentStatus('running')

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'status':
            setAgentStatus(data.content.toLowerCase().includes('think') ? 'thinking' : 'running')
            break
          case 'thought':
            addMessage({ role: 'agent', type: 'thought', content: data.content })
            setAgentStatus('thinking')
            break
          case 'tool_start':
            addMessage({
              role: 'agent', type: 'tool_start',
              tool_name: data.tool_name, content: data.args
            })
            setAgentStatus(`executing: ${data.tool_name}`)
            break
          case 'tool_output':
            addMessage({
              role: 'agent', type: 'tool_output',
              tool_name: data.tool_name, content: data.output
            })
            break
          case 'final_answer':
            addMessage({ role: 'agent', type: 'final_answer', content: data.content })
            setAgentStatus('idle')
            saveCurrentConversation()
            break
          case 'error':
            addMessage({ role: 'agent', type: 'error', content: data.content })
            setAgentStatus('error')
            break
        }
      }

      ws.onerror = () => {
        addMessage({ role: 'agent', type: 'error', content: 'Connection error. Please try again.' })
        setAgentStatus('error')
      }

      ws.onclose = () => {
        if (useStore.getState().agentStatus === 'running' || useStore.getState().agentStatus === 'thinking') {
          setAgentStatus('idle')
        }
      }

    } catch (err) {
      addMessage({ role: 'agent', type: 'error', content: err.message })
      setAgentStatus('error')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleNewChat = () => {
    startNewConversation()
    setSidebarOpen(false)
  }

  const isRunning = ['running', 'thinking', 'starting'].includes(agentStatus) || agentStatus.startsWith('executing')

  return (
    <div className="flex h-screen overflow-hidden">
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <aside className={`
        fixed lg:static inset-y-0 left-0 z-40 w-72 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        flex flex-col
      `}>
        <div className="p-4 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Bot className="w-6 h-6 text-primary-500" />
              <h1 className="text-lg font-bold">AI Agent</h1>
            </div>
            <button onClick={() => setSidebarOpen(false)} className="lg:hidden p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
              <X className="w-5 h-5" />
            </button>
          </div>
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors font-medium"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
          {conversations.length === 0 && (
            <p className="text-center text-sm text-gray-400 dark:text-gray-600 mt-8">No conversations yet</p>
          )}
          {conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => { loadConversation(conv.id); setSidebarOpen(false) }}
              className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 flex items-center gap-2 text-sm transition-colors
                ${conv.id === activeConversationId
                  ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'
                }`}
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span className="truncate">{conv.title}</span>
            </button>
          ))}
        </div>

        <div className="p-3 border-t border-gray-200 dark:border-gray-800">
          <Link
            to="/settings"
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            <Settings className="w-4 h-4" />
            Settings
          </Link>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex items-center px-4 gap-3 shrink-0">
          <button onClick={() => setSidebarOpen(true)} className="lg:hidden p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <StatusIndicator status={agentStatus} />
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 scrollbar-thin">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center max-w-lg mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center mb-6">
                <Bot className="w-8 h-8 text-primary-500" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Autonomous AI Agent</h2>
              <p className="text-gray-500 dark:text-gray-400 mb-8">
                I can search the web, run commands, create files, and solve complex tasks step by step. What would you like me to do?
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
                {[
                  { icon: Search, text: 'Search for the latest news about AI' },
                  { icon: Terminal, text: 'Create a Python hello world script' },
                  { icon: FileText, text: 'Write a to-do list to a file' },
                  { icon: Bot, text: 'Explain how you work as an agent' },
                ].map((item, i) => (
                  <button
                    key={i}
                    onClick={() => { setInput(item.text) }}
                    className="flex items-center gap-3 p-3 text-left text-sm border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    <item.icon className="w-4 h-4 text-primary-500 shrink-0" />
                    <span>{item.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-1">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-2 bg-gray-100 dark:bg-gray-800 rounded-xl p-2">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your task or question..."
                rows={1}
                className="flex-1 bg-transparent resize-none outline-none px-2 py-1.5 text-sm placeholder-gray-400 dark:placeholder-gray-500 max-h-[150px]"
                disabled={isRunning}
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || isRunning}
                className="p-2 rounded-lg bg-primary-500 hover:bg-primary-600 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors shrink-0"
              >
                {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-600 mt-2 text-center">
              The agent can execute commands and browse the web. Use responsibly.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default ChatPage
