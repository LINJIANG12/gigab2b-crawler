import requests
import re

url = 'https://www.gigab2b.com/public/assets/dist/assets/placement-mgj309xj.js'
code = requests.get(url).text

# 搜索 changeSort 的调用位置
for m in re.finditer(r'changeSort\s*\([^\)]+\)', code):
    print("Sort call:", m.group(0))

# 搜索 order 字符串（ASC/DESC）
m2 = re.findall(r'(\b[a-zA-Z0-9_]*:\s*"(?:asc|desc|ASC|DESC)")', code)
print("Order options:", set(m2))
