/**
 * Format a date string to a localized format.
 * @param dateString - ISO date string
 * @param format - Format type: 'full', 'short', 'time', or 'datetime'
 * @returns Formatted date string
 */
export function formatDate(
  dateString: string,
  format: 'full' | 'short' | 'time' | 'datetime' = 'datetime'
): string {
  const date = new Date(dateString)

  if (isNaN(date.getTime())) {
    return '-'
  }

  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }

  switch (format) {
    case 'full':
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    case 'short':
      return date.toLocaleDateString('zh-CN', options)
    case 'time':
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      })
    case 'datetime':
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    default:
      return date.toLocaleString('zh-CN')
  }
}

/**
 * Get relative time string (e.g., "5 minutes ago").
 * @param dateString - ISO date string
 * @returns Relative time string
 */
export function getRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) {
    return '刚刚'
  } else if (diffMins < 60) {
    return `${diffMins} 分钟前`
  } else if (diffHours < 24) {
    return `${diffHours} 小时前`
  } else if (diffDays < 7) {
    return `${diffDays} 天前`
  } else {
    return formatDate(dateString, 'short')
  }
}

/**
 * Format a duration in seconds to readable string.
 * @param seconds - Duration in seconds
 * @returns Formatted duration string
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}秒`
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return secs > 0 ? `${mins}分${secs}秒` : `${mins}分钟`
  } else {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return mins > 0 ? `${hours}小时${mins}分钟` : `${hours}小时`
  }
}
