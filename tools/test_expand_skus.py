import sqlite3
import json

conn = sqlite3.connect("gigab2b.db")
cursor = conn.cursor()

rows = cursor.execute("""
    SELECT product_id, sku, title, price, discount_price, total_stock, 
           main_color, main_material, product_dimensions, package_size, 
           variants, main_image
    FROM products
""").fetchall()

expanded_rows = []

for r in rows:
    pid, sku, title, price, discount_price, total_stock, main_color, main_material, dims, pkg_size, variants_json, main_img = r
    
    variants = []
    try:
        if variants_json:
            variants = json.loads(variants_json)
    except:
        pass
        
    if variants and len(variants) > 1:
        for v in variants:
            v_sku = v.get("sku") or sku
            v_spec = v.get("spec_name") or v.get("name") or ""
            v_price = v.get("price") or price
            v_stock = v.get("stock") or total_stock
            v_img = v.get("image") or main_img
            expanded_rows.append({
                "product_id": pid,
                "sku": v_sku,
                "spec": v_spec,
                "title": f"{title} [{v_spec}]" if v_spec else title,
                "price": v_price,
                "stock": v_stock,
                "main_image": v_img
            })
    else:
        expanded_rows.append({
            "product_id": pid,
            "sku": sku,
            "spec": "单品/默认规格",
            "title": title,
            "price": price,
            "stock": total_stock,
            "main_image": main_img
        })

print(f"==================================================")
print(f" SPU（商品主体）总数:          {len(rows):,} 件")
print(f" SKU（变体展开后独立明细）总数:  {len(expanded_rows):,} 行")
print(f"==================================================")
if expanded_rows:
    print("样本展示:")
    for ex in expanded_rows[:3]:
        print(f" - PID:{ex['product_id']} | SKU:{ex['sku']} | 规格:{ex['spec']} | 价格:{ex['price']} | 标题:{ex['title'][:30]}...")

conn.close()
