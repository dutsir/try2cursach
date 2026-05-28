// Landing page — 8-section cinematic narrative
const { useState, useEffect, useRef } = React;

function Landing() {
  return (
    <div data-screen-label="Landing" style={{ width: '100%', background: '#0A0A0A', color: '#F5F5F5', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <LandingNav />
      <HeroSection />
      <BeforeAfterSection />
      <HowItWorksSection />
      <DashboardPreviewSection />
      <MascotSection />
      <SocialProofSection />
      <PricingSection />
      <FinalCtaSection />
      <LandingFooter />
    </div>
  );
}

// ============ NAV ============
function LandingNav() {
  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 50,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '20px 48px', background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(12px)',
      borderBottom: '1px solid #1C1C1C',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 22, height: 22, borderRadius: 5, background: '#0A0A0A', border: '1.5px solid #A855F7', position: 'relative' }}>
          <span style={{ position: 'absolute', top: -3, left: '50%', transform: 'translateX(-50%)', width: 6, height: 6, borderRadius: '50%', background: '#A855F7' }}/>
        </div>
        <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>scout</span>
      </div>
      <div style={{ display: 'flex', gap: 36, fontSize: 14, color: '#A3A3A3' }}>
        <a style={navLink}>how it works</a>
        <a style={navLink}>pricing</a>
        <a style={navLink}>changelog</a>
        <a style={navLink}>docs</a>
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <a style={{ ...navLink, fontSize: 14 }}>sign in</a>
        <button style={ctaSm}>start tracking →</button>
      </div>
    </nav>
  );
}
const navLink = { color: '#A3A3A3', cursor: 'pointer', textDecoration: 'none' };
const ctaSm = {
  background: '#A855F7', color: '#0A0A0A', border: 'none',
  fontFamily: 'Inter', fontSize: 13, fontWeight: 600,
  padding: '10px 16px', borderRadius: 4, cursor: 'pointer',
};

