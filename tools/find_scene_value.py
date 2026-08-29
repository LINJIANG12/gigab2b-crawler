import requests
import re

url = 'https://www.gigab2b.com/public/assets/dist/assets/placement-mgj309xj.js'
code = requests.get(url).text

# 搜索 w = { ... } 或 enum scene 定义
m = re.findall(r'(\b[a-zA-Z0-9_]+\s*=\s*\{\s*search:\s*[^,]+,\s*category:\s*[^,]+[^}]+\})', code)
print("Scene enum matches:")
for item in m:
    print(item)

# 搜索所有的 scene: 数字
scenes = set(re.findall(r'scene:\s*([0-9a-zA-Z_.]+)', code))
print("Scene usages:", scenes)
