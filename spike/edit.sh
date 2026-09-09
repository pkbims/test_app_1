#!/bin/bash
# Usage: ./edit.sh <name> <prompt> [extra curl -F args...]
# Runs one gpt-image-2 edit against inputs/room.jpg and saves spike/out/<name>.png
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
NAME="$1"; PROMPT="$2"; shift 2
printf '%s\n' "$PROMPT" > "spike/out/$NAME.txt"
curl -sS https://api.openai.com/v1/images/edits \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F "model=gpt-image-2" \
  -F "image=@${SRC:-inputs/room.jpg}" \
  -F "size=1536x1024" \
  -F "prompt=$PROMPT" \
  "$@" > "spike/out/$NAME.json"
python3 - "$NAME" <<'PY'
import json,sys,base64,os
n=sys.argv[1]; d=json.load(open(f"spike/out/{n}.json"))
if "error" in d:
    print("API ERROR:", json.dumps(d["error"])[:400]); raise SystemExit(1)
b=d["data"][0].get("b64_json")
open(f"spike/out/{n}.png","wb").write(base64.b64decode(b))
os.remove(f"spike/out/{n}.json")
u=d.get("usage",{})
print(f"saved spike/out/{n}.png  tokens={u}")
PY
