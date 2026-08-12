from pdf2image import convert_from_bytes
import pytesseract
import json
import re

pdf = open("/tmp/w2.pdf", "rb").read()
imgs = convert_from_bytes(pdf, dpi=300)
img = imgs[0]
print("size", img.size, "pages", len(imgs))
text = pytesseract.image_to_string(img, config="--oem 3 --psm 4")
print("===== FULL TEXT PSM4 =====")
print(text)
print("===== FULL TEXT PSM6 =====")
print(pytesseract.image_to_string(img, config="--oem 3 --psm 6"))

data = pytesseract.image_to_data(img, config="--oem 3 --psm 11", output_type=pytesseract.Output.DICT)
n = len(data["text"])
rows = []
for i in range(n):
    t = data["text"][i].strip()
    if not t:
        continue
    conf = float(data["conf"][i]) if str(data["conf"][i]).lstrip("-").isdigit() else -1
    rows.append(
        {
            "l": data["left"][i],
            "t": data["top"][i],
            "w": data["width"][i],
            "h": data["height"][i],
            "conf": conf,
            "text": t,
        }
    )

money = [r for r in rows if re.search(r"\d+\.\d{2}", r["text"])]
print("===== MONEY TOKENS =====")
for r in sorted(money, key=lambda x: (x["t"], x["l"])):
    print(r)

labels = [
    r
    for r in rows
    if any(
        k in r["text"].lower()
        for k in [
            "wage",
            "employer",
            "employee",
            "social",
            "medicare",
            "ein",
            "control",
            "name",
            "address",
            "state",
            "federal",
            "dependent",
            "allocated",
            "tips",
        ]
    )
]
print("===== LABEL TOKENS =====")
for r in sorted(labels, key=lambda x: (x["t"], x["l"]))[:80]:
    print(r)

with open("/tmp/w2_ocr_words.json", "w", encoding="utf-8") as f:
    json.dump(rows, f)
print("saved", len(rows), "words")
