#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单监控脚本 - 每5分钟查询订单列表，发现非「NG一类」的订单即推送钉钉通知
"""

import requests
import json
import time
import os
import hmac
import hashlib
import base64
from datetime import datetime

# ==================== 从环境变量读取配置 ====================

DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", "")
API_TOKEN = os.environ.get("API_TOKEN", "")

# 如果环境变量没有配置，检查是否报错
if not DINGTALK_WEBHOOK:
    print("❌ 错误：未配置 DINGTALK_WEBHOOK 环境变量")
if not API_TOKEN:
    print("❌ 错误：未配置 API_TOKEN 环境变量")

# ==================== 业务配置 ====================

ALLOWED_PREFIX = "NG一类"

REQUEST_DATA = {
    "transNo": "",
    "paymentTransNoList": [],
    "outTradeNoList": [],
    "payeeAccountNo": "",
    "channelTransNoList": [],
    "paymentStatus": "",
    "appId": "",
    "mchtId": "",
    "countryCode": "NG",
    "channelCode": "",
    "isvCode": "",
    "appType": "",
    "e2eId": "",
    "createStartTime": "",
    "createEndTime": "",
    "completionStartTime": "",
    "completionEndTime": "",
    "pageSize": 50,
    "pageIndex": 1
}

CHECK_INTERVAL = 300


# ==================== 钉钉通知函数 ====================

def dingtalk_sign(secret):
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return timestamp, sign


def send_dingtalk_message(text):
    try:
        headers = {'Content-Type': 'application/json'}
        payload = {
            "msgtype": "text",
            "text": {"content": text}
        }
        
        if DINGTALK_SECRET:
            timestamp, sign = dingtalk_sign(DINGTALK_SECRET)
            webhook_url = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"
        else:
            webhook_url = DINGTALK_WEBHOOK
            
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 钉钉通知发送成功")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 钉钉通知发送失败: {result}")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 钉钉通知请求失败: {response.status_code}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 钉钉通知异常: {str(e)}")


# ==================== 订单查询函数 ====================

def query_orders():
    try:
        headers = {
            'accept': 'application/json, text/plain, */*',
            'b-access-token': API_TOKEN,
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://managementcdn.shpayinc.com',
            'referer': 'https://managementcdn.shpayinc.com/',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
        }
        
        response = requests.post(API_URL, json=REQUEST_DATA, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            orders = None
            if isinstance(data, dict):
                if 'data' in data and isinstance(data['data'], dict) and 'list' in data['data']:
                    orders = data['data']['list']
                elif 'list' in data:
                    orders = data['list']
                elif 'data' in data and isinstance(data['data'], list):
                    orders = data['data']
                elif isinstance(data, list):
                    orders = data
            
            if orders is not None:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📥 成功获取 {len(orders)} 条订单")
                return orders
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ 无法解析订单列表")
                return []
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 接口请求失败，状态码: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ 接口请求异常: {str(e)}")
        return []


# ==================== 核心检查逻辑 ====================

def check_orders():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 开始检查订单...")
    
    orders = query_orders()
    
    if not orders:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📭 未获取到订单数据")
        return
    
    abnormal_count = 0
    for order in orders:
        app_name = order.get('appName', '')
        if not app_name.startswith(ALLOWED_PREFIX):
            abnormal_count += 1
    
    if abnormal_count > 0:
        msg = f"🚨 尼日利亚代付订单二三类应用出现了新的订单，请查看\n"
        msg += f"📊 异常订单数量：{abnormal_count} 笔\n"
        msg += f"🕐 检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        send_dingtalk_message(msg)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚨 发现 {abnormal_count} 个异常订单，已推送钉钉通知")
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 无异常订单")


# ==================== 主函数 ====================

def main():
    print("=" * 50)
    print("🚀 订单监控脚本已启动")
    print(f"📋 监控规则：appName 不以「{ALLOWED_PREFIX}」开头的订单")
    print(f"⏱️  检查间隔：{CHECK_INTERVAL} 秒（{CHECK_INTERVAL//60} 分钟）")
    print("=" * 50)
    print("按 Ctrl+C 可停止脚本\n")
    
    check_orders()
    
    while True:
        time.sleep(CHECK_INTERVAL)
        check_orders()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 👋 脚本已停止")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💥 脚本异常: {str(e)}")
