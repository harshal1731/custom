import json
from pathlib import Path

rows = json.loads(Path("live_sample_results.json").read_text(encoding="utf-8"))
total = [r for r in rows if "error" not in r]
passed = sum(1 for r in total if r.get("ok"))
print(f"OVERALL {passed}/{len(total)} ({100 * passed / len(total):.1f}%)")
print("FAILS:")
for r in total:
    if not r.get("ok"):
        name = str(r.get("recipient_or_employee"))[:40]
        print(
            f"  {r['form']:12} {r['file'][:42]:42} "
            f"cls={r.get('cls_ok')} fill={r.get('fill_pct')} "
            f"type={r.get('form_type')} name={name!r}"
        )
under = sum(1 for r in total if (r.get("ms") or 99999) <= 15000)
avg = sum(r.get("ms") or 0 for r in total) / max(len(total), 1)
print(f"under15s={under}/{len(total)} avg_ms={avg:.0f}")
