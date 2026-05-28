// Dashboard — product grid with mini-charts. Empty state with Scout.
const { useState: useStateD } = React;

const dashProducts = [
  { id: 1, name: 'Sony WH-1000XM5 wireless headphones', cat: 'Электроника · Аудио', source: 'wb', price: 32490, prev: 38990, verdict: 'buy', series: genSeries(20, 39000, 32500), stock: true, lastSeen: '2 мин назад' },
  { id: 2, name: 'iPhone 15 Pro 256GB Natural Titanium', cat: 'Электроника · Смартфоны', source: 'ozon', price: 109990, prev: 104990, verdict: 'wait', series: genSeries(20, 104000, 110000), stock: true, lastSeen: '14 мин назад' },
  { id: 3, name: 'LG OLED C3 55" 4K UHD Smart TV', cat: 'Электроника · ТВ', source: 'dns', price: 124900, prev: 129900, verdict: 'monitor', series: genSeries(20, 130500, 124800), stock: true, lastSeen: '1 ч назад' },
  { id: 4, name: 'Dyson V15 Detect Absolute', cat: 'Бытовая техника', source: 'citilink', price: 64990, prev: 71990, verdict: 'buy', series: genSeries(20, 72000, 65000), stock: true, lastSeen: '34 мин назад' },
  { id: 5, name: 'MacBook Air M3 13" 16/512', cat: 'Электроника · Ноутбуки', source: 'ozon', price: 149900, prev: 144900, verdict: 'wait', series: genSeries(20, 144000, 150000), stock: false, lastSeen: '3 ч назад' },
  { id: 6, name: 'Bosch SMV4HVX31E посудомойка', cat: 'Бытовая техника', source: 'wb', price: 58740, prev: 61200, verdict: 'monitor', series: genSeries(20, 61500, 58800), stock: true, lastSeen: '8 мин назад' },
  { id: 7, name: 'GeForce RTX 4070 Ti Super Gigabyte', cat: 'Компьютеры · Видеокарты', source: 'regard', price: 89990, prev: 94990, verdict: 'buy', series: genSeries(20, 95000, 90000), stock: true, lastSeen: '12 мин назад' },
  { id: 8, name: 'PlayStation 5 Slim Disc Edition', cat: 'Игры · Консоли', source: 'dns', price: 54990, prev: 52990, verdict: 'wait', series: genSeries(20, 52500, 55200), stock: true, lastSeen: '21 мин назад' },
  { id: 9, name: 'Samsung Galaxy Tab S9 128GB', cat: 'Электроника · Планшеты', source: 'ozon', price: 72400, prev: 78900, verdict: 'buy', series: genSeries(20, 79000, 72400), stock: true, lastSeen: '5 мин назад', anomaly: true },
];

function Dashboard({ empty = false, withModal = false, onOpenProduct }) {
  const [view, setView] = useStateD('grid'); // grid | list
  const [filter, setFilter] = useStateD('all');

  const filtered = filter === 'all' ? dashProducts : dashProducts.filter(p => p.verdict === filter);

  return (
    <div data-screen-label="Dashboard" style={{ width: '100%', minHeight: '100%', background: '#0A0A0A', color: '#F5F5F5', fontFamily: 'Inter, system-ui, sans-serif', position: 'relative' }}>
      <DashNav />
      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: 'calc(100% - 64px)' }}>
        <DashSidebar />
        <main style={{ padding: '32px 40px 80px', borderLeft: '1px solid #1C1C1C', minHeight: 800 }}>
          {empty ? <EmptyDash /> : <>
            <DashHeader filter={filter} setFilter={setFilter} view={view} setView={setView} />
            <DashStats />
            {view === 'grid'
              ? <ProductGrid products={filtered} onOpen={onOpenProduct}/>
              : <ProductList products={filtered} onOpen={onOpenProduct}/>}
          </>}
        </main>
      </div>
      {withModal && <AddProductModal />}
    </div>
  );
}

