import requests
import re

url = 'https://www.gigab2b.com/public/assets/dist/assets/placement-mgj309xj.js'
code = requests.get(url).text

# 查找所有发送给 search 的参数名
matches = re.findall(r'product/list/search[^\}]+\}', code)
print(f"Matches count: {len(matches)}")
for m in matches[:5]:
    print("--- Match ---")
    print(m[:300])

# 查找所有包含 category 的属性键
keys = set(re.findall(r'[a-zA-Z0-9_]*category[a-zA-Z0-9_]*', code, re.IGNORECASE))
print("\nCategory keys found in JS:")
for k in sorted(keys):
    print(" ", k)
