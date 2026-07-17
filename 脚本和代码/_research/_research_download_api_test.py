# -*- coding: utf-8 -*-
"""测试：直接用 requests 调用下载 API（无需浏览器）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json
import requests
from pathlib import Path

COOKIE_FILE = Path.home() / ".claude/skills/wkinfo-cli/storage/wkinfo-cookies.json"
DL_DIR = Path(r"D:\ai\Claudecode\威科案例检索和下载-20260716\临时资源\downloads")
DL_DIR.mkdir(parents=True, exist_ok=True)

# 已知一个判决书的 docId
DOC_ID = "MjA0MTUzMjY0NDg="
SEARCH_ID = "414d083230784dcfb945e42824384f25"
FILENAME = "某保险公司与孙某保证保险合同纠纷一案_20260716下载.pdf"

# 加载 cookie
with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)

cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list)
uid = "1000250387"
identification = "_79cfe8d062d911f1b542513c0fcf6872"

headers = {
    "cookie": cookie_str,
    "uid": uid,
    "identification": identification,
    "module": "",
    "content-type": "application/json;charset=UTF-8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0.0.0",
    "accept": "application/json, text/plain, */*",
    "referer": "https://law.wkinfo.com.cn/judgment-documents/list",
}

print('===Step 1: downloadLimit===')
r = requests.post(
    "https://law.wkinfo.com.cn/csi/document/downloadLimit",
    headers=headers,
    json={
        "indexId": "law.case",
        "fileType": "pdf",
        "docId": DOC_ID,
        "showType": 0,
        "module": "",
        "cellList": None
    },
    timeout=30
)
print(f'Status: {r.status_code}')
print(f'Body: {r.text[:500]}')

print('\n===Step 2: downloadPath===')
r2 = requests.post(
    "https://law.wkinfo.com.cn/csi/document/downloadPath",
    headers=headers,
    json={
        "indexId": "law.case",
        "fileType": "pdf",
        "docId": DOC_ID,
        "showType": 0,
        "filename": FILENAME,
        "module": "",
        "searchId": SEARCH_ID,
        "containLink": True
    },
    timeout=30
)
print(f'Status: {r2.status_code}')
print(f'Body: {r2.text[:500]}')
key = r2.json()["data"]["key"]
print(f'Got key: {key}')

print('\n===Step 3: 下载文件===')
r3 = requests.get(
    f"https://law.wkinfo.com.cn/api/download?key={key}",
    headers={
        "cookie": cookie_str,
        "uid": uid,
        "identification": identification,
        "user-agent": "Mozilla/5.0",
    },
    timeout=60,
    stream=True
)
print(f'Status: {r3.status_code}')
print(f'Content-Type: {r3.headers.get("content-type")}')
print(f'Content-Disposition: {r3.headers.get("content-disposition")}')
print(f'Content-Length: {r3.headers.get("content-length")}')

# 保存到文件
filename = r3.headers.get('content-disposition', '').split('filename=')[-1].strip('"')
if not filename:
    filename = FILENAME
out = DL_DIR / filename
with open(out, 'wb') as f:
    for chunk in r3.iter_content(chunk_size=8192):
        f.write(chunk)
print(f'\n===保存到===\n{out}')
print(f'大小: {out.stat().st_size} 字节')

# 验证是 PDF
with open(out, 'rb') as f:
    head = f.read(5)
print(f'文件头: {head} (应该以 %PDF- 开头)')