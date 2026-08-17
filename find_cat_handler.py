import requests
import re

url = 'https://www.gigab2b.com/public/assets/dist/assets/placement-mgj309xj.js'
code = requests.get(url).text

# 搜索包含 category 的函数和逻辑
for m in re.finditer(r'category[a-zA-Z0-9_]*\s*\(|handleCategory|selectCategory|changeCategory', code):
    start = max(0, m.start() - 100)
    end = min(len(code), m.end() + 200)
    print("--- Function context ---")
    print(code[start:end])
