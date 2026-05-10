"""
菜單圖片 OCR 解析 — 使用 Google Gemini Vision
需要環境變數 GOOGLE_API_KEY
"""
import os
import re
import json


def parse_menu_image(image_bytes: bytes, mime_type: str = 'image/jpeg') -> list:
    """
    傳入圖片 bytes，回傳結構化品項列表：
    [{"category": str, "name": str, "price": int, "desc": str, "available": True}]

    若 GOOGLE_API_KEY 未設定，回傳 mock 資料供開發測試。
    """
    api_key = os.environ.get('GOOGLE_API_KEY', '')
    if not api_key:
        return _mock_menu()

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    prompt = (
        "Look at this menu image. Extract every food and drink item.\n"
        "Return ONLY a JSON array, no markdown, no explanation:\n"
        '[{"category":"...","name":"...","price":0,"desc":"..."}]\n'
        "Rules: category in Traditional Chinese; price as integer (0 if unknown); "
        "desc as short string or empty string.\n"
        "If the image is not a menu or contains no food items, return an empty array: []"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
    )

    text = response.text.strip()
    # Extract JSON array from response (handles code fences and extra prose)
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        return []
    text = match.group(0)

    items = json.loads(text)

    # Normalize and assign sequential IDs
    result = []
    for i, item in enumerate(items):
        result.append({
            "id": i + 1,
            "category": str(item.get("category") or "其他").strip(),
            "name":     str(item.get("name", "")).strip(),
            "price":    int(item.get("price") or 0),
            "desc":     str(item.get("desc") or "").strip(),
            "available": True,
        })
    return result


def _mock_menu() -> list:
    """GOOGLE_API_KEY 未設定時回傳的假資料"""
    return [
        {"id": 1, "category": "主餐", "name": "招牌牛肉堡", "price": 89, "desc": "雙層牛肉、生菜番茄", "available": True},
        {"id": 2, "category": "主餐", "name": "脆皮雞腿堡", "price": 79, "desc": "香酥炸雞腿", "available": True},
        {"id": 3, "category": "主餐", "name": "素食總匯堡", "price": 75, "desc": "豆腐排、時蔬", "available": True},
        {"id": 4, "category": "飲料", "name": "可口可樂", "price": 30, "desc": "中杯含冰", "available": True},
        {"id": 5, "category": "飲料", "name": "柳橙汁",   "price": 35, "desc": "現打100%", "available": True},
        {"id": 6, "category": "配餐", "name": "薯條（大）", "price": 45, "desc": "酥脆黃金薯條", "available": True},
        {"id": 7, "category": "配餐", "name": "洋蔥圈",   "price": 40, "desc": "六入",     "available": True},
    ]
