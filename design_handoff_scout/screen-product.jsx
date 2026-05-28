// Product Detail — chart + AI verdict + marketplace comparison
const { useState: useStateP } = React;

function ProductDetail({ onBack }) {
  const [range, setRange] = useStateP('90d');
  const [hoverIdx, setHoverIdx] = useStateP(null);

  const baseData = genSeries(90, 38990, 32490, 0.05);
  // build a sensible label set
  const months = ['фев', 'мар', 'апр', 'май'];
  const data = baseData.map((p, i) => ({
    price: p,
    label: `${(i % 30) + 1} ${months[Math.min(3, Math.floor(i / 22))]}`,
  }));
  const current = data[data.length - 1].price;
  const prev30 = data[data.length - 30].price;
  const prev7 = data[data.length - 7].price;
  const min90 = Math.min(...data.map(d=>d.price));
  const max90 = Math.max(...data.map(d=>d.price));

  return (
    <div data-screen-label="Product detail" style={{ width: '100%', minHeight: '100%', background: '#0A0A0A', color: '#F5F5F5', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <DashNav />
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: '32px 40px 80px' }}>
        {/* breadcrumb / back */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: '#A3A3A3' }}>
          <a onClick={onBack} style={{ cursor: 'pointer', color: '#A3A3A3', display: 'flex', alignItems: 'center', gap: 6 }}>← все товары</a>
          <span style={{ color: '#2E2E2E' }}>/</span>
          <span>электроника</span>
          <span style={{ color: '#2E2E2E' }}>/</span>
          <span>аудио</span>
          <span style={{ color: '#2E2E2E' }}>/</span>
          <span style={{ color: '#F5F5F5' }}>WH-1000XM5</span>
        </div>

        {/* header */}
        <div style={{ marginTop: 28, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 32 }}>
          <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', flex: 1 }}>
            <ImagePlaceholder width={120} height={120} label="product"/>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <MarketplaceTag source="wb" size="lg"/>
                <span style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em' }}>отслеживается 67 дней</span>
              </div>
              <h1 style={{ marginTop: 14, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 44, fontWeight: 700, letterSpacing: '-0.025em', textTransform: 'lowercase', margin: 0, lineHeight: 1.05 }}>
                sony wh-1000xm5
              </h1>
              <div style={{ marginTop: 8, fontSize: 15, color: '#A3A3A3' }}>беспроводные наушники с активным шумоподавлением</div>
              <div style={{ marginTop: 14, display: 'flex', gap: 6, alignItems: 'center' }}>
                <a style={{ fontSize: 12, color: '#A855F7', textDecoration: 'underline', textUnderlineOffset: 4, fontFamily: 'JetBrains Mono, monospace' }}>wildberries.ru/catalog/164842543</a>
                <span style={{ fontSize: 12, color: '#666' }}>· обновлено 2 мин назад</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={btnGhost}>★ wishlist</button>
            <button style={btnGhost}>↗ share</button>
            <button style={{ ...btnGhost, color: '#EF4444', borderColor: 'rgba(239,68,68,0.3)' }}>✕ remove</button>
          </div>
        </div>

        {/* two-col */}
        <div style={{ marginTop: 40, display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 24 }}>
          {/* LEFT — chart */}
          <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 8, padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={cardLabel}>история цен</div>
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 12 }}>
                  <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 48, fontWeight: 700, letterSpacing: '-0.025em', color: '#A855F7', fontVariantNumeric: 'tabular-nums' }}>{fmt(current)} ₽</span>
                  <span style={{ fontSize: 16, color: '#666', textDecoration: 'line-through', fontVariantNumeric: 'tabular-nums' }}>{fmt(38990)} ₽</span>
                  <span style={{ fontSize: 14, color: '#10B981', fontWeight: 600 }}>↓ 16.7%</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 2, background: '#0A0A0A', padding: 2, borderRadius: 4, border: '1px solid #1C1C1C' }}>
                {['7d','30d','90d','1y','all'].map(k => (
                  <button key={k} onClick={() => setRange(k)} style={{
                    padding: '6px 12px', background: range === k ? '#1C1C1C' : 'transparent',
                    color: range === k ? '#F5F5F5' : '#A3A3A3', border: 'none', cursor: 'pointer',
                    borderRadius: 3, fontSize: 12, fontWeight: 500, fontFamily: 'Inter',
                  }}>{k}</button>
                ))}
              </div>
            </div>

            <div style={{ marginTop: 24 }}>
              <PriceChart data={data} hoverIdx={hoverIdx} onHover={setHoverIdx} width={780} height={300}/>
            </div>

            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, paddingTop: 20, borderTop: '1px solid #1C1C1C' }}>
              <MetricMini label="за 7 дней" value={`${(((current-prev7)/prev7)*100).toFixed(1)}%`} color={current<prev7 ? '#10B981':'#EF4444'} arrow={current<prev7?'↓':'↑'}/>
              <MetricMini label="за 30 дней" value={`${(((current-prev30)/prev30)*100).toFixed(1)}%`} color={current<prev30 ? '#10B981':'#EF4444'} arrow={current<prev30?'↓':'↑'}/>
              <MetricMini label="мин · 90 дней" value={`${fmt(min90)} ₽`}/>
              <MetricMini label="макс · 90 дней" value={`${fmt(max90)} ₽`}/>
            </div>
          </div>

          {/* RIGHT — verdict + comparison */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* AI verdict */}
            <div style={{ background: 'linear-gradient(180deg, #141414 0%, #0F0A1A 100%)', border: '1px solid rgba(168,85,247,0.4)', borderRadius: 8, padding: 24, position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: -40, right: -40, width: 160, height: 160, borderRadius: '50%', background: 'radial-gradient(circle, rgba(168,85,247,0.15), transparent 70%)' }}/>
              <div style={{ position: 'relative' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Scout size={36} state="watching"/>
                  <span style={{ fontSize: 11, color: '#A855F7', textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 600 }}>scout verdict</span>
                </div>
                <div style={{ marginTop: 20 }}>
                  <VerdictBadge verdict="buy" size="lg"/>
                </div>
                <h3 style={{ marginTop: 16, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase', margin: 0, lineHeight: 1.1 }}>real drop. buy now.</h3>
                <p style={{ marginTop: 14, fontSize: 14, color: '#A3A3A3', lineHeight: 1.55 }}>
                  lowest price in 90 days. trend has been monotonically down for 14 of the last 21 days — this is not a spike-followed-by-bounceback pattern.
                </p>
                <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid #1C1C1C', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>confidence</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 100, height: 4, background: '#1C1C1C', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: '87%', background: '#A855F7' }}/>
                    </div>
                    <span style={{ fontSize: 13, color: '#F5F5F5', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>87%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Subscriptions */}
            <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 8, padding: 24 }}>
              <div style={cardLabel}>уведомления</div>
              <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <CheckRowD label="цена упадёт ниже" right={<PriceInputD v="30 000"/>} checked />
                <CheckRowD label="обнаружена аномалия" checked />
                <CheckRowD label="появилось в наличии"/>
              </div>
            </div>
          </div>
        </div>

        {/* Marketplace comparison */}
        <div style={{ marginTop: 24, background: '#141414', border: '1px solid #1C1C1C', borderRadius: 8, padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
            <div>
              <div style={cardLabel}>сравнение по маркетплейсам</div>
              <h3 style={{ marginTop: 8, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase', margin: 0 }}>где дешевле прямо сейчас</h3>
            </div>
            <span style={{ fontSize: 12, color: '#666' }}>обновлено 2 мин назад</span>
          </div>
          <div style={{ marginTop: 20, border: '1px solid #1C1C1C', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '160px 160px 1fr 140px 100px 120px', gap: 16, padding: '12px 20px', background: '#0A0A0A', fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              <span>маркетплейс</span>
              <span style={{ textAlign: 'right' }}>цена</span>
              <span>история (30д)</span>
              <span style={{ textAlign: 'right' }}>тренд · 7д</span>
              <span style={{ textAlign: 'right' }}>наличие</span>
              <span style={{ textAlign: 'right' }}>верд.</span>
            </div>
            {[
              { src: 'wb', price: 32490, trend: -16.7, sparkColor: '#10B981', series: genSeries(20, 38000, 32500), stock: true, verdict: 'buy', best: true },
              { src: 'ozon', price: 34990, trend: -10.2, sparkColor: '#10B981', series: genSeries(20, 38500, 35000), stock: true, verdict: 'buy' },
              { src: 'dns', price: 35900, trend: -8.1, sparkColor: '#10B981', series: genSeries(20, 38900, 36000), stock: true, verdict: 'monitor' },
              { src: 'citilink', price: 37490, trend: -3.4, sparkColor: '#10B981', series: genSeries(20, 38500, 37500), stock: false, verdict: 'monitor' },
              { src: 'regard', price: 39900, trend: +2.3, sparkColor: '#EF4444', series: genSeries(20, 38900, 39900), stock: true, verdict: 'wait' },
            ].map((row, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '160px 160px 1fr 140px 100px 120px', gap: 16, padding: '14px 20px', borderTop: '1px solid #1C1C1C', alignItems: 'center', background: row.best ? 'rgba(168,85,247,0.04)' : 'transparent' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <MarketplaceTag source={row.src}/>
                  {row.best && <span style={{ fontSize: 10, color: '#A855F7', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600 }}>лучшая</span>}
                </div>
                <span style={{ textAlign: 'right', fontFamily: 'Inter', fontSize: 16, fontWeight: 700, color: row.best ? '#A855F7' : '#F5F5F5', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.price)} ₽</span>
                <Sparkline data={row.series} width={220} height={32} color={row.sparkColor}/>
                <span style={{ textAlign: 'right', fontSize: 13, color: row.trend < 0 ? '#10B981' : '#EF4444', fontWeight: 600 }}>{row.trend < 0 ? '↓' : '↑'} {Math.abs(row.trend).toFixed(1)}%</span>
                <span style={{ textAlign: 'right', fontSize: 12, color: row.stock ? '#10B981' : '#666' }}>{row.stock ? '● в наличии' : '○ нет'}</span>
                <div style={{ textAlign: 'right' }}><VerdictBadge verdict={row.verdict}/></div>
              </div>
            ))}
          </div>
        </div>

        {/* Similar products */}
        <div style={{ marginTop: 56 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20 }}>
            <h3 style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase', margin: 0 }}>похожие товары</h3>
            <a style={{ fontSize: 13, color: '#A855F7' }}>смотреть все →</a>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            {[
              { name: 'Sony WH-CH720N', price: 9990, prev: 12490, verdict: 'buy', series: genSeries(15, 12500, 10000), src: 'ozon' },
              { name: 'Bose QuietComfort Ultra', price: 39990, prev: 42990, verdict: 'monitor', series: genSeries(15, 43000, 40000), src: 'wb' },
              { name: 'AirPods Max', price: 54990, prev: 51990, verdict: 'wait', series: genSeries(15, 52000, 55000), src: 'dns' },
              { name: 'Sennheiser Momentum 4', price: 28490, prev: 32990, verdict: 'buy', series: genSeries(15, 33000, 28500), src: 'citilink' },
            ].map((p, i) => (
              <div key={i} style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6, padding: 16 }}>
                <ImagePlaceholder width="100%" height={90} label=""/>
                <MarketplaceTag source={p.src}/>
                <div style={{ marginTop: 8, fontSize: 13, fontWeight: 600, height: 36, overflow: 'hidden' }}>{p.name}</div>
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{fmt(p.price)} ₽</span>
                  <span style={{ fontSize: 11, color: '#666', textDecoration: 'line-through' }}>{fmt(p.prev)} ₽</span>
                </div>
                <div style={{ marginTop: 8 }}><Sparkline data={p.series} width={200} height={24} color={p.price < p.prev ? '#10B981':'#EF4444'}/></div>
                <div style={{ marginTop: 10 }}><VerdictBadge verdict={p.verdict}/></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
const btnGhost = {
  height: 36, padding: '0 14px', background: 'transparent', color: '#A3A3A3',
  border: '1px solid #2E2E2E', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 500, fontFamily: 'Inter',
};
const cardLabel = { fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' };
function MetricMini({ label, value, color = '#F5F5F5', arrow }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
      <div style={{ marginTop: 6, fontSize: 18, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>
        {arrow && <span style={{ marginRight: 4 }}>{arrow}</span>}{value}
      </div>
    </div>
  );
}
function CheckRowD({ label, right, checked }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: '#0A0A0A', border: '1px solid #1C1C1C', borderRadius: 4 }}>
      <div style={{
        width: 16, height: 16, borderRadius: 3, border: '1px solid #2E2E2E',
        background: checked ? '#A855F7' : '#0A0A0A', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>{checked && <span style={{ color: '#0A0A0A', fontSize: 10, fontWeight: 700 }}>✓</span>}</div>
      <span style={{ flex: 1, fontSize: 13, color: '#F5F5F5' }}>{label}</span>
      {right}
    </div>
  );
}
function PriceInputD({ v }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#141414', border: '1px solid #2E2E2E', borderRadius: 3, padding: '4px 8px', minWidth: 100 }}>
      <input defaultValue={v} style={{ width: 64, background: 'transparent', border: 'none', outline: 'none', color: '#F5F5F5', fontSize: 12, fontFamily: 'Inter', fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}/>
      <span style={{ fontSize: 12, color: '#666' }}>₽</span>
    </div>
  );
}

window.ProductDetail = ProductDetail;
