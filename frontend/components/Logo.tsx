import { cn } from '@/lib/utils'

/**
 * Ollive brand mark — a single-line olive sprig: five outlined oval leaves that
 * overlap at the center (creating the woven, hand-drawn crossing) with a trailing
 * stem. Pure stroke art using `currentColor`, so it can be tinted anywhere:
 *   <OliveLogo size={20} className="text-emerald-400" />
 */
export function OliveLogo({
  size = 24,
  className,
  strokeWidth = 2.3,
}: {
  size?: number
  className?: string
  strokeWidth?: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn('shrink-0', className)}
      aria-hidden="true"
    >
      {/* trailing stem with a soft curl */}
      <path d="M32 30 C 26 38 20 43 12.5 48" />

      {/* five oval leaves fanning out from a small central crossing */}
      <ellipse cx="27.6" cy="16.8" rx="12"   ry="7"   transform="rotate(70 27.6 16.8)" />
      <ellipse cx="39.5" cy="18.4" rx="10"   ry="6.2" transform="rotate(125 39.5 18.4)" />
      <ellipse cx="44.9" cy="27.9" rx="12"   ry="7"   transform="rotate(175 44.9 27.9)" />
      <ellipse cx="37.5" cy="40.8" rx="11.5" ry="6.8" transform="rotate(65 37.5 40.8)" />
      <ellipse cx="20.7" cy="35.5" rx="12.5" ry="7"   transform="rotate(150 20.7 35.5)" />
    </svg>
  )
}

export default OliveLogo
