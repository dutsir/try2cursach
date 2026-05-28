// Shared: Scout mascot, charts, marketplace tags, utility components.
// All consumers expect these on window.

// ---- Scout mascot (simple geometric: rounded square + dot eyes + antenna) ----
function Scout({ size = 200, state = 'idle', glow = false }) {
  // states: idle | watching | alert | happy | sleeping
  const s = size;
  const eyeY = state === 'sleeping' ? 0.52 : 0.48;
  const eyeR = state === 'sleeping' ? 0.005 : (state === 'alert' ? 0.075 : 0.06);
  const eyeShape = state === 'sleeping' ? 'line' : 'circle';
  const accent = '#A855F7';
  const mouthY = 0.66;
  // mouth element varies per state
  let mouth = null;
  if (state === 'happy') {
    mouth = <path d={`M ${s*0.40} ${s*mouthY} Q ${s*0.5} ${s*(mouthY+0.06)} ${s*0.60} ${s*mouthY}`} stroke="#A855F7" strokeWidth={s*0.018} strokeLinecap="round" fill="none" />;
  } else if (state === 'alert') {
    mouth = <rect x={s*0.46} y={s*(mouthY-0.005)} width={s*0.08} height={s*0.012} rx={s*0.006} fill="#A855F7" />;
  } else if (state === 'sleeping') {
    // zzz dots
    mouth = (
      <g fill="#666">
        <circle cx={s*0.50} cy={s*mouthY} r={s*0.012}/>
      </g>
    );
  } else {
    mouth = <rect x={s*0.44} y={s*(mouthY-0.005)} width={s*0.12} height={s*0.010} rx={s*0.005} fill="#444" />;
  }

  const eyeOffsetX = state === 'watching' ? 0.015 : 0;

  return (
    <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} style={{ overflow: 'visible' }}>
      {glow && (
        <circle cx={s*0.5} cy={s*0.55} r={s*0.42} fill="url(#scout-glow)" opacity="0.4" />
      )}
      <defs>
        <radialGradient id="scout-glow">
          <stop offset="0%" stopColor="#A855F7" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#A855F7" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* antenna */}
      <line x1={s*0.5} y1={s*0.20} x2={s*0.5} y2={s*0.08} stroke={accent} strokeWidth={s*0.012} strokeLinecap="round" />
      <circle cx={s*0.5} cy={s*0.07} r={s*0.022} fill={accent} />
      {state === 'alert' && (
        <circle cx={s*0.5} cy={s*0.07} r={s*0.045} fill="none" stroke={accent} strokeWidth={s*0.008} opacity="0.5">
          <animate attributeName="r" from={s*0.022} to={s*0.08} dur="1.2s" repeatCount="indefinite" />
          <animate attributeName="opacity" from="0.6" to="0" dur="1.2s" repeatCount="indefinite" />
        </circle>
      )}
      {/* body */}
      <rect
        x={s*0.20} y={s*0.22} width={s*0.60} height={s*0.62}
        rx={s*0.14}
        fill="#141414"
        stroke={accent}
        strokeWidth={s*0.012}
      />
      {/* visor strip */}
      <rect x={s*0.24} y={s*0.40} width={s*0.52} height={s*0.18} rx={s*0.04} fill="#0A0A0A" />
      {/* eyes */}
      {eyeShape === 'circle' ? (
        <g fill="#F5F5F5">
          <circle cx={s*(0.40 + eyeOffsetX)} cy={s*eyeY} r={s*eyeR}>
            <animate attributeName="r" values={`${s*eyeR};${s*eyeR};${s*0.005};${s*eyeR}`} keyTimes="0;0.93;0.96;1" dur="4s" repeatCount="indefinite" />
          </circle>
          <circle cx={s*(0.60 + eyeOffsetX)} cy={s*eyeY} r={s*eyeR}>
            <animate attributeName="r" values={`${s*eyeR};${s*eyeR};${s*0.005};${s*eyeR}`} keyTimes="0;0.93;0.96;1" dur="4s" repeatCount="indefinite" />
          </circle>
        </g>
      ) : (
        <g stroke="#F5F5F5" strokeWidth={s*0.012} strokeLinecap="round">
          <line x1={s*0.36} y1={s*eyeY} x2={s*0.44} y2={s*eyeY} />
          <line x1={s*0.56} y1={s*eyeY} x2={s*0.64} y2={s*eyeY} />
        </g>
      )}
      {/* small accent at eye corner when alert */}
      {state === 'alert' && (
        <circle cx={s*0.66} cy={s*0.43} r={s*0.018} fill="#EF4444" />
      )}
      {mouth}
      {/* feet/base hint */}
      <rect x={s*0.30} y={s*0.84} width={s*0.10} height={s*0.04} rx={s*0.012} fill="#262626" />
      <rect x={s*0.60} y={s*0.84} width={s*0.10} height={s*0.04} rx={s*0.012} fill="#262626" />

      {state === 'sleeping' && (
        <g fill="#A855F7" fontFamily="Inter, system-ui" fontSize={s*0.07} fontWeight="600">
          <text x={s*0.78} y={s*0.30}>z</text>
          <text x={s*0.85} y={s*0.22}>z</text>
        </g>
      )}
    </svg>
  );
}

