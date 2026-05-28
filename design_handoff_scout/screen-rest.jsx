// Wishlist — compact list with drag-handle hints + Settings
const { useState: useStateW } = React;

const wishItems = [
  { id: 1, name: 'GeForce RTX 5090 Founders Edition', cat: 'Видеокарты', source: 'regard', price: 219990, prev: 224990, target: 180000, verdict: 'wait', series: genSeries(15, 224000, 220000), added: '12 мая' },
  { id: 2, name: 'Apple Vision Pro 256GB', cat: 'Электроника', source: 'wb', price: 419000, prev: 449000, target: 350000, verdict: 'monitor', series: genSeries(15, 449000, 419000), added: '8 мая' },
  { id: 3, name: 'Steam Deck OLED 1TB', cat: 'Игры', source: 'dns', price: 79990, prev: 84990, target: 70000, verdict: 'monitor', series: genSeries(15, 85000, 80000), added: '4 мая' },
  { id: 4, name: 'iPad Pro 11" M4 256GB', cat: 'Планшеты', source: 'ozon', price: 99990, prev: 109990, target: 90000, verdict: 'buy', series: genSeries(15, 110000, 100000), added: '2 мая' },
  { id: 5, name: 'Lego Star Wars UCS Millennium Falcon', cat: 'Игрушки', source: 'wb', price: 84990, prev: 89990, target: 70000, verdict: 'monitor', series: genSeries(15, 90000, 85000), added: '28 апр' },
  { id: 6, name: 'Sony α7 IV Body', cat: 'Фото', source: 'citilink', price: 234900, prev: 229900, target: 200000, verdict: 'wait', series: genSeries(15, 230000, 235000), added: '22 апр' },
  { id: 7, name: 'Dell UltraSharp U3225QE', cat: 'Мониторы', source: 'dns', price: 119990, prev: 129990, target: 100000, verdict: 'buy', series: genSeries(15, 130000, 120000), added: '15 апр' },
  { id: 8, name: 'Bose Soundbar 900', cat: 'Аудио', source: 'ozon', price: 89990, prev: 94990, target: 75000, verdict: 'monitor', series: genSeries(15, 95000, 90000), added: '10 апр' },
];

