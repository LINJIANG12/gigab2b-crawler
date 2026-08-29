import requests
import re

url = 'https://www.gigab2b.com/public/assets/dist/assets/placement-mgj309xj.js'
code = requests.get(url).text

# 搜索所有 sort 相关的代码
sorts = set(re.findall(r'[a-zA-Z0-9_]*sort[a-zA-Z0-9_]*', code, re.IGNORECASE))
print("Sort keys in JS:")
for s in sorted(sorts):
    print(" ", s)

# 搜索所有的排序选项对象
m = re.findall(r'(\b[a-zA-Z0-9_]+\s*:\s*\[\s*\{[^}]*sort[^}]+\}\s*\])', code)
print("\nSort list definitions:")
for item in m[:5]:
    print(item)
