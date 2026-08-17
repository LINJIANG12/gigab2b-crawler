import requests
import re

url = 'https://www.gigab2b.com/public/assets/dist/assets/placement-mgj309xj.js'
code = requests.get(url).text

idx = code.find('product/list/search"')
if idx != -1:
    snippet = code[idx-300:idx+600]
    print("Snippet around search:\n", snippet)
