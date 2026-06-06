import json
from pathlib import Path

FILE = Path("var/dedup_auto_canary_post_reviewed.jsonl")

rows = [json.loads(x) for x in FILE.read_text(encoding="utf-8").splitlines() if x.strip()]
meta, items = rows[0], rows[1:]

print(f"Всего кейсов: {len(items)}")
print("Клавиши: c=correct_merge, w=wrong_merge, s=skip, q=quit")

def save():
    FILE.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in [meta] + items) + "\n",
        encoding="utf-8",
    )

try:
    for i, r in enumerate(items, 1):
        if (r.get("manual_verdict") or "").strip() in {"correct_merge", "wrong_merge"}:
            continue

        print("\n" + "=" * 80)
        print(f"[{i}/{len(items)}] audit_log_id={r.get('audit_log_id')}  category={r.get('to_product_category')}")
        print(f"OFFER : {r.get('offer_raw_name')}")
        print(f"CANON : {r.get('to_product_name')}")
        print(f"URL   : {r.get('offer_url')}")
        print(f"RULE  : {(r.get('signals') or {}).get('rule')} | signals={(r.get('signals') or {})}")

        ans = input("Вердикт [c/w/s/q]: ").strip().lower()
        if ans == "q":
            break
        if ans in {"", "s"}:
            continue
        if ans == "c":
            r["manual_verdict"] = "correct_merge"
        elif ans == "w":
            r["manual_verdict"] = "wrong_merge"
        else:
            continue

        note = input("Комментарий (optional): ").strip()
        if note:
            r["manual_notes"] = note

        save()  # сохраняем после каждого кейса

finally:
    save()
    print(f"\nСохранено: {FILE}")
