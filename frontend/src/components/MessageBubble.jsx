import React, { useState } from 'react'
import { User, Bot, Brain, Terminal, Search, FileText, CheckCircle, AlertCircle, ChevronDown, ChevronRight, RefreshCw, Zap, Clock } from 'lucide-react'

function MessageBubble({ message }) {
  const [expanded, setExpanded] = useState(false)
  const { type, content, tool_name, role, step, retry_attempt, max_retries, has_error, steps_taken, retries } = message

  if (type === 'user') {
    return (
      <div className="flex gap-3 py-4 animate-fade-in">
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
      <div className="flex gap-3 py-2 animate-fade-in">
        <div className="w-8 h-8 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center shrink-0">
          <Brain className="w-4 h-4 text-purple-500 animate-pulse" />
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-xs font-medium text-purple-500">Thinking</p>
            {step && <span className="text-[10px] text-purple-400 bg-purple-50 dark:bg-purple-900/20 px-1.5 py-0.5 rounded-full">Step {step}</span>}
          </div>
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

    const toolLabel = tool_name === 'web_search' ? 'Web Search'
      : tool_name === 'terminal' ? 'Terminal'
      : tool_name === 'file_editor' ? 'File Editor'
      : tool_name

    let parsedArgs = content
    try {
      parsedArgs = JSON.stringify(JSON.parse(content), null, 2)
    } catch {}

    return (
      <div className="flex gap-3 py-2 animate-fade-in">
        <div className="w-8 h-8 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center shrink-0">
          {React.createElement(toolIcon, { className: "w-4 h-4 text-orange-500" })}
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 text-xs font-medium text-orange-500 hover:text-orange-600 transition-colors mb-1"
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <Zap className="w-3 h-3" />
            Running: {toolLabel}
            {step && <span className="text-[10px] text-orange-400 bg-orange-50 dark:bg-orange-900/20 px-1.5 py-0.5 rounded-full ml-1">Step {step}</span>}
          </button>
          {expanded && (
            <pre className="text-xs bg-gray-900 dark:bg-gray-800 text-green-400 rounded-lg p-3 overflow-x-auto font-mono border border-gray-700">{parsedArgs}</pre>
          )}
        </div>
      </div>
    )
  }

  if (type === 'tool_output') {
    const isError = has_error || (content && (
      content.includes('Error') || content.includes('Traceback') || content.includes('exit code: 1')
    ))

    return (
      <div className="flex gap-3 py-2 ml-11 animate-fade-in">
        <div className="flex-1 min-w-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className={`flex items-center gap-1.5 text-xs font-medium mb-1 transition-colors ${
              isError
                ? 'text-red-500 hover:text-red-600'
                : 'text-gray-500 hover:text-gray-600'
            }`}
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {isError ? <AlertCircle className="w-3 h-3" /> : <CheckCircle className="w-3 h-3" />}
            Output ({tool_name}) {isError && <span className="text-red-400 bg-red-50 dark:bg-red-900/20 px-1.5 py-0.5 rounded-full text-[10px]">Error</span>}
          </button>
          {expanded && (
            <pre className={`text-xs rounded-lg p-3 overflow-x-auto max-h-60 font-mono border ${
              isError
                ? 'bg-red-950/50 text-red-300 border-red-800'
                : 'bg-gray-900 dark:bg-gray-800 text-gray-300 border-gray-700'
            }`}>{content}</pre>
          )}
        </div>
      </div>
    )
  }

  if (type === 'self_correction') {
    return (
      <div className="flex gap-3 py-2 animate-fade-in">
        <div className="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0">
          <RefreshCw className="w-4 h-4 text-amber-500 animate-spin" />
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-xs font-semibold text-amber-600 dark:text-amber-400">Self-Correction</p>
            {retry_attempt && max_retries && (
              <span className="text-[10px] text-amber-500 bg-amber-50 dark:bg-amber-900/20 px-1.5 py-0.5 rounded-full">
                Attempt {retry_attempt}/{max_retries}
              </span>
            )}
          </div>
          <p className="text-sm text-amber-700 dark:text-amber-300">{content}</p>
          {message.error_snippet && (
            <pre className="text-xs bg-red-950/30 text-red-300 rounded-lg p-2 mt-2 overflow-x-auto font-mono border border-red-800/50 max-h-20">
              {message.error_snippet}
            </pre>
          )}
        </div>
      </div>
    )
  }

  if (type === 'final_answer') {
    return (
      <div className="flex gap-3 py-4 animate-fade-in">
        <div className="w-8 h-8 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center shrink-0">
          <CheckCircle className="w-4 h-4 text-green-500" />
        </div>
        <div className="flex-1 min-w-0 pt-1">
          <p className="text-xs font-medium text-green-500 mb-1">Result</p>
          <p className="text-sm whitespace-pre-wrap break-words">{content}</p>
          {(steps_taken || retries > 0) && (
            <div className="flex items-center gap-3 mt-3 text-[10px] text-gray-400">
              {steps_taken && (
                <span className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded-full">
                  <Clock className="w-3 h-3" />
                  {steps_taken} steps
                </span>
              )}
              {retries > 0 && (
                <span className="flex items-center gap-1 bg-amber-50 dark:bg-amber-900/20 text-amber-500 px-2 py-1 rounded-full">
                  <RefreshCw className="w-3 h-3" />
                  {retries} retries
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  if (type === 'error') {
    return (
      <div className="flex gap-3 py-3 animate-fade-in">
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
