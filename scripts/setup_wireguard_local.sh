#!/usr/bin/env bash
# WireGuard на ЛОКАЛЬНОЙ машине (клиент туннеля — там крутятся тяжёлые парсеры).
# Запускать с sudo на своей машине.
#
# Двухфазный запуск:
#   Фаза 1 (без аргументов) — генерит ключи локалки и печатает ПУБЛИЧНЫЙ ключ:
#       sudo bash scripts/setup_wireguard_local.sh
#   Фаза 2 — когда есть публичный ключ VPS и его публичный IP:
#       sudo VPS_ENDPOINT=<публичный_ip_vps> VPS_PUBKEY=<pubkey_vps> \
#            bash scripts/setup_wireguard_local.sh
set -euo pipefail

WG_DIR=/etc/wireguard
VPS_ADDR="${VPS_WG_ADDR:-10.10.0.1}"
LOCAL_ADDR="${LOCAL_WG_ADDR:-10.10.0.2}"
WG_PORT="${WG_PORT:-51820}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Запусти с sudo." >&2
    exit 1
fi

if ! command -v wg &>/dev/null; then
    echo "[wg] Устанавливаю wireguard…"
    apt-get update -qq
    apt-get install -y -qq wireguard
fi

mkdir -p "$WG_DIR"
if [[ ! -f "$WG_DIR/privkey" ]]; then
    echo "[wg] Генерирую ключи локальной машины…"
    (umask 077; wg genkey | tee "$WG_DIR/privkey" | wg pubkey > "$WG_DIR/pubkey")
fi

LOCAL_PUB="$(cat "$WG_DIR/pubkey")"

if [[ -z "${VPS_ENDPOINT:-}" || -z "${VPS_PUBKEY:-}" ]]; then
    echo ""
    echo "=== ФАЗА 1 завершена ==="
    echo "ПУБЛИЧНЫЙ ключ локальной машины (вставь в VPS-скрипт как LOCAL_PUBKEY):"
    echo "  $LOCAL_PUB"
    echo ""
    echo "Дальше запусти ФАЗУ 2 (нужен публичный IP VPS и его публичный ключ):"
    echo "  sudo VPS_ENDPOINT=<ip_vps> VPS_PUBKEY=<pubkey_vps> \\"
    echo "       bash scripts/setup_wireguard_local.sh"
    exit 0
fi

echo "[wg] Пишу $WG_DIR/wg0.conf…"
cat > "$WG_DIR/wg0.conf" <<EOF
[Interface]
Address = ${LOCAL_ADDR}/24
PrivateKey = $(cat "$WG_DIR/privkey")

[Peer]
# VPS — там БД/брокер/сайт
PublicKey = ${VPS_PUBKEY}
Endpoint = ${VPS_ENDPOINT}:${WG_PORT}
# Маршрутизируем В ТУННЕЛЬ только адрес VPS — остальной трафик локалки идёт как обычно
# (важно: иначе парсеры пойдут в интернет через VPS и потеряют резидентный IP → Qrator 403).
AllowedIPs = ${VPS_ADDR}/32
PersistentKeepalive = 25
EOF
chmod 600 "$WG_DIR/wg0.conf"

echo "[wg] Поднимаю интерфейс wg0…"
systemctl enable wg-quick@wg0 >/dev/null 2>&1 || true
wg-quick down wg0 >/dev/null 2>&1 || true
wg-quick up wg0

echo ""
echo "=== WireGuard на локальной машине поднят ==="
echo "  Адрес локалки в туннеле: ${LOCAL_ADDR}"
echo "  VPS в туннеле:           ${VPS_ADDR}"
echo ""
echo "Проверка туннеля:  ping ${VPS_ADDR}"
echo "Дальше: cp .env.home-dns-worker.example .env.home-dns-worker (впиши креды VPS)"
echo "        затем: bash scripts/run_heavy_worker_remote.sh"
wg show
