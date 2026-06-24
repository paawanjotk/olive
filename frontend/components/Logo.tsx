import { cn } from '@/lib/utils'

/**
 * Ollive brand mark — a loose, single-line olive sprig with outlined leaves.
 * Pure stroke art using `currentColor`, so it inherits the text color and can be
 * tinted anywhere: <OliveLogo size={20} className="text-emerald-400" />
 */
export function OliveLogo({
  size = 24,
  className,
  strokeWidth = 2.4,
}: {
  size?: number
  className?: string
  strokeWidth?: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn('shrink-0', className)}
      aria-hidden="true"
    >
      <defs>
        {/* one teardrop leaf: pointed base at (0,0), rounded tip at (0,-16) */}
        <path id="ollive-leaf" d="M0 0 C5 -4 6 -12 0 -16 C-6 -12 -5 -4 0 0 Z" />
      </defs>

      {/* trailing stem */}
      <path d="M27 26 C21 32 15 36 8 41" />

      {/* leaves radiating from the node, alternating sizes for an organic feel */}
      <use href="#ollive-leaf" transform="translate(27 26) rotate(-54) scale(0.9)" />
      <use href="#ollive-leaf" transform="translate(27 26) rotate(-16) scale(1)" />
      <use href="#ollive-leaf" transform="translate(27 26) rotate(24) scale(0.64)" />
      <use href="#ollive-leaf" transform="translate(27 26) rotate(66) scale(0.96)" />
      <use href="#ollive-leaf" transform="translate(27 26) rotate(112) scale(0.86)" />
    </svg>
  )
}

export default OliveLogo
