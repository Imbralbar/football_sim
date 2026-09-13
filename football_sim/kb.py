# dump_to_kb.py — uruchom przed aktualizacją KB
import pathlib, shutil

OUT = pathlib.Path("kb_export")
OUT.mkdir(exist_ok=True)

for p in pathlib.Path(".").rglob("*.py"):
    if any(x in p.parts for x in ("kb_export", "__pycache__", "tests", ".venv")):
        continue
    shutil.copy(p, OUT / "-".join(p.parts).replace(".py", ".txt"))

print(f"Gotowe: {len(list(OUT.iterdir()))} plików w {OUT}")