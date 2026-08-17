import re
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup

class ProductParser:
    """
    GigaB2B 商品全字段深度解析器（终极全量版）：
    支持 37 个字段深度抽取，涵盖基础信息、价格、分仓库存、代发运费、时效、LTL物流、
    体积重量、材质尺寸箱规、说明书文档、质保政策、全量副图、多变体与状态原因。
    """
    def __init__(self, base_url: str = "https://www.gigab2b.com"):
        self.base_url = base_url

    def parse_api_data(self, base_info_res: dict, price_list_res: dict = None, product_url: str = "") -> dict:
        """从官方 JSON API 响应中提取结构化全字段"""
        data = {
            "product_id": "",
            "sku": "",
            "title": "",
            "url": product_url,
            "category_path": "",
            "store_name": "",
            "store_code": "",
            "product_status": "公开在售现货",
            "status_reason": "",
            "price": "",
            "discount_price": "",
            "original_price": "",
            "moq": "1",
            "currency": "$",
            "total_stock": 0,
            "inventory_warehouses": {},
            "drop_ship_fee": "",
            "cloud_freight_range": "",
            "handling_time": "",
            "delivery_time": "",
            "is_ltl": "否",
            "total_weight": "",
            "total_volume": "",
            "main_color": "",
            "main_material": "",
            "origin_place": "",
            "upc": "",
            "product_dimensions": "",
            "package_size": "",
            "rating": "",
            "sales_count": "",
            "reviews_count": "",
            "shipping_and_services": {},
            "documents": "",
            "bullet_points": [],
            "description_text": "",
            "description_html": "",
            "main_image": "",
            "gallery_images": [],
            "specifications": {},
            "variants": [],
            "seller_info": {}
        }

        b_data = base_info_res.get('data', {}) if isinstance(base_info_res, dict) else {}
        p_info = b_data.get('product_info', {})
        s_info = b_data.get('seller_info', {})

        if not p_info:
            data["product_status"] = "商品不存在或已下架"
            data["status_reason"] = "平台接口未返回商品基础信息"
            return data

        # 1. 基础信息
        data["sku"] = str(p_info.get("sku") or "")
        data["title"] = str(p_info.get("product_name") or "")

        # 分类层级路径
        cat_info = p_info.get("category_info", [])
        if isinstance(cat_info, list) and cat_info:
            cat_names = [c.get("name") or c.get("category_name", "") for c in cat_info if isinstance(c, dict)]
            data["category_path"] = " > ".join([c for c in cat_names if c])

        # 店铺信息
        if isinstance(s_info, dict):
            data["store_name"] = str(s_info.get("store_name") or "")
            data["store_code"] = str(s_info.get("store_code") or "")
            data["seller_info"] = s_info

        # LTL大件物流标识
        ltl_info = p_info.get("ltl_info", {})
        if isinstance(ltl_info, dict) and ltl_info.get("is_ltl"):
            data["is_ltl"] = "是 (LTL大件卡车派送)"

        # 文档与手册
        docs = p_info.get("documents")
        if docs and isinstance(docs, list):
            doc_links = [d.get("url") or d.get("download_url") or str(d) for d in docs if isinstance(d, dict)]
            data["documents"] = "\n".join(doc_links)

        # 2. 图片媒体
        main_img = p_info.get("main_image", {})
        if isinstance(main_img, dict):
            data["main_image"] = main_img.get("popup") or main_img.get("thumb") or ""
        elif isinstance(main_img, str):
            data["main_image"] = main_img

        gallery = []
        for img in p_info.get("image_list", []):
            if isinstance(img, dict):
                src = img.get("popup") or img.get("thumb") or img.get("image") or ""
                if src and src not in gallery:
                    gallery.append(src)
            elif isinstance(img, str) and img not in gallery:
                gallery.append(img)
        data["gallery_images"] = gallery

        # 3. 规格参数、尺寸、箱规与材质
        specs = {}
        spec_obj = p_info.get("specification", {})
        desc_parts = []

        if isinstance(spec_obj, dict):
            if spec_obj.get("origin_place"):
                data["origin_place"] = str(spec_obj["origin_place"])
                specs["Origin Place"] = data["origin_place"]
                desc_parts.append(f"Origin Place: {data['origin_place']}")

            if spec_obj.get("upc"):
                data["upc"] = str(spec_obj["upc"])
                specs["UPC"] = data["upc"]
                desc_parts.append(f"UPC: {data['upc']}")

            if spec_obj.get("product_type_name"):
                specs["Product Type"] = str(spec_obj["product_type_name"])
                desc_parts.append(f"Product Type: {spec_obj['product_type_name']}")

            # 产品组装尺寸与净重
            dims = spec_obj.get("product_dimensions")
            if dims and isinstance(dims, list):
                dim_items = []
                for d in dims:
                    if isinstance(d, dict):
                        d_name = d.get('name') or 'Main'
                        d_str = f"{d_name}: {d.get('length','')}x{d.get('width','')}x{d.get('height','')} {d.get('unit','')}"
                        if d.get('weight'):
                            d_str += f" (Weight: {d.get('weight')} {d.get('weight_unit','')})"
                        dim_items.append(d_str)
                if dim_items:
                    data["product_dimensions"] = "\n".join(dim_items)
                    specs["Product Dimensions"] = data["product_dimensions"]
                    desc_parts.append(f"Product Dimensions: {'; '.join(dim_items)}")

            # 外包装箱规尺寸与毛重
            pkg = spec_obj.get("package_size")
            if pkg and isinstance(pkg, list):
                pkg_items = []
                for idx, p in enumerate(pkg):
                    if isinstance(p, dict):
                        p_str = f"Package {idx+1}: {p.get('length','')}x{p.get('width','')}x{p.get('height','')} {p.get('unit','')}"
                        if p.get('weight'):
                            p_str += f" (Gross Weight: {p.get('weight')} {p.get('weight_unit','')})"
                        pkg_items.append(p_str)
                if pkg_items:
                    data["package_size"] = "\n".join(pkg_items)
                    specs["Package Size"] = data["package_size"]
                    desc_parts.append(f"Package Size: {'; '.join(pkg_items)}")

            # 属性/材质/颜色 (property_infos)
            for prop in spec_obj.get("property_infos", []):
                if isinstance(prop, dict):
                    k = prop.get("property_name") or prop.get("name") or ""
                    v = prop.get("property_value_name") or prop.get("value") or ""
                    if k and v:
                        specs[k] = v
                        desc_parts.append(f"{k}: {v}")
                        if k.lower() == "main color":
                            data["main_color"] = v
                        elif k.lower() == "main material":
                            data["main_material"] = v

        data["specifications"] = specs

        # 4. 商品详细描述与核心卖点
        raw_desc = p_info.get("description")
        if raw_desc and isinstance(raw_desc, str) and raw_desc.strip():
            data["description_text"] = raw_desc.strip()
            data["description_html"] = raw_desc.strip()
        elif desc_parts:
            data["description_text"] = "\n".join([f"• {p}" for p in desc_parts])
            data["description_html"] = "<br/>".join(desc_parts)

        charac = p_info.get("characteristic")
        if isinstance(charac, list) and charac:
            data["bullet_points"] = [str(c) for c in charac if c]
        elif desc_parts:
            data["bullet_points"] = desc_parts[:8]

        # 5. 质量指标、退货率与热度
        ret_rate = p_info.get("return_rate", {})
        if isinstance(ret_rate, dict):
            rate_str = ret_rate.get("return_rate_str") or "Low"
            rate_val = ret_rate.get("return_rate")
            pur_num = ret_rate.get("purchase_num") or 0
            data["rating"] = f"Quality: {rate_str} (Return Rate {rate_val}%)" if rate_val is not None else f"Quality: {rate_str}"
            if pur_num:
                data["sales_count"] = f"{pur_num} Orders"
                data["reviews_count"] = str(pur_num)

        if not data["sales_count"] and p_info.get("download_count") and str(p_info.get("download_count")) != "**":
            data["sales_count"] = f"Downloads: {p_info['download_count']}"

        # 6. 服务保障与质保政策
        warranty = p_info.get("return_warranty", {})
        srv = {}
        if isinstance(warranty, dict):
            if warranty.get("level"):
                srv["Warranty Level"] = f"Level {warranty['level']}"
            deliv = warranty.get("delivered", {})
            if isinstance(deliv, dict) and deliv.get("days"):
                srv["Delivered Warranty"] = f"{deliv.get('days')} Days Return/Warranty Support"
            undeliv = warranty.get("undelivered", {})
            if isinstance(undeliv, dict) and undeliv.get("days"):
                srv["Undelivered Warranty"] = f"{undeliv.get('days')} Days Support (Restock Fee: {undeliv.get('rate', '')}%)"
            if warranty.get("descriptions"):
                srv["Warranty Policy"] = str(warranty["descriptions"])
        data["shipping_and_services"] = srv

        # 7. 价格体系、分仓库存与运费履约 (Price List API)
        price_visible = True
        qty_visible = True
        is_cooperate = True
        has_real_stock = False

        if price_list_res and isinstance(price_list_res, dict):
            pr_data = price_list_res.get("data", {})
            if isinstance(pr_data, dict):
                price_visible = pr_data.get("price_visible", True)
                qty_visible = pr_data.get("qty_visible", True)
                is_cooperate = pr_data.get("is_cooperate", True)

                # 基础价格
                base_pr = pr_data.get("base_price_info", {})
                if isinstance(base_pr, dict) and base_pr:
                    data["price"] = str(base_pr.get("price") or base_pr.get("final_price") or "")
                    data["discount_price"] = str(base_pr.get("discount_price") or "")
                    data["original_price"] = str(base_pr.get("msrp") or base_pr.get("line_through_normal_price") or base_pr.get("srp_price") or "")
                    data["currency"] = str(base_pr.get("currency_symbol") or "$")
                    data["moq"] = str(base_pr.get("moq") or "1")

                # 分仓库存与总库存统计
                stock_dict = {}
                total_stock = 0
                stock_dist = pr_data.get("stock_distributions", {})
                if isinstance(stock_dist, dict):
                    distributions = stock_dist.get("distributions", [])
                    if isinstance(distributions, list):
                        for dist in distributions:
                            if isinstance(dist, dict):
                                code = dist.get("warehouse_code") or f"WH-{dist.get('wh_id')}"
                                qty = int(dist.get("qty") or dist.get("quantity") or 0)
                                stock_dict[code] = f"{qty} in stock"
                                total_stock += qty
                elif isinstance(stock_dist, list):
                    for dist in stock_dist:
                        if isinstance(dist, dict):
                            w_name = dist.get("warehouse_name") or dist.get("name") or "Warehouse"
                            qty = int(dist.get("quantity") or dist.get("stock") or 0)
                            stock_dict[w_name] = f"{qty} in stock"
                            total_stock += qty

                data["inventory_warehouses"] = stock_dict
                data["total_stock"] = total_stock
                if total_stock > 0:
                    has_real_stock = True

                # 多变体规格明细
                options = pr_data.get("option", [])
                if isinstance(options, list) and options:
                    variants = []
                    option_prices = []
                    for opt in options:
                        if isinstance(opt, dict):
                            v_title = opt.get("title") or opt.get("name") or "Option"
                            v_price = opt.get("price") or opt.get("final_price")
                            if v_price:
                                option_prices.append(float(v_price))
                            variants.append({
                                "title": v_title,
                                "price": str(v_price) if v_price else "",
                                "stock": "In Stock" if opt.get("is_have_available_stock") else "Out of Stock"
                            })
                    data["variants"] = variants
                    if not data["price"] and option_prices:
                        min_p = min(option_prices)
                        max_p = max(option_prices)
                        data["price"] = f"{min_p:.2f}" if min_p == max_p else f"{min_p:.2f} - {max_p:.2f}"

                # 履约运费与时效信息 (fulfillment_options)
                fulfill = pr_data.get("fulfillment_options", {})
                if isinstance(fulfill, dict):
                    drop_ship = fulfill.get("drop_ship", {})
                    if isinstance(drop_ship, dict):
                        data["drop_ship_fee"] = str(drop_ship.get("total_show") or drop_ship.get("total_amount") or "")
                        est_day = drop_ship.get("estimated_ship_day", {})
                        if isinstance(est_day, dict) and est_day.get("min_day"):
                            data["delivery_time"] = f"{est_day['min_day']}~{est_day.get('max_day','')} Days"
                        h_time = drop_ship.get("handling_time", {})
                        if isinstance(h_time, dict) and h_time.get("min_day"):
                            data["handling_time"] = f"{h_time['min_day']}~{h_time.get('max_day','')} Days"

                    cloud = fulfill.get("cloud", {})
                    if isinstance(cloud, dict):
                        data["cloud_freight_range"] = str(cloud.get("total_show") or "")
                        w_v = cloud.get("weight_volume_info", {})
                        if isinstance(w_v, dict):
                            w_obj = w_v.get("weight", {})
                            if isinstance(w_obj, dict) and w_obj.get("weight_total"):
                                data["total_weight"] = f"{w_obj['weight_total']} {w_obj.get('unit','lbs')}"
                            v_obj = w_v.get("volume", {})
                            if isinstance(v_obj, dict) and v_obj.get("volume_total"):
                                data["total_volume"] = f"{v_obj['volume_total']} {v_obj.get('unit','ft³')}"

        # 8. 智能分析在售状态与缺失原因
        if data["price"] and has_real_stock:
            data["product_status"] = "公开在售现货"
            data["status_reason"] = "正常在售，各海外仓现货充足"
        elif data["price"] and not has_real_stock:
            data["product_status"] = "全仓已售罄/缺货"
            data["status_reason"] = "各海外仓现货已售罄，暂不可下单"
        elif not price_visible or not is_cooperate:
            data["product_status"] = "需申请供应商授权"
            data["status_reason"] = "供应商开启渠道保护，需单独申请合作授权后解锁底价"
            if not data["price"]:
                data["price"] = "[需申请供应商合作授权]"
        elif not has_real_stock:
            data["product_status"] = "全仓已售罄/缺货"
            data["status_reason"] = "全美各海外分仓均无现货，平台已隐藏底价"
            if not data["price"]:
                data["price"] = "[全美海外仓缺货/售罄]"
        else:
            data["product_status"] = "暂未开放采购"
            data["status_reason"] = "平台未配置公开批发价"
            if not data["price"]:
                data["price"] = "[平台未公开底价]"

        return data

    def parse_category_tree(self, categories_list: list) -> list[dict]:
        """递归展开全部分类树为扁平末级分类列表"""
        leaf_categories = []

        def _traverse(node, parent_path=""):
            c_id = node.get("category_id")
            c_name = node.get("category_name") or node.get("name") or ""
            current_path = f"{parent_path} > {c_name}" if parent_path else c_name
            children = node.get("children", [])

            if not children:
                leaf_categories.append({
                    "category_id": c_id,
                    "name": current_path,
                    "category_name": c_name
                })
            else:
                for child in children:
                    _traverse(child, current_path)

        for root in categories_list:
            _traverse(root)

        return leaf_categories
