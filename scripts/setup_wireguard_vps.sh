#!/usr/bin/env bash
# WireGuard на VPS (сервер туннеля). Запускать ОТ ROOT на VPS.
#
# Двухфазный запуск (обмен ключами между машинами):
#   Фаза 1 (без аргументов) — генерит ключи VPS и печатает ПУБЛИЧНЫЙ ключ:
#       bash scripts/setup_wireguard_vps.sh
#   Фаза 2 — когда получишь ПУБЛИЧНЫЙ ключ локальной машины:
#       LOCAL_PUBKEY=<pubkey_локалки> bash scripts/setup_wireguard_vps.sh
#
# После Фазы 2 БД/брокер на VPS надо забиндить ТОLьКО на туннель:
#   в .env поставить  INFRA_BIND_ADDR=10.10.0.1  и перезапустить compose.
set -euo pipefail

WG_DIR=/etc/wireguard
VPS_ADDR="${VPS_WG_ADDR:-10.10.0.1}"
LOCAL_ADDR="${LOCAL_WG_ADDR:-10.10.0.2}"
WG_PORT="${WG_PORT:-51820}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Запусти от root (sudo)." >&2
    exit 1
fi

if ! command -v wg &>/dev/null; then
    echo "[wg] Устанавливаю wireguard…"
    apt-get update -qq
    apt-get install -y -qq wireguard
fi

mkdir -p "$WG_DIR"
# Ключи генерим ОДИН раз — повторный запуск их не перетирает.
if [[ ! -f "$WG_DIR/privkey" ]]; then
    echo "[wg] Генерирую ключи VPS…"
    (umask 077; wg genkey | tee "$WG_DIR/privkey" | wg pubkey > "$WG_DIR/pubkey")
fi

VPS_PUB="$(cat "$WG_DIR/pubkey")"

if [[ -z "${LOCAL_PUBKEY:-}" ]]; then
    echo ""
    echo "=== ФАЗА 1 завершена ==="
    echo "ПУБЛИЧНЫЙ ключ VPS (понадобится для локального скрипта):"
    echo "  $VPS_PUB"
    echo ""
    echo "Дальше:"
    echo "  1) На локальной машине: bash scripts/setup_wireguard_local.sh"
    echo "     (она напечатает свой публичный ключ)"
    echo "  2) Вернись сюда и запусти ФАЗУ 2:"
    echo "     LOCAL_PUBKEY=<pubkey_локалки> bash scripts/setup_wireguard_vps.sh"
    exit 0
fi

echo "[wg] Пишу $WG_DIR/wg0.conf…"
cat > "$WG_DIR/wg0.conf" <<EOF
[Interface]
Address = ${VPS_ADDR}/24
ListenPort = ${WG_PORT}
PrivateKey = $(cat "$WG_DIR/privkey")

[Peer]
# Локальная машина с тяжёлыми парсерами (DNS/Citilink/Ozon/MVideo)
PublicKey = ${LOCAL_PUBKEY}
AllowedIPs = ${LOCAL_ADDR}/32
EOF
chmod 600 "$WG_DIR/wg0.conf"

echo "[wg] Поднимаю интерфейс wg0…"
systemctl enable wg-quick@wg0 >/dev/null 2>&1 || true
# down/up чтобы перечитать конфиг при повторном запуске
wg-quick down wg0 >/dev/null 2>&1 || true
wg-quick up wg0

# Фаервол: открыть ТОЛЬКО UDP-порт самого WG. Postgres/RabbitMQ наружу НЕ открываем —
# они будут слушать только на 10.10.0.1 (через INFRA_BIND_ADDR в .env).
if command -v ufw &>/dev/null; then
    ufw allow "${WG_PORT}/udp" >/dev/null 2>&1 || true
    echo "[wg] ufw: открыт ${WG_PORT}/udp"
fi

echo ""
echo "=== WireGuard на VPS поднят ==="
echo "  Адрес VPS в туннеле: ${VPS_ADDR}"
echo "  Порт:               ${WG_PORT}/udp"
echo "  Публичный ключ VPS: ${VPS_PUB}"
echo ""
echo "ВАЖНО: теперь в .env на VPS поставь  INFRA_BIND_ADDR=${VPS_ADDR}"
echo "и перезапусти: docker compose --profile vps-celery up -d"
echo "Проверка с локалки: ping ${VPS_ADDR}"
wg show
