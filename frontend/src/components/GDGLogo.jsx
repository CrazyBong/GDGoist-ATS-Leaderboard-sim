import React from 'react'

export default function GDGLogo({ size = 'md', showText = true, variant = 'full' }) {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16',
  }

  const textSizeClasses = {
    sm: { title: 'text-sm', subtitle: 'text-xs' },
    md: { title: 'text-base', subtitle: 'text-xs' },
    lg: { title: 'text-lg', subtitle: 'text-sm' },
    xl: { title: 'text-xl', subtitle: 'text-base' },
  }

  return (
    <div className="flex items-center gap-3">
      {/* GDG Logo - Subtle, understated */}
      <div className={`${sizeClasses[size]} relative flex items-center justify-center flex-shrink-0`}>
        <svg viewBox="0 0 120 120" className="w-full h-full opacity-90">
          {/* Blue rounded pill - left bottom */}
          <path
            d="M 15 55 Q 15 40 25 35 L 45 25 Q 55 20 60 30 L 60 80 Q 55 90 45 85 L 25 75 Q 15 70 15 55 Z"
            fill="#4285F4"
            stroke="none"
          />

          {/* Red rounded pill - top left */}
          <path
            d="M 30 15 Q 45 5 55 15 L 70 35 Q 75 45 65 55 L 50 45 Q 40 35 30 40 Z"
            fill="#EA4335"
            stroke="none"
          />

          {/* Green rounded pill - top right */}
          <path
            d="M 65 15 Q 80 10 90 20 L 100 40 Q 105 50 95 60 L 80 50 Q 70 40 65 35 Z"
            fill="#34A853"
            stroke="none"
          />

          {/* Yellow rounded pill - bottom right */}
          <path
            d="M 60 60 L 75 75 Q 90 90 80 105 Q 65 115 55 105 L 45 85 Q 40 70 60 60 Z"
            fill="#FBBC04"
            stroke="none"
          />
        </svg>
      </div>

      {showText && (
        <div className="flex flex-col leading-tight">
          {variant === 'full' ? (
            <>
              <span
                className={`${textSizeClasses[size].title} font-semibold tracking-tight`}
                style={{ color: 'var(--text-primary)' }}
              >
                ATS Leaderboard
              </span>
              <span
                className={`${textSizeClasses[size].subtitle} font-normal`}
                style={{ color: 'var(--text-muted)', opacity: 0.7 }}
              >
                GDG on Campus OIST
              </span>
            </>
          ) : (
            <span
              className={`${textSizeClasses[size].title} font-semibold tracking-tight`}
              style={{ color: 'var(--text-primary)' }}
            >
              ATS Leaderboard
            </span>
          )}
        </div>
      )}
    </div>
  )
}