// ============ 01 HERO ============
function HeroSection() {
  return (
    <section style={{ position: 'relative', minHeight: '90vh', padding: '120px 48px 80px', display: 'flex', flexDirection: 'column', justifyContent: 'center', overflow: 'hidden' }}>
      <HeroBackground />
      <div style={{ position: 'relative', maxWidth: 1440, margin: '0 auto', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28, color: '#A3A3A3', fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981', boxShadow: '0 0 8px #10B981' }}/>
          watching 12,847 products · 5 marketplaces
        </div>
        <h1 style={{
          fontFamily: 'Cabinet Grotesk, Inter', fontWeight: 700,
          fontSize: 'clamp(56px, 8vw, 112px)', lineHeight: 0.95, letterSpacing: '-0.035em',
          textTransform: 'lowercase', margin: 0, maxWidth: 1100,
        }}>
          stop guessing<br/>the right price.
        </h1>
        <p style={{ marginTop: 36, fontSize: 20, color: '#A3A3A3', maxWidth: 620, lineHeight: 1.5 }}>
          we watch wildberries, ozon, dns and citilink 24/7. one verdict tells you to buy, wait, or monitor — backed by months of price history.
        </p>
        <div style={{ marginTop: 48, display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
          <button style={{
            background: '#A855F7', color: '#0A0A0A', border: 'none',
            fontFamily: 'Inter', fontSize: 15, fontWeight: 600,
            padding: '16px 28px', borderRadius: 4, cursor: 'pointer', height: 48,
          }}>start tracking — free</button>
          <a style={{ color: '#F5F5F5', textDecoration: 'underline', textUnderlineOffset: 6, textDecorationColor: '#666', fontSize: 15 }}>see how it works ↓</a>
        </div>

        <div style={{ marginTop: 100, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 48, paddingTop: 40, borderTop: '1px solid #1C1C1C', maxWidth: 980 }}>
          <Stat n="12,847" l="products tracked" />
          <Stat n="23%" l="avg savings · 30d" color="#10B981"/>
          <Stat n="2.4M" l="price points / day" />
          <Stat n="847" l="anomalies flagged" color="#F59E0B"/>
        </div>
      </div>

      {/* Floating Scout in hero */}
      <div style={{ position: 'absolute', right: 80, top: '50%', transform: 'translateY(-50%)', opacity: 0.95 }}>
        <Scout size={220} state="watching" glow />
      </div>
    </section>
  );
}
function Stat({ n, l, color = '#F5F5F5' }) {
  return (
    <div>
      <div style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 36, fontWeight: 700, letterSpacing: '-0.02em', color, fontVariantNumeric: 'tabular-nums' }}>{n}</div>
      <div style={{ marginTop: 6, fontSize: 12, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{l}</div>
    </div>
  );
}

// abstract animated line backdrop
function HeroBackground() {
  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.35 }} preserveAspectRatio="none" viewBox="0 0 1440 900">
      <defs>
        <linearGradient id="hero-line" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#A855F7" stopOpacity="0"/>
          <stop offset="50%" stopColor="#A855F7" stopOpacity="0.4"/>
          <stop offset="100%" stopColor="#A855F7" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {Array.from({length: 14}).map((_, i) => {
        const y = 60 + i * 60;
        const pts = [];
        for (let x = 0; x <= 1440; x += 30) {
          pts.push(`${x},${(y + Math.sin((x + i*120) * 0.008) * (18 + i*1.5)).toFixed(1)}`);
        }
        return <polyline key={i} points={pts.join(' ')} fill="none" stroke="url(#hero-line)" strokeWidth="1" opacity={0.3 + (i%4)*0.15}/>;
      })}
      {/* dot field */}
      {Array.from({length: 60}).map((_, i) => (
        <circle key={`d${i}`} cx={(i*73) % 1440} cy={((i*131) % 900)} r={1.5} fill="#A855F7" opacity="0.4"/>
      ))}
    </svg>
  );
}

// ============ 02 BEFORE / AFTER ============
function BeforeAfterSection() {
  return (
    <section style={sectionWrap}>
      <SectionLabel n="02" t="the contrast" />
      <h2 style={h2}>from 10 tabs to one verdict.</h2>
      <div style={{ marginTop: 80, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
        {/* BEFORE */}
        <div style={{
          background: '#141414', border: '1px solid #2E2E2E', borderRadius: 8,
          padding: 32, position: 'relative', overflow: 'hidden',
        }}>
          <div style={chipBad}>before · chaos</div>
          <h3 style={h3}>10 tabs. 5 spreadsheets. zero signal.</h3>
          <p style={{ color: '#A3A3A3', fontSize: 15, marginTop: 12, lineHeight: 1.5 }}>
            manual tracking. missed drops. decision fatigue at 11pm.
          </p>
          {/* mock browser chaos */}
          <div style={{ marginTop: 28, background: '#0A0A0A', borderRadius: 6, padding: 12, border: '1px solid #1C1C1C', position: 'relative' }}>
            <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
              {['wildberries', 'ozon', 'dns', 'citilink', 'regard', 'excel — copy', 'amazon', 'pricerunner', '+12'].map((t, i) => (
                <div key={i} style={{
                  flex: '0 0 auto', padding: '4px 8px', background: i === 0 ? '#1C1C1C' : '#141414',
                  border: '1px solid #2E2E2E', borderRadius: 3, fontSize: 10, color: '#A3A3A3',
                  whiteSpace: 'nowrap', maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis',
                }}>{t}</div>
              ))}
            </div>
            <div style={{ height: 160, background: 'repeating-linear-gradient(135deg, #1C1C1C 0 6px, #141414 6px 12px)', borderRadius: 4, position: 'relative', overflow: 'hidden' }}>
              {/* fake scattered prices */}
              {[
                { x: 8, y: 14, p: '45 990 ₽', s: 'wb' },
                { x: 38, y: 26, p: '47 200 ₽', s: 'ozon' },
                { x: 64, y: 50, p: '44 890 ₽', s: 'dns' },
                { x: 12, y: 70, p: '46 500 ₽', s: 'citi' },
                { x: 70, y: 78, p: '?' , s: '404' },
                { x: 42, y: 60, p: '49 990 ₽', s: 'amzn' },
              ].map((d, i) => (
                <div key={i} style={{
                  position: 'absolute', left: `${d.x}%`, top: `${d.y}%`,
                  fontFamily: 'Inter', fontSize: 12, fontWeight: 600, color: '#F5F5F5',
                  background: '#0A0A0A', padding: '4px 8px', border: '1px solid #2E2E2E', borderRadius: 3,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
                }}>{d.s} · {d.p}</div>
              ))}
              <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at 70% 80%, rgba(239,68,68,0.18), transparent 60%)' }}/>
            </div>
          </div>
          <ul style={{ listStyle: 'none', padding: 0, marginTop: 24, color: '#666', fontSize: 13, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <li>— refresh tabs every 2 hours</li>
            <li>— argue with yourself about "is this a real discount?"</li>
            <li>— miss the drop. buy at peak. regret.</li>
          </ul>
        </div>

        {/* AFTER */}
        <div style={{
          background: '#141414', border: '1px solid rgba(16,185,129,0.4)', borderRadius: 8,
          padding: 32, position: 'relative', overflow: 'hidden',
        }}>
          <div style={chipGood}>after · signal</div>
          <h3 style={h3}>one card. one verdict. one click.</h3>
          <p style={{ color: '#A3A3A3', fontSize: 15, marginTop: 12, lineHeight: 1.5 }}>
            we already watched. here's what to do.
          </p>
          {/* mock clean product card */}
          <div style={{ marginTop: 28, background: '#0A0A0A', border: '1px solid #1C1C1C', borderRadius: 6, padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
              <div>
                <div style={{ fontSize: 12, color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em' }}>sony · electronics</div>
                <div style={{ marginTop: 8, fontSize: 16, fontWeight: 600 }}>WH-1000XM5 wireless headphones</div>
              </div>
              <ImagePlaceholder width={64} height={64} label="img"/>
            </div>
            <div style={{ marginTop: 20, display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 40, fontWeight: 700, color: '#A855F7', letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>32 490 ₽</span>
              <span style={{ fontSize: 14, color: '#666', textDecoration: 'line-through', fontVariantNumeric: 'tabular-nums' }}>38 990 ₽</span>
              <span style={{ fontSize: 13, color: '#10B981', fontWeight: 600 }}>↓ 16.7%</span>
            </div>
            <div style={{ marginTop: 16 }}>
              <Sparkline data={[39000, 39200, 38500, 38900, 37200, 36800, 35400, 34900, 33800, 33200, 32800, 32490]} width={400} height={56} color="#10B981" />
            </div>
            <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
              <VerdictBadge verdict="buy" size="lg"/>
              <span style={{ fontSize: 13, color: '#A3A3A3' }}>lowest price in 90 days · real drop, not a spike</span>
            </div>
          </div>
          <ul style={{ listStyle: 'none', padding: 0, marginTop: 24, color: '#A3A3A3', fontSize: 13, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <li style={{ color: '#10B981' }}>+ one source of truth</li>
            <li style={{ color: '#10B981' }}>+ we filter fake discounts before you see them</li>
            <li style={{ color: '#10B981' }}>+ notification only when it matters</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
const chipBad = {
  display: 'inline-block', padding: '4px 8px', fontSize: 11, fontWeight: 600,
  letterSpacing: '0.08em', textTransform: 'uppercase', color: '#EF4444',
  background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 3, marginBottom: 16,
};
const chipGood = { ...chipBad, color: '#10B981', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)' };

// ============ 03 HOW IT WORKS ============
function HowItWorksSection() {
  const steps = [
    { n: '01', t: 'paste a link', d: 'any product from wb, ozon, dns, citilink or regard.' },
    { n: '02', t: 'we watch 24/7', d: 'background workers re-check prices every few hours.' },
    { n: '03', t: 'history grows', d: 'every datapoint stored. 90 days minimum.' },
    { n: '04', t: 'AI reads the trend', d: 'we separate real drops from fake-discount spikes.' },
    { n: '05', t: 'smart alerts', d: 'a ping only when something material changes.' },
    { n: '06', t: 'decide with data', d: 'buy now. wait. monitor. you choose with context.' },
  ];
  return (
    <section style={{ ...sectionWrap, background: '#0A0A0A' }}>
      <SectionLabel n="03" t="the process" />
      <h2 style={h2}>six steps. zero guesswork.</h2>
      <div style={{ marginTop: 80, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, background: '#1C1C1C', border: '1px solid #1C1C1C', borderRadius: 8, overflow: 'hidden' }}>
        {steps.map(s => (
          <div key={s.n} style={{ background: '#0A0A0A', padding: '40px 32px', minHeight: 220 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
              <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 48, fontWeight: 700, color: '#262626', letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums' }}>{s.n}</span>
              <span style={{ flex: 1, height: 1, background: '#1C1C1C', position: 'relative', top: -10 }}/>
              <StepIcon n={s.n}/>
            </div>
            <h3 style={{ ...h3, marginTop: 28, fontSize: 24 }}>{s.t}</h3>
            <p style={{ marginTop: 12, color: '#A3A3A3', fontSize: 14, lineHeight: 1.6, maxWidth: 320 }}>{s.d}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
function StepIcon({ n }) {
  // tiny geometric icons (squares/circles/diamonds only)
  const stroke = '#A855F7';
  if (n === '01') return <svg width="28" height="28" viewBox="0 0 28 28"><rect x="3" y="9" width="22" height="10" rx="2" fill="none" stroke={stroke} strokeWidth="1.5"/><line x1="7" y1="14" x2="17" y2="14" stroke={stroke} strokeWidth="1.5" strokeLinecap="round"/></svg>;
  if (n === '02') return <svg width="28" height="28" viewBox="0 0 28 28"><circle cx="14" cy="14" r="9" fill="none" stroke={stroke} strokeWidth="1.5"/><line x1="14" y1="14" x2="14" y2="7" stroke={stroke} strokeWidth="1.5" strokeLinecap="round"/><line x1="14" y1="14" x2="19" y2="16" stroke={stroke} strokeWidth="1.5" strokeLinecap="round"/></svg>;
  if (n === '03') return <svg width="28" height="28" viewBox="0 0 28 28"><polyline points="3,20 9,15 14,17 19,10 25,6" fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>;
  if (n === '04') return <svg width="28" height="28" viewBox="0 0 28 28"><rect x="7" y="7" width="14" height="14" rx="3" fill="none" stroke={stroke} strokeWidth="1.5"/><circle cx="14" cy="14" r="3" fill={stroke}/></svg>;
  if (n === '05') return <svg width="28" height="28" viewBox="0 0 28 28"><path d="M 7 18 L 14 4 L 21 18 Z" fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round"/><circle cx="14" cy="22" r="1.5" fill={stroke}/></svg>;
  return <svg width="28" height="28" viewBox="0 0 28 28"><polyline points="5,14 12,21 23,7" fill="none" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

// ============ 04 DASHBOARD PREVIEW ============
function DashboardPreviewSection() {
  return (
    <section style={{ ...sectionWrap, background: '#0A0A0A' }}>
      <SectionLabel n="04" t="live preview" />
      <h2 style={h2}>your shelf. always watched.</h2>
      <p style={{ ...sub, marginTop: 24 }}>this is the actual dashboard. interactive. real data shape from the API.</p>
      <div style={{ marginTop: 72, background: '#141414', border: '1px solid #2E2E2E', borderRadius: 10, padding: 16, boxShadow: '0 40px 100px rgba(0,0,0,0.5), 0 0 0 1px rgba(168,85,247,0.08)' }}>
        {/* fake browser chrome */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 4px', borderBottom: '1px solid #1C1C1C', marginBottom: 16 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#262626' }}/>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#262626' }}/>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#262626' }}/>
          <span style={{ marginLeft: 16, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#666' }}>scout.app/dashboard</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24, minHeight: 480 }}>
          {/* sidebar */}
          <div style={{ padding: '16px 8px', display: 'flex', flexDirection: 'column', gap: 4 }}>
            <SidebarItem icon="◆" label="Все товары" count="24" active />
            <SidebarItem icon="○" label="Wishlist" count="8" />
            <SidebarItem icon="◇" label="Аномалии" count="3" warn />
            <SidebarItem icon="□" label="Архив" count="12" />
            <div style={{ marginTop: 16, padding: '8px 12px', fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>marketplaces</div>
            <SidebarItem icon="·" label="Wildberries" count="9" />
            <SidebarItem icon="·" label="Ozon" count="7" />
            <SidebarItem icon="·" label="DNS" count="5" />
            <SidebarItem icon="·" label="Citilink" count="3" />
          </div>
          {/* product grid mini */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0 20px' }}>
              <div>
                <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>shelf · 24 active</div>
                <div style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', marginTop: 4 }}>good morning, anna.</div>
              </div>
              <button style={{ ...ctaSm, height: 36 }}>+ add product</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {previewProducts.map((p, i) => <MiniProductCard key={i} {...p}/>)}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
const previewProducts = [
  { name: 'Sony WH-1000XM5', source: 'wb', price: 32490, prev: 38990, verdict: 'buy', series: [39000,38500,38000,37200,36000,34900,33500,32490] },
  { name: 'iPhone 15 Pro 256GB', source: 'ozon', price: 109990, prev: 104990, verdict: 'wait', series: [104990,105000,106500,107200,108000,108500,109000,109990] },
  { name: 'LG OLED C3 55"', source: 'dns', price: 124900, prev: 129900, verdict: 'monitor', series: [130000,129500,128000,128200,127500,126800,125900,124900] },
];
function MiniProductCard({ name, source, price, prev, verdict, series }) {
  const up = price > prev;
  return (
    <div style={{ background: '#0A0A0A', border: '1px solid #1C1C1C', borderRadius: 6, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <MarketplaceTag source={source}/>
        <span style={{ fontSize: 11, color: '#666' }}>···</span>
      </div>
      <ImagePlaceholder width="100%" height={70} label="" />
      <div style={{ marginTop: 12, fontSize: 13, fontWeight: 600, lineHeight: 1.3, color: '#F5F5F5', height: 34, overflow: 'hidden' }}>{name}</div>
      <div style={{ marginTop: 10, display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'Inter', fontSize: 18, fontWeight: 700, color: '#F5F5F5', fontVariantNumeric: 'tabular-nums' }}>{fmt(price)} ₽</span>
        <span style={{ fontSize: 11, color: up ? '#EF4444' : '#10B981', fontWeight: 600 }}>{up ? '↑' : '↓'} {Math.abs(((price - prev)/prev)*100).toFixed(1)}%</span>
      </div>
      <div style={{ marginTop: 8 }}>
        <Sparkline data={series} width={170} height={28} color={up ? '#EF4444' : '#10B981'} />
      </div>
      <div style={{ marginTop: 10 }}>
        <VerdictBadge verdict={verdict}/>
      </div>
    </div>
  );
}
function SidebarItem({ icon, label, count, active, warn }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px', borderRadius: 4,
      background: active ? '#1C1C1C' : 'transparent',
      color: active ? '#F5F5F5' : '#A3A3A3',
      fontSize: 13, cursor: 'pointer',
    }}>
      <span style={{ color: active ? '#A855F7' : (warn ? '#F59E0B' : '#666'), width: 12 }}>{icon}</span>
      <span style={{ flex: 1 }}>{label}</span>
      <span style={{ fontSize: 11, color: '#666', fontVariantNumeric: 'tabular-nums' }}>{count}</span>
    </div>
  );
}

// ============ 05 MASCOT ============
function MascotSection() {
  return (
    <section style={{ ...sectionWrap, background: '#0A0A0A' }}>
      <SectionLabel n="05" t="meet scout" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 80, alignItems: 'center', marginTop: 60 }}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 360, position: 'relative' }}>
          <Scout size={280} state="watching" glow />
          {/* state pills around */}
          <div style={{ position: 'absolute', top: 20, left: '8%' }}><StatePill label="idle" state="idle"/></div>
          <div style={{ position: 'absolute', top: 60, right: '8%' }}><StatePill label="watching" state="watching"/></div>
          <div style={{ position: 'absolute', bottom: 100, left: '4%' }}><StatePill label="alert" state="alert"/></div>
          <div style={{ position: 'absolute', bottom: 40, right: '4%' }}><StatePill label="happy" state="happy"/></div>
        </div>
        <div>
          <h2 style={{ ...h2, fontSize: 'clamp(40px, 5vw, 64px)' }}>this is scout.</h2>
          <p style={{ fontSize: 20, color: '#A3A3A3', marginTop: 28, lineHeight: 1.5, maxWidth: 540 }}>
            "i watch prices 24/7 so you don't have to. i'll only knock when something material changes — not before."
          </p>
          <div style={{ marginTop: 36, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <ScoutTrait label="never sleeps" desc="background workers run every 4 hours"/>
            <ScoutTrait label="never spams" desc="bundled digests by default. real alerts on real signal"/>
            <ScoutTrait label="never lies" desc="we show the raw history. you decide what counts as a deal"/>
          </div>
        </div>
      </div>
    </section>
  );
}
function StatePill({ label, state }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px 8px 8px', background: '#141414', border: '1px solid #2E2E2E', borderRadius: 100 }}>
      <Scout size={32} state={state}/>
      <span style={{ fontSize: 11, color: '#A3A3A3', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</span>
    </div>
  );
}
function ScoutTrait({ label, desc }) {
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', padding: '14px 0', borderTop: '1px solid #1C1C1C' }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#A855F7', marginTop: 8 }}/>
      <div>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#F5F5F5' }}>{label}</div>
        <div style={{ fontSize: 13, color: '#A3A3A3', marginTop: 4 }}>{desc}</div>
      </div>
    </div>
  );
}

// ============ 06 SOCIAL PROOF ============
function SocialProofSection() {
  const quotes = [
    { source: 'wb', name: 'maxim p.', role: 'electronics reseller', quote: 'caught a 4070 ti drop on dns at 3am. scout pinged me, i bought 6 units. paid for the year in one night.' },
    { source: 'ozon', name: 'anna k.', role: 'planning a kitchen renovation', quote: 'i was about to buy a bosch dishwasher on ozon. scout said "wait, this is a spike". it dropped 18% nine days later.' },
    { source: 'dns', name: 'denis r.', role: 'price hunter · 4 years', quote: 'i deleted 14 chrome extensions after onboarding. this is the only tracker that flags fake discounts correctly.' },
    { source: 'citilink', name: 'olga m.', role: 'collector', quote: 'i track 38 lego sets. the verdict column saves me twenty minutes every morning. that\'s the whole pitch.' },
  ];
  return (
    <section style={{ ...sectionWrap, background: '#0A0A0A' }}>
      <SectionLabel n="06" t="receipts"/>
      <h2 style={h2}>real people. real drops.</h2>
      <div style={{ marginTop: 80, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 24 }}>
        {quotes.map((q, i) => (
          <div key={i} style={{ background: '#141414', border: '1px solid #2E2E2E', borderRadius: 8, padding: 32 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <MarketplaceTag source={q.source}/>
              <span style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em' }}>verified user</span>
            </div>
            <p style={{ marginTop: 24, fontSize: 18, lineHeight: 1.5, color: '#F5F5F5' }}>"{q.quote}"</p>
            <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 12, paddingTop: 20, borderTop: '1px solid #1C1C1C' }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#1C1C1C', border: '1px solid #2E2E2E', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#A3A3A3', fontWeight: 600 }}>{q.name[0].toUpperCase()}</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{q.name}</div>
                <div style={{ fontSize: 12, color: '#A3A3A3' }}>{q.role}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ============ 07 PRICING ============
function PricingSection() {
  return (
    <section style={{ ...sectionWrap, background: '#0A0A0A' }}>
      <SectionLabel n="07" t="pricing" />
      <h2 style={h2}>simple math. no traps.</h2>
      <div style={{ marginTop: 80, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
        <PricingCard
          name="free"
          price="0 ₽"
          per="forever"
          diff="up to 10 tracked products"
          features={['10 products', '6-hour check interval', 'price history · 30 days', 'email alerts']}
        />
        <PricingCard
          name="pro"
          price="490 ₽"
          per="per month"
          diff="for serious buyers"
          features={['250 products', '1-hour check interval', 'price history · 1 year', 'AI verdict + anomaly detection', 'telegram alerts', 'wishlist sharing']}
          accent
        />
        <PricingCard
          name="team"
          price="2 490 ₽"
          per="per month"
          diff="for resellers & buyers"
          features={['unlimited products', '15-min check interval', 'price history · forever', 'API access', 'priority parsing queue', '5 seats included']}
        />
      </div>
    </section>
  );
}
function PricingCard({ name, price, per, diff, features, accent }) {
  return (
    <div style={{
      background: accent ? '#141414' : '#0A0A0A',
      border: accent ? '1px solid #A855F7' : '1px solid #1C1C1C',
      borderRadius: 8, padding: 32, position: 'relative',
    }}>
      {accent && (
        <div style={{ position: 'absolute', top: -10, left: 24, padding: '4px 10px', fontSize: 10, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#0A0A0A', background: '#A855F7', borderRadius: 3 }}>most popular</div>
      )}
      <div style={{ fontSize: 12, color: '#A3A3A3', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{name}</div>
      <div style={{ marginTop: 16, display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 56, fontWeight: 700, letterSpacing: '-0.03em', color: '#F5F5F5', fontVariantNumeric: 'tabular-nums' }}>{price}</span>
        <span style={{ fontSize: 13, color: '#666' }}>{per}</span>
      </div>
      <div style={{ marginTop: 12, fontSize: 14, color: accent ? '#A855F7' : '#A3A3A3' }}>{diff}</div>
      <button style={{
        marginTop: 24, width: '100%', height: 44, borderRadius: 4, border: 'none', cursor: 'pointer',
        background: accent ? '#A855F7' : '#1C1C1C', color: accent ? '#0A0A0A' : '#F5F5F5',
        fontSize: 14, fontWeight: 600, fontFamily: 'Inter',
      }}>{accent ? 'start free trial →' : 'choose ' + name}</button>
      <ul style={{ listStyle: 'none', padding: 0, margin: '32px 0 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {features.map((f, i) => (
          <li key={i} style={{ display: 'flex', gap: 12, fontSize: 14, color: '#A3A3A3' }}>
            <span style={{ color: accent ? '#A855F7' : '#666' }}>→</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============ 08 FINAL CTA ============
function FinalCtaSection() {
  return (
    <section style={{ padding: '200px 48px', textAlign: 'center', position: 'relative', borderTop: '1px solid #1C1C1C' }}>
      <div style={{ position: 'absolute', top: 80, left: '50%', transform: 'translateX(-50%)', opacity: 0.4 }}>
        <Scout size={120} state="idle" />
      </div>
      <div style={{ position: 'relative', maxWidth: 1100, margin: '0 auto', paddingTop: 80 }}>
        <h2 style={{
          fontFamily: 'Cabinet Grotesk, Inter', fontWeight: 700,
          fontSize: 'clamp(56px, 9vw, 120px)', lineHeight: 0.95, letterSpacing: '-0.035em',
          textTransform: 'lowercase', margin: 0,
        }}>
          stop refreshing.<br/>start tracking.
        </h2>
        <button style={{
          marginTop: 64, background: '#A855F7', color: '#0A0A0A', border: 'none',
          fontFamily: 'Inter', fontSize: 17, fontWeight: 600,
          padding: '20px 36px', borderRadius: 4, cursor: 'pointer', minHeight: 56,
        }}>start free — no card needed →</button>
        <div style={{ marginTop: 24, fontSize: 13, color: '#666' }}>10 products free, forever. upgrade anytime.</div>
      </div>
    </section>
  );
}

// ============ FOOTER ============
function LandingFooter() {
  return (
    <footer style={{ padding: '60px 48px 40px', background: '#0A0A0A', borderTop: '1px solid #1C1C1C' }}>
      <div style={{ maxWidth: 1440, margin: '0 auto', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 48 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 22, height: 22, borderRadius: 5, background: '#0A0A0A', border: '1.5px solid #A855F7', position: 'relative' }}>
              <span style={{ position: 'absolute', top: -3, left: '50%', transform: 'translateX(-50%)', width: 6, height: 6, borderRadius: '50%', background: '#A855F7' }}/>
            </div>
            <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>scout</span>
          </div>
          <p style={{ marginTop: 16, fontSize: 13, color: '#666', maxWidth: 300, lineHeight: 1.6 }}>
            price monitoring across russian marketplaces. open beta. all data points stored as you tracked them.
          </p>
        </div>
        <FooterCol title="product" links={['dashboard','wishlist','pricing','changelog']}/>
        <FooterCol title="company" links={['about','blog','careers','contact']}/>
        <FooterCol title="legal" links={['terms','privacy','imprint','status']}/>
      </div>
      <div style={{ maxWidth: 1440, margin: '60px auto 0', paddingTop: 24, borderTop: '1px solid #1C1C1C', display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#666' }}>
        <span>© 2026 scout. all prices belong to their marketplaces.</span>
        <span>moscow · saint petersburg</span>
      </div>
    </footer>
  );
}
function FooterCol({ title, links }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{title}</div>
      <ul style={{ listStyle: 'none', padding: 0, margin: '20px 0 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {links.map((l, i) => <li key={i} style={{ fontSize: 14, color: '#A3A3A3', cursor: 'pointer' }}>{l}</li>)}
      </ul>
    </div>
  );
}

// ============ shared section primitives ============
const sectionWrap = {
  padding: '140px 48px',
  borderTop: '1px solid #1C1C1C',
  maxWidth: 1440,
  margin: '0 auto',
};
const h2 = {
  fontFamily: 'Cabinet Grotesk, Inter', fontWeight: 700,
  fontSize: 'clamp(40px, 5.5vw, 72px)', lineHeight: 0.95, letterSpacing: '-0.03em',
  textTransform: 'lowercase', margin: 0, maxWidth: 1200,
};
const h3 = {
  fontFamily: 'Inter', fontWeight: 600,
  fontSize: 22, lineHeight: 1.3, letterSpacing: '-0.01em',
  margin: 0,
};
const sub = { fontSize: 18, color: '#A3A3A3', lineHeight: 1.5, maxWidth: 640 };
function SectionLabel({ n, t }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 40, fontSize: 12, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
      <span style={{ color: '#A855F7', fontVariantNumeric: 'tabular-nums' }}>{n}</span>
      <span style={{ flex: 1, height: 1, background: '#1C1C1C', maxWidth: 40 }}/>
      <span>{t}</span>
    </div>
  );
}

window.Landing = Landing;
