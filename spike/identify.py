#!/usr/bin/env python3
"""Stage 1: ask a vision model to inventory the room and label everything A, B, C..."""
import base64, json, os, urllib.request

os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
KEY = dict(l.strip().split("=", 1) for l in open(".env") if "=" in l)["OPENAI_API_KEY"]
img = base64.b64encode(open("inputs/room.jpg", "rb").read()).decode()

SCHEMA = """Return JSON only:
{"items":[{"id":"A","kind":"architecture"|"object","name":"short name for a user",
"description":"precise visual description with position, for an image model"}]}"""

body = {
 "model": "gpt-4.1",
 "messages": [{"role": "user", "content": [
   {"type": "text", "text":
    "Inventory this room photo. List every fixed architectural feature (walls, "
    "openings, fireplace, mantel, alcoves, ceiling features, flooring, switches) "
    "as kind=architecture, and every moveable object (furniture, decor, lamps, "
    "art, plants) as kind=object. Label them A, B, C in reading order. "
    "'description' must be precise enough that an image model could locate it "
    "without seeing labels. " + SCHEMA},
   {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}]}],
 "response_format": {"type": "json_object"},
}
req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
  data=json.dumps(body).encode(),
  headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
out = json.loads(urllib.request.urlopen(req, timeout=180).read())
items = json.loads(out["choices"][0]["message"]["content"])["items"]
json.dump(items, open("spike/out/inventory.json", "w"), indent=2)
for i in items:
    print(f"  {i['id']}  [{i['kind'][:4]}]  {i['name']}")
print(f"\n{len(items)} items -> spike/out/inventory.json")
