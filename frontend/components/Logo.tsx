import { cn } from '@/lib/utils'

/**
 * Ollive brand mark — five simple outlined leaves arranged in a pentagon (72°
 * apart). Pure stroke art using `currentColor`, so it can be tinted anywhere:
 *   <OliveLogo size={20} className="text-emerald-400" />
 */
export function OliveLogo({
  size = 24,
  className,
  strokeWidth = 2.2,
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
      <defs>
        {/* one leaf: pointed base at the center (0,0), rounded tip outward at (0,-19) */}
        <path id="ollive-leaf" d="M0 0 C5 -5 5.4 -13 0 -19 C-5.4 -13 -5 -5 0 0 Z" />
      </defs>

      {/* five leaves radiating from the center, 72° apart */}
      <g transform="translate(32 32)">
        <use href="#ollive-leaf" transform="rotate(0)" />
        <use href="#ollive-leaf" transform="rotate(72)" />
        <use href="#ollive-leaf" transform="rotate(144)" />
        <use href="#ollive-leaf" transform="rotate(216)" />
        <use href="#ollive-leaf" transform="rotate(288)" />
      </g>
    </svg>
  )
}

export default OliveLogo
