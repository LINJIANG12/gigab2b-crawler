import requests
import re

url = 'https://www.gigab2b.com/public/assets/dist/assets/placement-mgj309xj.js'
code = requests.get(url).text

for m in re.finditer(r'product_category_id', code):
    start = max(0, m.start() - 150)
    end = min(len(code), m.end() + 250)
    print("--- product_category_id Match ---")
    print(code[start:end])