function DashNav() {
  return (
    <header style={{
      height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 24px', borderBottom: '1px solid #1C1C1C', background: '#0A0A0A',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 22, height: 22, borderRadius: 5, background: '#0A0A0A', border: '1.5px solid #A855F7', position: 'relative' }}>
            <span style={{ position: 'absolute', top: -3, left: '50%', transform: 'translateX(-50%)', width: 6, height: 6, borderRadius: '50%', background: '#A855F7' }}/>
          </div>
          <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 17, fontWeight: 700, letterSpacing: '-0.02em' }}>scout</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#141414', border: '1px solid #1C1C1C', borderRadius: 4, padding: '8px 12px', width: 360 }}>
          <span style={{ color: '#666', fontSize: 14 }}>⌕</span>
          <input placeholder="Поиск по товарам, маркетплейсам…" style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none',
            color: '#F5F5F5', fontSize: 13, fontFamily: 'Inter',
          }}/>
          <span style={{ fontSize: 10, color: '#666', padding: '2px 6px', border: '1px solid #2E2E2E', borderRadius: 3, fontFamily: 'JetBrains Mono, monospace' }}>⌘K</span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <button style={{
          height: 36, padding: '0 16px', background: '#A855F7', color: '#0A0A0A', border: 'none',
          fontFamily: 'Inter', fontSize: 13, fontWeight: 600, borderRadius: 4, cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>+ добавить товар</button>
        <button style={iconBtn} title="Уведомления">
          <span style={{ position: 'relative' }}>◌
            <span style={{ position: 'absolute', top: -2, right: -4, width: 6, height: 6, borderRadius: '50%', background: '#EF4444' }}/>
          </span>
        </button>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#1C1C1C', border: '1px solid #2E2E2E', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: '#A3A3A3', fontWeight: 600 }}>A</div>
      </div>
    </header>
  );
}
const iconBtn = {
  width: 36, height: 36, borderRadius: 4, background: 'transparent', border: '1px solid #1C1C1C',
  color: '#A3A3A3', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
};

function DashSidebar() {
  const items = [
    { i: '◆', l: 'Все товары', c: 24, active: true },
    { i: '★', l: 'Wishlist', c: 8 },
    { i: '◇', l: 'Аномалии', c: 3, warn: true },
    { i: '✓', l: 'Можно купить', c: 5, good: true },
    { i: '□', l: 'Архив', c: 12 },
  ];
  const sources = [
    { i: '·', l: 'Wildberries', c: 9 },
    { i: '·', l: 'Ozon', c: 7 },
    { i: '·', l: 'DNS', c: 5 },
    { i: '·', l: 'Citilink', c: 3 },
    { i: '·', l: 'Regard', c: 1 },
  ];
  return (
    <aside style={{ padding: '24px 16px', background: '#0A0A0A' }}>
      <div style={sidebarLabel}>shelf</div>
      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {items.map((x, i) => <SideRow key={i} {...x}/>)}
      </div>
      <div style={{ ...sidebarLabel, marginTop: 28 }}>marketplaces</div>
      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {sources.map((x, i) => <SideRow key={i} {...x}/>)}
      </div>
      <div style={{ marginTop: 40, padding: 16, background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>free plan</span>
          <span style={{ fontSize: 11, color: '#A855F7' }}>upgrade →</span>
        </div>
        <div style={{ marginTop: 12, fontSize: 13, color: '#F5F5F5' }}>24 / 10 товаров</div>
        <div style={{ marginTop: 8, height: 4, background: '#1C1C1C', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: '100%', background: '#EF4444' }}/>
        </div>
        <div style={{ marginTop: 8, fontSize: 11, color: '#A3A3A3' }}>лимит превышен. некоторые товары не парсятся.</div>
      </div>
    </aside>
  );
}
const sidebarLabel = {
  padding: '0 12px', fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em',
};
function SideRow({ i, l, c, active, warn, good }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px', borderRadius: 4,
      background: active ? '#1C1C1C' : 'transparent',
      color: active ? '#F5F5F5' : '#A3A3A3',
      fontSize: 13, cursor: 'pointer',
    }}>
      <span style={{ color: active ? '#A855F7' : (warn ? '#F59E0B' : good ? '#10B981' : '#666'), width: 14, textAlign: 'center' }}>{i}</span>
      <span style={{ flex: 1 }}>{l}</span>
      <span style={{ fontSize: 11, color: '#666', fontVariantNumeric: 'tabular-nums' }}>{c}</span>
    </div>
  );
}

