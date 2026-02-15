import React, { useState } from 'react'
import { User, Bot, Brain, Terminal, Search, FileText, CheckCircle, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'

function MessageBubble({ message }) {
  const [expanded, setExpanded] = useState(false)
  const { type, content, tool_name, role } = message

  if (type === 'user') {
    return (
      <div className="flex gap-3 py-4">
        <div className="w-8 h-8 rounded-lg bg-primary-100 dark:bg-primary-900/40 flex items-center justify-center shrink-0">
          <User className="w-4 h-4 text-primary-600 dark:text-primary-400" />
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
        </div>
      </div>
    )
  }

  if (type === 'thought') {
    return (
      <div className="flex gap-3 py-2">
        <div className="w-8 h-8 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0">
          <Brain className="w-4 h-4 text-purple-500" />
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <p className="text-xs font-medium text-purple-500 mb-1">Thinking</p>
          <p className="text-sm text-gray-600 dark:text-gray-400 italic">{content}</p>
        </div>
      </div>
    )
  }

  if (type === 'tool_start') {
    const toolIcon = tool_name === 'web_search' ? Search
      : tool_name === 'terminal' ? Terminal
      : tool_name === 'file_editor' ? FileText
      : Terminal

    let parsedArgs = content
    try {
      parsedArgs = JSON.stringify(JSON.parse(content), null, 2)
    } catch {}

    return (
      <div className="flex gap-3 py-2">
        <div className="w-8 h-8 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center shrink-0">
          {React.createElement(toolIcon, { className: "w-4 h-4 text-orange-500" })}
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs font-medium text-orange-500 hover:text-orange-600 mb-1"
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            Running: {tool_name}
          </button>
          {expanded && (
            <pre className="text-xs bg-gray-100 dark:bg-gray-800 rounded-lg p-3 overflow-x-auto">{parsedArgs}</pre>
          )}
        </div>
      </div>
    )
  }

  if (type === 'tool_output') {
    return (
      <div className="flex gap-3 py-2 ml-11">
        <div className="flex-1 min-w-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-600 mb-1"
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            Output ({tool_name})
          </button>
          {expanded && (
            <pre className="text-xs bg-gray-100 dark:bg-gray-800 rounded-lg p-3 overflow-x-auto max-h-60">{content}</pre>
          )}
        </div>
      </div>
    )
  }

  if (type === 'final_answer') {
    return (
      <div className="flex gap-3 py-4">
        <div className="w-8 h-8 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center shrink-0">
          <CheckCircle className="w-4 h-4 text-green-500" />
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <p className="text-xs font-medium text-green-500 mb-1">Result</p>
          <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
        </div>
      </div>
    )
  }

  if (type === 'error') {
    return (
      <div className="flex gap-3 py-3">
        <div className="w-8 h-8 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
          <AlertCircle className="w-4 h-4 text-red-500" />
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <p className="text-xs font-medium text-red-500 mb-1">Error</p>
          <p className="text-sm text-red-600 dark:text-red-400">{content}</p>
        </div>
      </div>
    )
  }

  return null
}

export default MessageBubble