// ---- Sparkline (mini chart) ----
function Sparkline({ data, width = 120, height = 36, color = '#10B981', fill = true }) {
  if (!data || data.length === 0) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const w = width - pad*2;
  const h = height - pad*2;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * w;
    const y = pad + h - ((v - min) / range) * h;
    return [x, y];
  });
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  const area = fill
    ? `${path} L ${pts[pts.length-1][0].toFixed(1)} ${height} L ${pts[0][0].toFixed(1)} ${height} Z`
    : null;
  const gradId = `spark-g-${color.replace('#','')}-${Math.random().toString(36).slice(2,7)}`;
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${gradId})`} />}
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="2.2" fill={color} />
    </svg>
  );
}

// ---- Full chart (for product detail) ----
function PriceChart({ data, width = 760, height = 320, accent = '#A855F7', hoverIdx, onHover }) {
  const min = Math.min(...data.map(d => d.price));
  const max = Math.max(...data.map(d => d.price));
  const range = max - min || 1;
  const padL = 56, padR = 24, padT = 24, padB = 36;
  const w = width - padL - padR;
  const h = height - padT - padB;
  const pts = data.map((d, i) => {
    const x = padL + (i / (data.length - 1)) * w;
    const y = padT + h - ((d.price - min) / range) * h;
    return { x, y, ...d };
  });
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const area = `${path} L ${pts[pts.length-1].x.toFixed(1)} ${padT + h} L ${pts[0].x.toFixed(1)} ${padT + h} Z`;

  // y-axis ticks
  const ticks = 5;
  const yTicks = Array.from({ length: ticks }, (_, i) => {
    const v = min + (range / (ticks - 1)) * i;
    const y = padT + h - (i / (ticks - 1)) * h;
    return { v: Math.round(v), y };
  });

  // x-axis: pick ~6 labels
  const xLabels = [0, Math.floor(data.length*0.2), Math.floor(data.length*0.4), Math.floor(data.length*0.6), Math.floor(data.length*0.8), data.length - 1];

  function handleMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * width;
    const idx = Math.round(((x - padL) / w) * (data.length - 1));
    if (idx >= 0 && idx < data.length) onHover && onHover(idx);
  }

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      onMouseMove={handleMove}
      onMouseLeave={() => onHover && onHover(null)}
      style={{ display: 'block' }}
    >
      <defs>
        <linearGradient id="chart-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.22" />
          <stop offset="100%" stopColor={accent} stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* grid */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} y1={t.y} x2={width - padR} y2={t.y} stroke="#1C1C1C" strokeWidth="1" />
          <text x={padL - 10} y={t.y + 4} textAnchor="end" fill="#666" fontSize="11" fontFamily="Inter">
            {t.v.toLocaleString('ru-RU')} ₽
          </text>
        </g>
      ))}
      {/* x labels */}
      {xLabels.map((idx, i) => (
        <text key={i} x={pts[idx]?.x} y={height - 12} textAnchor="middle" fill="#666" fontSize="11" fontFamily="Inter">
          {pts[idx]?.label}
        </text>
      ))}
      {/* area + line */}
      <path d={area} fill="url(#chart-area)" />
      <path d={path} fill="none" stroke={accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

      {/* hover indicator */}
      {hoverIdx != null && pts[hoverIdx] && (
        <g>
          <line x1={pts[hoverIdx].x} y1={padT} x2={pts[hoverIdx].x} y2={padT + h} stroke="#2E2E2E" strokeWidth="1" strokeDasharray="3 3" />
          <circle cx={pts[hoverIdx].x} cy={pts[hoverIdx].y} r="5" fill="#0A0A0A" stroke={accent} strokeWidth="2" />
          <g transform={`translate(${pts[hoverIdx].x + 12}, ${pts[hoverIdx].y - 28})`}>
            <rect x="0" y="0" width="130" height="44" rx="6" fill="#141414" stroke="#2E2E2E" />
            <text x="10" y="18" fill="#A3A3A3" fontSize="11" fontFamily="Inter">{pts[hoverIdx].label}</text>
            <text x="10" y="35" fill="#F5F5F5" fontSize="14" fontFamily="Inter" fontWeight="600">{pts[hoverIdx].price.toLocaleString('ru-RU')} ₽</text>
          </g>
        </g>
      )}
    </svg>
  );
}

// ---- Marketplace tag (text-only) ----
function MarketplaceTag({ source, size = 'sm' }) {
  const map = {
    wb: { label: 'WB', full: 'Wildberries' },
    ozon: { label: 'OZ', full: 'Ozon' },
    dns: { label: 'DNS', full: 'DNS' },
    citilink: { label: 'CL', full: 'Citilink' },
    regard: { label: 'RG', full: 'Regard' },
  };
  const m = map[source] || { label: source, full: source };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'Inter', fontSize: size === 'sm' ? 11 : 12, fontWeight: 600,
      letterSpacing: '0.08em', textTransform: 'uppercase',
      color: '#A3A3A3',
      padding: size === 'sm' ? '4px 8px' : '6px 10px',
      border: '1px solid #2E2E2E', borderRadius: 4,
      background: '#141414',
    }}>{m.full}</span>
  );
}

// ---- Verdict badge ----
function VerdictBadge({ verdict, size = 'sm' }) {
  // verdict: buy | wait | monitor
  const map = {
    buy: { label: 'Buy Now', color: '#10B981', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.3)' },
    wait: { label: 'Wait', color: '#EF4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.3)' },
    monitor: { label: 'Monitor', color: '#F59E0B', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.3)' },
  };
  const v = map[verdict];
  if (!v) return null;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'Inter', fontSize: size === 'sm' ? 11 : 13, fontWeight: 600,
      letterSpacing: '0.06em', textTransform: 'uppercase',
      color: v.color,
      padding: size === 'sm' ? '4px 8px' : '8px 12px',
      border: `1px solid ${v.border}`, borderRadius: 4,
      background: v.bg,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: v.color, boxShadow: `0 0 8px ${v.color}` }}/>
      {v.label}
    </span>
  );
}

// ---- Image placeholder (subtle stripes + monospace label) ----
function ImagePlaceholder({ width, height, label = 'product shot', dark = true }) {
  return (
    <div style={{
      width, height,
      background: dark
        ? 'repeating-linear-gradient(135deg, #1C1C1C 0 8px, #141414 8px 16px)'
        : 'repeating-linear-gradient(135deg, #e8e6e0 0 8px, #f0eee9 8px 16px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'JetBrains Mono, ui-monospace, monospace',
      fontSize: 11, color: '#666', letterSpacing: '0.04em',
      borderRadius: 4,
    }}>{label}</div>
  );
}

// ---- Tabular formatter ----
function fmt(n) { return n.toLocaleString('ru-RU'); }

// ---- Generate a price series ----
function genSeries(n, start, end, jitter = 0.04) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    const base = start + (end - start) * t;
    const noise = (Math.sin(i * 1.7) + Math.sin(i * 0.43) * 0.6) * (start * jitter);
    out.push(Math.round(base + noise));
  }
  return out;
}

Object.assign(window, {
  Scout, Sparkline, PriceChart, MarketplaceTag, VerdictBadge, ImagePlaceholder, fmt, genSeries
});