function DashHeader({ filter, setFilter, view, setView }) {
  const tabs = [
    { k: 'all', l: 'Все', n: dashProducts.length },
    { k: 'buy', l: 'Можно купить', n: dashProducts.filter(p=>p.verdict==='buy').length, c: '#10B981' },
    { k: 'wait', l: 'Подождать', n: dashProducts.filter(p=>p.verdict==='wait').length, c: '#EF4444' },
    { k: 'monitor', l: 'Мониторим', n: dashProducts.filter(p=>p.verdict==='monitor').length, c: '#F59E0B' },
  ];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 32 }}>
      <div>
        <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>пятница · 27 мая, 14:23</div>
        <h1 style={{ marginTop: 8, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 40, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase', margin: 0 }}>добрый день, anna.</h1>
        <p style={{ marginTop: 8, fontSize: 14, color: '#A3A3A3' }}>5 товаров готовы к покупке. 3 показали аномалии за последние 24 часа.</p>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', gap: 2, background: '#141414', padding: 2, borderRadius: 4, border: '1px solid #1C1C1C' }}>
          {tabs.map(t => (
            <button key={t.k} onClick={() => setFilter(t.k)} style={{
              padding: '8px 12px', background: filter === t.k ? '#1C1C1C' : 'transparent',
              color: filter === t.k ? '#F5F5F5' : '#A3A3A3', border: 'none', cursor: 'pointer',
              borderRadius: 3, fontSize: 12, fontWeight: 500, display: 'flex', gap: 6, alignItems: 'center',
              fontFamily: 'Inter',
            }}>
              {t.c && <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.c }}/>}
              {t.l}
              <span style={{ color: '#666', fontVariantNumeric: 'tabular-nums' }}>{t.n}</span>
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 2, background: '#141414', padding: 2, borderRadius: 4, border: '1px solid #1C1C1C' }}>
          <button onClick={()=>setView('grid')} style={{ ...viewBtn, background: view==='grid' ? '#1C1C1C' : 'transparent' }}>▦</button>
          <button onClick={()=>setView('list')} style={{ ...viewBtn, background: view==='list' ? '#1C1C1C' : 'transparent' }}>≡</button>
        </div>
      </div>
    </div>
  );
}
const viewBtn = { width: 30, height: 30, border: 'none', color: '#A3A3A3', cursor: 'pointer', borderRadius: 3, fontSize: 14 };

function DashStats() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
      <StatTile label="Отслеживается" value="24" sub="товаров"/>
      <StatTile label="Средняя экономия" value="23%" sub="за 30 дней" color="#10B981"/>
      <StatTile label="Парсингов / день" value="384" sub="≈ 1 раз в 4 часа"/>
      <StatTile label="Аномалий найдено" value="3" sub="за 7 дней" color="#F59E0B"/>
    </div>
  );
}
function StatTile({ label, value, sub, color = '#F5F5F5' }) {
  return (
    <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6, padding: 20 }}>
      <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</div>
      <div style={{ marginTop: 12, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em', color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      <div style={{ marginTop: 4, fontSize: 12, color: '#A3A3A3' }}>{sub}</div>
    </div>
  );
}

