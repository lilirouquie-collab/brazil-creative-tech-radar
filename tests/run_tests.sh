#!/usr/bin/env bash
# End-to-end test on invented data. Usage: bash tests/run_tests.sh [WORKDIR]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${1:-$(mktemp -d)}"
PORT=8765
rm -rf "$WORK/repo" "$WORK/sample" && mkdir -p "$WORK"
cp -r "$REPO" "$WORK/repo"
rm -rf "$WORK/repo/data"/* "$WORK/repo/site/data"/*
cd "$WORK/repo"
python3 tests/make_sample.py "$WORK/sample" "$PORT"
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$WORK/repo/tests/sites" >/dev/null 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
sleep 1
python3 -m unittest tests.test_units -v
echo "=== Run 1: first load (2026-11-09)"
python3 -m pipeline.run --local-data "$WORK/sample" --month 2026-11 --today 2026-11-09
echo "=== Run 2: next week, same registry month (2026-11-16)"
python3 -m pipeline.run --local-data "$WORK/sample" --month 2026-11 --today 2026-11-16
echo "=== Run 3: Gema Digital launches its site; new month (2026-12-14)"
cp tests/sites/modaflux/index.html tests/sites/gemadigital/index.html
sed -i 's/Modaflux/Gema Digital/g; s/modaflux/gemadigital/g' tests/sites/gemadigital/index.html
python3 - "$WORK/sample" <<'EOF'
import sys, zipfile, io, csv
d = sys.argv[1]
row = ["31313131","0001","90","1","LUMA","02","20261120","00","","","20261120","7410203","6203100",
       "RUA","X","1","","C","01000000","SP","7107","","","","","","","","",""]
buf = io.StringIO(); csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL).writerow(row)
with zipfile.ZipFile(f"{d}/Estabelecimentos5.zip","w") as z: z.writestr("X.ESTABELE", buf.getvalue().encode("latin-1"))
buf = io.StringIO(); csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL).writerow(["31313131","LUMA DESIGN DIGITAL LTDA","2062","49","15000,00","01",""])
with zipfile.ZipFile(f"{d}/Empresas5.zip","w") as z: z.writestr("X.EMPRECSV", buf.getvalue().encode("latin-1"))
EOF
python3 -m pipeline.run --local-data "$WORK/sample" --month 2026-12 --today 2026-12-14
python3 tests/check_results.py
echo "ALL TESTS PASSED (work dir: $WORK)"