function Wishlist({ empty = false }) {
  const [sort, setSort] = useStateW('added');
  return (
    <div data-screen-label="Wishlist" style={{ width: '100%', minHeight: '100%', background: '#0A0A0A', color: '#F5F5F5', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <DashNav />
      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: 'calc(100% - 64px)' }}>
        <DashSidebar />
        <main style={{ padding: '32px 40px 80px', borderLeft: '1px solid #1C1C1C' }}>
          {empty ? <EmptyWish /> : (
            <>
              <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 32 }}>
                <div>
                  <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>★ wishlist · 8 товаров</div>
                  <h1 style={{ marginTop: 8, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 40, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase', margin: 0 }}>хочу купить.</h1>
                  <p style={{ marginTop: 8, fontSize: 14, color: '#A3A3A3' }}>scout следит за всеми. подождём пока упадут до целевой цены.</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>сортировать</span>
                  <div style={{ display: 'flex', gap: 2, background: '#141414', padding: 2, borderRadius: 4, border: '1px solid #1C1C1C' }}>
                    {[{k:'added',l:'дата'},{k:'price',l:'цена'},{k:'trend',l:'тренд'},{k:'target',l:'до цели'}].map(o => (
                      <button key={o.k} onClick={()=>setSort(o.k)} style={{
                        padding: '8px 12px', background: sort===o.k ? '#1C1C1C':'transparent',
                        color: sort===o.k ? '#F5F5F5':'#A3A3A3', border:'none', cursor:'pointer',
                        borderRadius: 3, fontSize: 12, fontFamily: 'Inter',
                      }}>{o.l}</button>
                    ))}
                  </div>
                </div>
              </div>

              <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6, overflow: 'hidden' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '24px 40px 1fr 110px 130px 130px 120px 110px 90px 32px', gap: 12, padding: '10px 16px', borderBottom: '1px solid #1C1C1C', fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em', alignItems: 'center' }}>
                  <span></span>
                  <span></span>
                  <span>товар</span>
                  <span>маркет</span>
                  <span style={{ textAlign: 'right' }}>цена сейчас</span>
                  <span style={{ textAlign: 'right' }}>целевая</span>
                  <span style={{ textAlign: 'right' }}>до цели</span>
                  <span>тренд · 30д</span>
                  <span>верд.</span>
                  <span></span>
                </div>
                {wishItems.map(it => <WishRow key={it.id} it={it}/>)}
              </div>

              <div style={{ marginTop: 32, padding: 24, background: '#141414', border: '1px dashed #2E2E2E', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <Scout size={48} state="idle"/>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>добавить ещё что-нибудь в wishlist?</div>
                    <div style={{ marginTop: 4, fontSize: 12, color: '#A3A3A3' }}>есть место для ещё 2 товаров на free плане.</div>
                  </div>
                </div>
                <button style={{
                  height: 36, padding: '0 16px', background: '#A855F7', color: '#0A0A0A', border: 'none',
                  borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: 'Inter',
                }}>+ добавить товар</button>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function WishRow({ it }) {
  const trend = ((it.price - it.prev) / it.prev) * 100;
  const up = trend > 0;
  const toGoal = it.price - it.target;
  const goalPct = Math.max(0, Math.min(100, ((it.prev - it.price) / (it.prev - it.target)) * 100));
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '24px 40px 1fr 110px 130px 130px 120px 110px 90px 32px', gap: 12, padding: '14px 16px', borderTop: '1px solid #1C1C1C', alignItems: 'center', transition: 'background .15s' }}
      onMouseEnter={e => e.currentTarget.style.background = '#1C1C1C'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
      <span style={{ color: '#444', cursor: 'grab', textAlign: 'center', fontSize: 14 }}>⋮⋮</span>
      <ImagePlaceholder width={32} height={32} label=""/>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#F5F5F5' }}>{it.name}</div>
        <div style={{ marginTop: 2, fontSize: 11, color: '#666' }}>{it.cat} · добавлено {it.added}</div>
      </div>
      <MarketplaceTag source={it.source}/>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: 14, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{fmt(it.price)} ₽</div>
        <div style={{ fontSize: 11, color: '#666', textDecoration: 'line-through', fontVariantNumeric: 'tabular-nums' }}>{fmt(it.prev)} ₽</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: 13, color: '#A855F7', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{fmt(it.target)} ₽</div>
        <div style={{ marginTop: 6, height: 3, background: '#1C1C1C', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${goalPct}%`, background: '#A855F7' }}/>
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: 13, color: toGoal > 0 ? '#A3A3A3':'#10B981', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
          {toGoal > 0 ? `+${fmt(toGoal)} ₽` : '✓ цель'}
        </div>
        <div style={{ fontSize: 11, color: '#666' }}>{Math.round(goalPct)}% пути</div>
      </div>
      <Sparkline data={it.series} width={100} height={24} color={up ? '#EF4444':'#10B981'}/>
      <VerdictBadge verdict={it.verdict}/>
      <span style={{ color: '#666', textAlign: 'right', cursor: 'pointer' }}>···</span>
    </div>
  );
}

function EmptyWish() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '120px 24px', textAlign: 'center', minHeight: 700 }}>
      <Scout size={140} state="idle"/>
      <div style={{ marginTop: 28, fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>★ wishlist empty</div>
      <h2 style={{ marginTop: 14, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 48, fontWeight: 700, letterSpacing: '-0.03em', textTransform: 'lowercase', margin: 0 }}>no items yet.</h2>
      <p style={{ marginTop: 14, fontSize: 15, color: '#A3A3A3', maxWidth: 420, lineHeight: 1.5 }}>
        save things you want but don't need yet. scout will tell you when the price hits your target.
      </p>
      <button style={{
        marginTop: 36, height: 44, padding: '0 24px', background: '#A855F7', color: '#0A0A0A',
        border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: 'Inter',
      }}>browse my products →</button>
    </div>
  );
}

// ============ SETTINGS ============
function Settings() {
  const [tab, setTab] = useStateW('notifications');
  return (
    <div data-screen-label="Settings" style={{ width: '100%', minHeight: '100%', background: '#0A0A0A', color: '#F5F5F5', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <DashNav />
      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: 'calc(100% - 64px)' }}>
        <DashSidebar />
        <main style={{ padding: '32px 40px 80px', borderLeft: '1px solid #1C1C1C' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 32 }}>
            <div>
              <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>settings</div>
              <h1 style={{ marginTop: 8, fontFamily: 'Cabinet Grotesk, Inter', fontSize: 40, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase', margin: 0 }}>настройки.</h1>
            </div>
            <Scout size={64} state="watching"/>
          </div>

          {/* tabs */}
          <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #1C1C1C', marginBottom: 32 }}>
            {[
              { k: 'notifications', l: 'Notifications' },
              { k: 'subscriptions', l: 'Subscriptions' },
              { k: 'account', l: 'Account' },
              { k: 'billing', l: 'Billing' },
            ].map(t => (
              <button key={t.k} onClick={() => setTab(t.k)} style={{
                padding: '14px 20px', background: 'transparent', border: 'none', cursor: 'pointer',
                fontSize: 13, fontFamily: 'Inter', fontWeight: 500,
                color: tab === t.k ? '#F5F5F5' : '#A3A3A3',
                borderBottom: tab === t.k ? '2px solid #A855F7' : '2px solid transparent',
                marginBottom: -1,
              }}>{t.l}</button>
            ))}
          </div>

          {tab === 'notifications' && <NotificationsTab />}
          {tab === 'subscriptions' && <SubscriptionsTab />}
          {tab === 'account' && <AccountTab />}
          {tab === 'billing' && <BillingTab />}
        </main>
      </div>
    </div>
  );
}

function NotificationsTab() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 64 }}>
      <div>
        <h2 style={{ fontFamily: 'Inter', fontSize: 20, fontWeight: 600, margin: 0 }}>Уведомления</h2>
        <p style={{ marginTop: 8, fontSize: 13, color: '#A3A3A3', lineHeight: 1.55 }}>
          scout стучится только когда происходит что-то важное. остальное — в дайджесте.
        </p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        <SettingsRow
          label="Частота уведомлений"
          desc="Как часто scout присылает нотификации"
        >
          <Segmented value="instant" options={[
            { k: 'instant', l: 'Мгновенно' },
            { k: 'daily', l: 'Дайджест · день' },
            { k: 'weekly', l: 'Дайджест · неделя' },
          ]}/>
        </SettingsRow>
        <SettingsRow label="Время доставки дайджеста" desc="Если выбрана периодика — когда приходит">
          <TimeInput v="09:00"/>
        </SettingsRow>
        <SettingsRow label="Каналы" desc="Куда отправлять">
          <div style={{ display: 'flex', gap: 8, flexDirection: 'column' }}>
            <ChannelChip label="Email" value="anna.k@gmail.com" checked />
            <ChannelChip label="Telegram" value="@anna_k" checked />
            <ChannelChip label="Push (браузер)"/>
            <ChannelChip label="Webhook (для API)"/>
          </div>
        </SettingsRow>
        <SettingsRow label="Типы событий" desc="О чём именно уведомлять">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <ToggleRow label="Падение цены" desc="Цена ушла ниже целевой или показала значимое падение" defaultChecked />
            <ToggleRow label="Аномалия (фейковая скидка)" desc="Подозрительный пик с обещанием 'скидки'" defaultChecked />
            <ToggleRow label="Появилось в наличии" desc="Товар вернулся на склад" defaultChecked />
            <ToggleRow label="Новые предложения" desc="Тот же товар появился на новом маркетплейсе"/>
            <ToggleRow label="Тихий режим · 22:00–08:00" desc="Откладывать ночные уведомления до утра" defaultChecked />
          </div>
        </SettingsRow>
      </div>
    </div>
  );
}

function SubscriptionsTab() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 64 }}>
      <div>
        <h2 style={{ fontFamily: 'Inter', fontSize: 20, fontWeight: 600, margin: 0 }}>Подписки</h2>
        <p style={{ marginTop: 8, fontSize: 13, color: '#A3A3A3', lineHeight: 1.55 }}>
          активные правила: когда и при каких условиях scout пингает по конкретным товарам.
        </p>
      </div>
      <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6, overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr 120px 140px 140px 80px', gap: 12, padding: '10px 16px', borderBottom: '1px solid #1C1C1C', fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          <span></span>
          <span>товар</span>
          <span>маркет</span>
          <span>условие</span>
          <span style={{ textAlign: 'right' }}>текущая цена</span>
          <span></span>
        </div>
        {[
          { name: 'Sony WH-1000XM5', src: 'wb', rule: 'цена < 30 000 ₽', price: 32490, active: true },
          { name: 'iPhone 15 Pro 256GB', src: 'ozon', rule: 'появится в наличии', price: 109990, active: true },
          { name: 'RTX 5090 FE', src: 'regard', rule: 'цена < 180 000 ₽', price: 219990, active: true },
          { name: 'PlayStation 5 Slim', src: 'dns', rule: 'любая аномалия', price: 54990, active: false },
          { name: 'Steam Deck OLED', src: 'dns', rule: 'цена < 70 000 ₽', price: 79990, active: true },
        ].map((s, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '40px 1fr 120px 140px 140px 80px', gap: 12, padding: '14px 16px', borderTop: '1px solid #1C1C1C', alignItems: 'center' }}>
            <ImagePlaceholder width={32} height={32} label=""/>
            <span style={{ fontSize: 13, fontWeight: 500 }}>{s.name}</span>
            <MarketplaceTag source={s.src}/>
            <span style={{ fontSize: 12, color: '#A3A3A3', fontFamily: 'JetBrains Mono, monospace' }}>{s.rule}</span>
            <span style={{ textAlign: 'right', fontSize: 13, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{fmt(s.price)} ₽</span>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
              <ToggleSwitch on={s.active}/>
              <span style={{ color: '#666' }}>···</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AccountTab() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 64 }}>
      <div>
        <h2 style={{ fontFamily: 'Inter', fontSize: 20, fontWeight: 600, margin: 0 }}>Аккаунт</h2>
        <p style={{ marginTop: 8, fontSize: 13, color: '#A3A3A3', lineHeight: 1.55 }}>
          email, пароль, danger zone. ничего сложного.
        </p>
      </div>
      <div>
        <SettingsRow label="Email" desc="Используется для логина и уведомлений">
          <TextInput v="anna.k@gmail.com"/>
        </SettingsRow>
        <SettingsRow label="Имя" desc="Как вас называть в интерфейсе">
          <TextInput v="Anna K."/>
        </SettingsRow>
        <SettingsRow label="Пароль" desc="Последнее изменение 2 месяца назад">
          <button style={btnGhostS}>сменить пароль</button>
        </SettingsRow>
        <SettingsRow label="Двухфакторная аутентификация" desc="Дополнительный код при входе">
          <ToggleSwitch on={false} large/>
        </SettingsRow>
        <SettingsRow label="Часовой пояс" desc="Влияет на время дайджеста">
          <SelectInput v="Europe/Moscow · UTC+3"/>
        </SettingsRow>

        <div style={{ marginTop: 32, padding: 24, border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, background: 'rgba(239,68,68,0.04)' }}>
          <div style={{ fontSize: 11, color: '#EF4444', textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 600 }}>danger zone</div>
          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Удалить аккаунт</div>
              <div style={{ marginTop: 4, fontSize: 12, color: '#A3A3A3' }}>удалит все 24 товара, всю историю цен, все подписки. без возможности восстановления.</div>
            </div>
            <button style={{ ...btnGhostS, color: '#EF4444', borderColor: 'rgba(239,68,68,0.3)' }}>удалить аккаунт</button>
          </div>
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid rgba(239,68,68,0.15)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Выйти со всех устройств</div>
              <div style={{ marginTop: 4, fontSize: 12, color: '#A3A3A3' }}>активных сессий: 3 (chrome · macos, ios, firefox · linux)</div>
            </div>
            <button style={btnGhostS}>logout everywhere</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function BillingTab() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 64 }}>
      <div>
        <h2 style={{ fontFamily: 'Inter', fontSize: 20, fontWeight: 600, margin: 0 }}>Подписка</h2>
        <p style={{ marginTop: 8, fontSize: 13, color: '#A3A3A3', lineHeight: 1.55 }}>текущий план и платежная информация.</p>
      </div>
      <div>
        <div style={{ background: '#141414', border: '1px solid #1C1C1C', borderRadius: 6, padding: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em' }}>текущий план</div>
            <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <span style={{ fontFamily: 'Cabinet Grotesk, Inter', fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em', textTransform: 'lowercase' }}>free</span>
              <span style={{ fontSize: 14, color: '#EF4444' }}>24 / 10 товаров · превышен</span>
            </div>
          </div>
          <button style={{
            height: 44, padding: '0 24px', background: '#A855F7', color: '#0A0A0A',
            border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 14, fontWeight: 600, fontFamily: 'Inter',
          }}>upgrade to pro · 490₽/мес</button>
        </div>
        <div style={{ marginTop: 32 }}>
          <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 12 }}>сравнение</div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 1, background: '#1C1C1C', border: '1px solid #1C1C1C', borderRadius: 6, overflow: 'hidden', fontSize: 13 }}>
            {[
              ['', 'Free', 'Pro', 'Team', true],
              ['Товаров', '10', '250', '∞'],
              ['Интервал парсинга', '6 ч', '1 ч', '15 мин'],
              ['История', '30 дней', '1 год', '∞'],
              ['AI verdict', '—', '✓', '✓'],
              ['Telegram alerts', '—', '✓', '✓'],
              ['API access', '—', '—', '✓'],
            ].map((row, i) => (
              <React.Fragment key={i}>
                <div style={{ background: '#0A0A0A', padding: 12, color: i === 0 ? '#666' : '#F5F5F5', fontWeight: i === 0 ? 500 : 400 }}>{row[0]}</div>
                <div style={{ background: '#0A0A0A', padding: 12, color: i === 0 ? '#666' : '#A3A3A3', textTransform: i === 0 ? 'uppercase' : 'none' }}>{row[1]}</div>
                <div style={{ background: i === 0 ? '#0A0A0A' : '#0F0A1A', padding: 12, color: i === 0 ? '#A855F7' : '#F5F5F5', fontWeight: i === 0 ? 600 : 500 }}>{row[2]}</div>
                <div style={{ background: '#0A0A0A', padding: 12, color: i === 0 ? '#666' : '#A3A3A3' }}>{row[3]}</div>
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingsRow({ label, desc, children }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: 32, padding: '24px 0', borderTop: '1px solid #1C1C1C' }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#F5F5F5' }}>{label}</div>
        <div style={{ marginTop: 6, fontSize: 12, color: '#A3A3A3', lineHeight: 1.5 }}>{desc}</div>
      </div>
      <div>{children}</div>
    </div>
  );
}
function Segmented({ options, value }) {
  return (
    <div style={{ display: 'inline-flex', background: '#141414', border: '1px solid #1C1C1C', borderRadius: 4, padding: 2 }}>
      {options.map(o => (
        <button key={o.k} style={{
          padding: '8px 14px', background: o.k === value ? '#1C1C1C' : 'transparent',
          color: o.k === value ? '#F5F5F5' : '#A3A3A3', border: 'none', cursor: 'pointer',
          borderRadius: 3, fontSize: 12, fontFamily: 'Inter',
        }}>{o.l}</button>
      ))}
    </div>
  );
}
function TextInput({ v, mono }) {
  return (
    <input defaultValue={v} style={{
      width: 320, padding: '10px 14px', background: '#0A0A0A', border: '1px solid #2E2E2E',
      borderRadius: 4, color: '#F5F5F5', fontSize: 13, fontFamily: mono ? 'JetBrains Mono, monospace' : 'Inter',
      outline: 'none',
    }}/>
  );
}
function TimeInput({ v }) {
  return (
    <input defaultValue={v} style={{
      width: 120, padding: '10px 14px', background: '#0A0A0A', border: '1px solid #2E2E2E',
      borderRadius: 4, color: '#F5F5F5', fontSize: 13, fontFamily: 'JetBrains Mono, monospace',
      outline: 'none', fontVariantNumeric: 'tabular-nums',
    }}/>
  );
}
function SelectInput({ v }) {
  return (
    <div style={{
      width: 320, padding: '10px 14px', background: '#0A0A0A', border: '1px solid #2E2E2E',
      borderRadius: 4, color: '#F5F5F5', fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer',
    }}>{v}<span style={{ color: '#666' }}>▾</span></div>
  );
}
function ChannelChip({ label, value, checked }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', background: '#0A0A0A', border: '1px solid #2E2E2E', borderRadius: 4, width: 360 }}>
      <div style={{
        width: 16, height: 16, borderRadius: 3, border: '1px solid #2E2E2E',
        background: checked ? '#A855F7' : '#0A0A0A', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>{checked && <span style={{ color: '#0A0A0A', fontSize: 10, fontWeight: 700 }}>✓</span>}</div>
      <span style={{ fontSize: 13, color: '#F5F5F5', flex: 1 }}>{label}</span>
      {value && <span style={{ fontSize: 12, color: '#A3A3A3', fontFamily: 'JetBrains Mono, monospace' }}>{value}</span>}
    </div>
  );
}
function ToggleSwitch({ on = false, large }) {
  const w = large ? 40 : 32, h = large ? 22 : 18;
  return (
    <div style={{
      width: w, height: h, borderRadius: h/2, background: on ? '#A855F7' : '#1C1C1C',
      border: '1px solid ' + (on ? '#A855F7' : '#2E2E2E'),
      position: 'relative', cursor: 'pointer', transition: 'background .15s',
    }}>
      <div style={{
        position: 'absolute', top: 1, left: on ? (w - h + 1) : 1,
        width: h - 4, height: h - 4, borderRadius: '50%',
        background: on ? '#0A0A0A' : '#666', transition: 'left .15s',
      }}/>
    </div>
  );
}
function ToggleRow({ label, desc, defaultChecked }) {
  const [on, setOn] = useStateW(defaultChecked || false);
  return (
    <div onClick={() => setOn(!on)} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 16px', background: '#0A0A0A', border: '1px solid #1C1C1C', borderRadius: 4, cursor: 'pointer' }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, color: '#F5F5F5', fontWeight: 500 }}>{label}</div>
        <div style={{ marginTop: 2, fontSize: 12, color: '#A3A3A3' }}>{desc}</div>
      </div>
      <ToggleSwitch on={on}/>
    </div>
  );
}
const btnGhostS = {
  height: 38, padding: '0 16px', background: 'transparent', color: '#F5F5F5',
  border: '1px solid #2E2E2E', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 500, fontFamily: 'Inter',
};

Object.assign(window, { Wishlist, Settings });