function ProductGrid({ products, onOpen }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
      {products.map(p => <ProductCard key={p.id} p={p} onClick={() => onOpen && onOpen(p)}/>)}
    </div>
  );
}
function ProductCard({ p, onClick }) {
  const trend = ((p.price - p.prev) / p.prev) * 100;
  const up = trend > 0;
  const color = up ? '#EF4444' : '#10B981';
  return (
    <div onClick={onClick} style={{
      background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6, padding: 20,
      cursor: 'pointer', position: 'relative', transition: 'border-color .2s, transform .2s',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = '#2E2E2E'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = '#1C1C1C'; e.currentTarget.style.transform = 'translateY(0)'; }}>
      {p.anomaly && (
        <div style={{ position: 'absolute', top: 12, right: 12, padding: '3px 8px', fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#F59E0B', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 3 }}>аномалия</div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <MarketplaceTag source={p.source}/>
        {!p.stock && <span style={{ fontSize: 11, color: '#666' }}>· нет в наличии</span>}
      </div>
      <ImagePlaceholder width="100%" height={140} label="product shot"/>
      <div style={{ marginTop: 4, fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{p.cat}</div>
      <div style={{ marginTop: 6, fontSize: 15, fontWeight: 600, lineHeight: 1.3, color: '#F5F5F5', height: 40, overflow: 'hidden' }}>{p.name}</div>
      <div style={{ marginTop: 14, display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'Inter', fontSize: 26, fontWeight: 700, color: '#F5F5F5', letterSpacing: '-0.01em', fontVariantNumeric: 'tabular-nums' }}>{fmt(p.price)} ₽</span>
        <span style={{ fontSize: 13, color: '#666', textDecoration: 'line-through', fontVariantNumeric: 'tabular-nums' }}>{fmt(p.prev)} ₽</span>
      </div>
      <div style={{ marginTop: 4, fontSize: 12, color, fontWeight: 600 }}>
        {up ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}% · {fmt(Math.abs(p.price - p.prev))} ₽
      </div>
      <div style={{ marginTop: 12 }}>
        <Sparkline data={p.series} width={320} height={48} color={color}/>
      </div>
      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <VerdictBadge verdict={p.verdict}/>
        <span style={{ fontSize: 11, color: '#666' }}>{p.lastSeen}</span>
      </div>
    </div>
  );
}
function ProductList({ products, onOpen }) {
  return (
    <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6, overflow: 'hidden' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr 120px 130px 100px 130px 80px 60px', gap: 16, padding: '12px 16px', borderBottom: '1px solid #1C1C1C', fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        <span></span>
        <span>товар</span>
        <span>маркетплейс</span>
        <span style={{ textAlign: 'right' }}>цена</span>
        <span style={{ textAlign: 'right' }}>тренд</span>
        <span>график</span>
        <span>вердикт</span>
        <span></span>
      </div>
      {products.map((p, i) => {
        const trend = ((p.price - p.prev) / p.prev) * 100;
        const up = trend > 0;
        return (
          <div key={p.id} onClick={() => onOpen && onOpen(p)} style={{ display: 'grid', gridTemplateColumns: '40px 1fr 120px 130px 100px 130px 80px 60px', gap: 16, padding: '14px 16px', borderTop: i === 0 ? 'none' : '1px solid #1C1C1C', alignItems: 'center', cursor: 'pointer' }}>
            <ImagePlaceholder width={28} height={28} label=""/>
            <span style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</span>
            <MarketplaceTag source={p.source}/>
            <span style={{ fontSize: 14, fontWeight: 600, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{fmt(p.price)} ₽</span>
            <span style={{ fontSize: 12, color: up ? '#EF4444' : '#10B981', textAlign: 'right', fontWeight: 600 }}>{up ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%</span>
            <Sparkline data={p.series} width={120} height={28} color={up ? '#EF4444' : '#10B981'}/>
            <VerdictBadge verdict={p.verdict}/>
            <span style={{ color: '#666', textAlign: 'right' }}>···</span>
          </div>
        );
      })}
    </div>
  );
}

function EmptyDash() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '120px 24px', textAlign: 'center', minHeight: 700 }}>
      <Scout size={160} state="sleeping"/>
      <div style={{ marginTop: 32, fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>nothing tracked yet</div>
      <h2 style={{ marginTop: 16, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 56, fontWeight: 700, letterSpacing: '-0.03em', textTransform: 'lowercase', margin: 0 }}>add your first product.</h2>
      <p style={{ marginTop: 16, fontSize: 16, color: '#A3A3A3', maxWidth: 460, lineHeight: 1.5 }}>
        paste a link from wildberries, ozon, dns, citilink or regard. scout will start watching within 60 seconds.
      </p>
      <button style={{
        marginTop: 40, height: 48, padding: '0 28px', background: '#A855F7', color: '#0A0A0A', border: 'none',
        borderRadius: 4, cursor: 'pointer', fontSize: 14, fontWeight: 600, fontFamily: 'Inter',
      }}>+ добавить товар</button>
      <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>либо нажмите ⌘N в любом месте</div>

      <div style={{ marginTop: 80, display: 'flex', gap: 12 }}>
        <ExampleChip src="wb" label="wildberries.ru/catalog/…"/>
        <ExampleChip src="ozon" label="ozon.ru/product/…"/>
        <ExampleChip src="dns" label="dns-shop.ru/product/…"/>
      </div>
    </div>
  );
}
function ExampleChip({ src, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 4, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#666' }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#A855F7' }}/>
      {label}
    </div>
  );
}

// ============ ADD PRODUCT MODAL ============
function AddProductModal({ onClose }) {
  const [url, setUrl] = useStateD('https://www.wildberries.ru/catalog/164842543/detail.aspx');
  const [stage, setStage] = useStateD('preview'); // empty | loading | preview | error
  return (
    <div style={{
      position: 'absolute', inset: 0, background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }}>
      <div style={{
        width: 600, background: '#141414', border: '1px solid #2E2E2E', borderRadius: 8,
        padding: 32, boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>new</div>
            <h2 style={{ marginTop: 6, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase', margin: 0 }}>add product</h2>
          </div>
          <button onClick={onClose} style={{ ...iconBtn, width: 32, height: 32 }}>✕</button>
        </div>

        <div style={{ marginTop: 28 }}>
          <label style={{ fontSize: 11, color: '#A3A3A3', textTransform: 'uppercase', letterSpacing: '0.1em' }}>ссылка на товар</label>
          <div style={{ marginTop: 8, display: 'flex', gap: 0, background: '#0A0A0A', border: '1px solid #2E2E2E', borderRadius: 4, padding: 4 }}>
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="paste a link from wildberries, ozon, dns…"
              style={{
                flex: 1, background: 'transparent', border: 'none', outline: 'none',
                padding: '12px 12px', fontSize: 14, color: '#F5F5F5', fontFamily: 'JetBrains Mono, monospace',
              }}
            />
            <button onClick={()=>setStage('preview')} style={{
              padding: '0 20px', background: '#A855F7', color: '#0A0A0A', border: 'none',
              fontSize: 12, fontWeight: 600, borderRadius: 3, cursor: 'pointer', fontFamily: 'Inter',
            }}>check</button>
          </div>
          <div style={{ marginTop: 8, display: 'flex', gap: 12, alignItems: 'center', fontSize: 11, color: '#666' }}>
            <span>supported:</span>
            {['wildberries','ozon','dns','citilink','regard'].map((s, i) => (
              <span key={i} style={{ color: '#A3A3A3' }}>{s}{i<4?'  ·':''}</span>
            ))}
          </div>
        </div>

        {/* live preview */}
        {stage === 'preview' && (
          <div style={{ marginTop: 24, padding: 20, background: '#0A0A0A', border: '1px solid rgba(168,85,247,0.3)', borderRadius: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#10B981', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981' }}/>
              parsed successfully · 1.2s
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 16 }}>
              <ImagePlaceholder width={88} height={88} label="img"/>
              <div style={{ flex: 1 }}>
                <MarketplaceTag source="wb"/>
                <div style={{ marginTop: 8, fontSize: 15, fontWeight: 600, color: '#F5F5F5' }}>Bosch SMV4HVX31E встраиваемая посудомоечная машина</div>
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'baseline', gap: 10 }}>
                  <span style={{ fontFamily: 'Inter', fontSize: 22, fontWeight: 700, color: '#A855F7', fontVariantNumeric: 'tabular-nums' }}>58 740 ₽</span>
                  <span style={{ fontSize: 12, color: '#666', textDecoration: 'line-through' }}>61 200 ₽</span>
                </div>
              </div>
            </div>
            <div style={{ marginTop: 16, fontSize: 12, color: '#A3A3A3' }}>
              scout will start watching this product. first datapoint already saved. you'll see history within 4 hours.
            </div>
          </div>
        )}

        {/* notification rules */}
        <div style={{ marginTop: 24 }}>
          <label style={{ fontSize: 11, color: '#A3A3A3', textTransform: 'uppercase', letterSpacing: '0.1em' }}>уведомить меня когда</label>
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <CheckRow label="цена упадёт ниже" right={<PriceInput v="55 000"/>} checked />
            <CheckRow label="обнаружена аномалия (фейковая скидка)" checked />
            <CheckRow label="появилось в наличии"/>
          </div>
        </div>

        <div style={{ marginTop: 32, display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            height: 40, padding: '0 20px', background: 'transparent', color: '#A3A3A3',
            border: '1px solid #2E2E2E', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 500, fontFamily: 'Inter',
          }}>cancel</button>
          <button style={{
            height: 40, padding: '0 24px', background: '#A855F7', color: '#0A0A0A',
            border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: 'Inter',
          }}>add product</button>
        </div>
      </div>
    </div>
  );
}
function CheckRow({ label, right, checked }) {
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
function PriceInput({ v }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#141414', border: '1px solid #2E2E2E', borderRadius: 3, padding: '4px 8px', minWidth: 100 }}>
      <input defaultValue={v} style={{ width: 64, background: 'transparent', border: 'none', outline: 'none', color: '#F5F5F5', fontSize: 12, fontFamily: 'Inter', fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}/>
      <span style={{ fontSize: 12, color: '#666' }}>₽</span>
    </div>
  );
}

Object.assign(window, { Dashboard, AddProductModal });
