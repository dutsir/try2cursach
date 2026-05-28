import type { ReactNode } from 'react'

interface ScoutProps {
  size?: number
  state?: 'idle' | 'watching' | 'alert' | 'happy' | 'sleeping'
  glow?: boolean
  className?: string
}

export function Scout({ size = 200, state = 'idle', glow = false, className }: ScoutProps) {
  const s = size
  const eyeY = state === 'sleeping' ? 0.52 : 0.48
  const eyeR = state === 'sleeping' ? 0.005 : state === 'alert' ? 0.075 : 0.06
  const eyeShape = state === 'sleeping' ? 'line' : 'circle'
  const accent = '#A855F7'
  const mouthY = 0.66
  const eyeOffsetX = state === 'watching' ? 0.015 : 0

  let mouth: ReactNode
  if (state === 'happy') {
    mouth = (
      <path
        d={`M ${s * 0.4} ${s * mouthY} Q ${s * 0.5} ${s * (mouthY + 0.06)} ${s * 0.6} ${s * mouthY}`}
        stroke={accent}
        strokeWidth={s * 0.018}
        strokeLinecap="round"
        fill="none"
      />
    )
  } else if (state === 'alert') {
    mouth = (
      <rect
        x={s * 0.46}
        y={s * (mouthY - 0.005)}
        width={s * 0.08}
        height={s * 0.012}
        rx={s * 0.006}
        fill={accent}
      />
    )
  } else if (state === 'sleeping') {
    mouth = (
      <g fill="#666">
        <circle cx={s * 0.5} cy={s * mouthY} r={s * 0.012} />
      </g>
    )
  } else {
    mouth = (
      <rect
        x={s * 0.44}
        y={s * (mouthY - 0.005)}
        width={s * 0.12}
        height={s * 0.01}
        rx={s * 0.005}
        fill="#444"
      />
    )
  }

  return (
    <svg
      width={s}
      height={s}
      viewBox={`0 0 ${s} ${s}`}
      className={className}
      style={{ overflow: 'visible' }}
    >
      {glow && <circle cx={s * 0.5} cy={s * 0.55} r={s * 0.42} fill="url(#scout-glow)" opacity={0.4} />}
      <defs>
        <radialGradient id="scout-glow">
          <stop offset="0%" stopColor={accent} stopOpacity="0.4" />
          <stop offset="100%" stopColor={accent} stopOpacity="0" />
        </radialGradient>
      </defs>

      <line x1={s * 0.5} y1={s * 0.2} x2={s * 0.5} y2={s * 0.08} stroke={accent} strokeWidth={s * 0.012} strokeLinecap="round" />
      <circle cx={s * 0.5} cy={s * 0.07} r={s * 0.022} fill={accent} />
      {state === 'alert' && (
        <circle cx={s * 0.5} cy={s * 0.07} r={s * 0.045} fill="none" stroke={accent} strokeWidth={s * 0.008} opacity={0.5}>
          <animate attributeName="r" from={s * 0.022} to={s * 0.08} dur="1.2s" repeatCount="indefinite" />
          <animate attributeName="opacity" from="0.6" to="0" dur="1.2s" repeatCount="indefinite" />
        </circle>
      )}

      <rect
        x={s * 0.2}
        y={s * 0.22}
        width={s * 0.6}
        height={s * 0.62}
        rx={s * 0.14}
        fill="#141414"
        stroke={accent}
        strokeWidth={s * 0.012}
      />
      <rect x={s * 0.24} y={s * 0.4} width={s * 0.52} height={s * 0.18} rx={s * 0.04} fill="#0A0A0A" />

      {eyeShape === 'circle' ? (
        <g fill="#F5F5F5">
          <circle cx={s * (0.4 + eyeOffsetX)} cy={s * eyeY} r={s * eyeR}>
            <animate
              attributeName="r"
              values={`${s * eyeR};${s * eyeR};${s * 0.005};${s * eyeR}`}
              keyTimes="0;0.93;0.96;1"
              dur="4s"
              repeatCount="indefinite"
            />
          </circle>
          <circle cx={s * (0.6 + eyeOffsetX)} cy={s * eyeY} r={s * eyeR}>
            <animate
              attributeName="r"
              values={`${s * eyeR};${s * eyeR};${s * 0.005};${s * eyeR}`}
              keyTimes="0;0.93;0.96;1"
              dur="4s"
              repeatCount="indefinite"
            />
          </circle>
        </g>
      ) : (
        <g stroke="#F5F5F5" strokeWidth={s * 0.012} strokeLinecap="round">
          <line x1={s * 0.36} y1={s * eyeY} x2={s * 0.44} y2={s * eyeY} />
          <line x1={s * 0.56} y1={s * eyeY} x2={s * 0.64} y2={s * eyeY} />
        </g>
      )}

      {state === 'alert' && <circle cx={s * 0.66} cy={s * 0.43} r={s * 0.018} fill="#EF4444" />}
      {mouth}

      <rect x={s * 0.3} y={s * 0.84} width={s * 0.1} height={s * 0.04} rx={s * 0.012} fill="#262626" />
      <rect x={s * 0.6} y={s * 0.84} width={s * 0.1} height={s * 0.04} rx={s * 0.012} fill="#262626" />

      {state === 'sleeping' && (
        <g fill={accent} fontFamily="Inter, system-ui" fontSize={s * 0.07} fontWeight={600}>
          <text x={s * 0.78} y={s * 0.3}>z</text>
          <text x={s * 0.85} y={s * 0.22}>z</text>
        </g>
      )}
    </svg>
  )
}
