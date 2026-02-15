import React from 'react'
import { Loader2, CheckCircle, AlertCircle, Brain, Wrench, Zap } from 'lucide-react'

const statusConfig = {
  idle: { icon: CheckCircle, text: 'Ready', color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30' },
  starting: { icon: Zap, text: 'Starting...', color: 'text-yellow-500', bg: 'bg-yellow-100 dark:bg-yellow-900/30', pulse: true },
  thinking: { icon: Brain, text: 'Thinking...', color: 'text-purple-500', bg: 'bg-purple-100 dark:bg-purple-900/30', pulse: true },
  running: { icon: Loader2, text: 'Working...', color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', spin: true },
  error: { icon: AlertCircle, text: 'Error', color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30' },
}

function StatusIndicator({ status }) {
  let config = statusConfig[status]

  if (!config && status?.startsWith('executing:')) {
    const toolName = status.split(':')[1]?.trim()
    config = {
      icon: Wrench,
      text: `Executing: ${toolName}`,
      color: 'text-orange-500',
      bg: 'bg-orange-100 dark:bg-orange-900/30',
      pulse: true,
    }
  }

  if (!config) config = statusConfig.idle

  const Icon = config.icon

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${config.bg} ${config.color}`}>
      <Icon className={`w-3.5 h-3.5 ${config.spin ? 'animate-spin' : ''} ${config.pulse ? 'animate-pulse' : ''}`} />
      {config.text}
    </div>
  )
}

export default StatusIndicator
