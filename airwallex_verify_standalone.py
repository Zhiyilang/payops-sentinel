#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Airwallex 沙盒一键验证脚本（Standalone · 零第三方依赖 · 自动选路）
============================================================
只用 Python 标准库（urllib），不需要 pip install 任何包。
只要另一台电脑装了 Python 3（任意 3.x 版本）即可运行。

用法（二选一）：

  方式 A（推荐，Key 不进命令行历史）：
    set AIRWALLEX_CLIENT_ID=你的client_id
    set AIRWALLEX_API_KEY=你的api_key
    python airwallex_verify_standalone.py

  方式 B（简单直接）：
    python airwallex_verify_standalone.py <client_id> <api_key>

网络说明（重要）：
  脚本默认【忽略系统代理、强制直连】。若你的 VPN 是「全局 / TUN 模式」，
  系统流量会经 VPN 虚拟网卡出去，直连即可访问境外沙盒域名。
  若直连失败，脚本会自动改用「系统代理」重试一次。
  也可手动指定：
    set USE_SYSTEM_PROXY=0   强制直连（忽略 http_proxy 环境变量）
    set USE_SYSTEM_PROXY=1   强制使用系统代理（走 http_proxy 环境变量）

预期结果：多行 [PASS]，最后出现 "ALL CHECKS PASSED"。
"""

import sys
import os
import json
import uuid
import urllib.request
import urllib.error

SANDBOX_BASE = "https://api-sandbox.airwallex.com/api/v1"
OPENER = None  # 在 main 里根据探测结果设置


def make_opener(use_system_proxy):
    if use_system_proxy:
        # 沿用环境变量 http_proxy / https_proxy
        return urllib.request.build_opener()
    # 空 ProxyHandler => 强制直连，忽略任何系统代理（适配 TUN / 全局 VPN）
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http(method, path, token=None, body=None, extra_headers=None, timeout=30):
    global OPENER
    url = SANDBOX_BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"_error": e.read().decode("utf-8", "ignore")[:400]}
    except Exception as e:  # 网络 / DNS / SSL 等
        return 0, {"_error": "{}: {}".format(type(e).__name__, e)}


def login(cid, key, use_system_proxy):
    opener = make_opener(use_system_proxy)
    req = urllib.request.Request(
        SANDBOX_BASE + "/authentication/login",
        method="POST",
        headers={"Content-Type": "application/json",
                 "x-client-id": cid, "x-api-key": key})
    try:
        with opener.open(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"_error": e.read().decode("utf-8", "ignore")[:400]}
    except Exception as e:
        return 0, {"_error": "{}: {}".format(type(e).__name__, e)}


def amount_of(b):
    """从余额条目里尽量取出金额数字。"""
    for k in ("available_amount", "total_amount", "amount",
              "available_balance", "balance"):
        v = b.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            return float(v.get("amount", 0))
    return 0.0


def main():
    # ---- 读取凭据：优先环境变量，其次命令行参数 ----
    cid = os.environ.get("AIRWALLEX_CLIENT_ID") or (sys.argv[1] if len(sys.argv) > 1 else "")
    key = os.environ.get("AIRWALLEX_API_KEY") or (sys.argv[2] if len(sys.argv) > 2 else "")
    if not (cid and key):
        print("缺少凭据。用法：")
        print("  python airwallex_verify_standalone.py <client_id> <api_key>")
        print("或先执行：")
        print("  set AIRWALLEX_CLIENT_ID=你的client_id")
        print("  set AIRWALLEX_API_KEY=你的api_key")
        print("再运行本脚本。")
        return 1

    print("=" * 60)
    print(" Airwallex 沙盒验证（standalone · 零依赖 · 自动选路）")
    print(" Python " + sys.version.split()[0])
    sys_proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
                 or os.environ.get("HTTP_PROXY") or "")
    print(" 系统代理环境变量: " + (sys_proxy if sys_proxy else "无"))
    print("=" * 60)

    # ---- 决定走哪种网络通道 ----
    forced = os.environ.get("USE_SYSTEM_PROXY", "").lower()
    if forced in ("1", "true", "yes"):
        prefer_direct = False
        mode_label = "强制系统代理"
    elif forced in ("0", "false", "no"):
        prefer_direct = True
        mode_label = "强制直连"
    else:
        prefer_direct = True          # 默认先试直连
        mode_label = "自动（先直连，失败回退系统代理）"

    # 先按首选登录
    s, d = login(cid, key, use_system_proxy=not prefer_direct)
    ok = (s == 200 and (d.get("token") or d.get("access_token")))
    if not ok and not forced:
        # 自动回退到另一种方式
        s, d = login(cid, key, use_system_proxy=prefer_direct)
        ok = (s == 200 and (d.get("token") or d.get("access_token")))
        if ok:
            prefer_direct = not prefer_direct

    if not ok:
        print("[FAIL] 直接连登录失败: {}".format(
            login(cid, key, use_system_proxy=False)[1].get("_error", "")))
        print("[FAIL] 系统代理登录也失败: {}".format(
            login(cid, key, use_system_proxy=True)[1].get("_error", "")))
        print("\n排查建议：")
        print("  1) 若『直连』报 DNS / 超时 -> 这台电脑的 VPN 没开『全局 / TUN 模式』，")
        print("     系统流量没走 VPN，需要把 VPN 切成全局模式后重跑。")
        print("  2) 若『系统代理』报 502 / SSL 错误 -> 环境变量里的代理通道不通")
        print("     （VPN 节点掉了，或规则模式没覆盖 airwallex），请重连 VPN 节点。")
        print("  也可手动指定通道后重跑：")
        print("     set USE_SYSTEM_PROXY=0   强制直连")
        print("     set USE_SYSTEM_PROXY=1   强制系统代理")
        return 1

    global OPENER
    OPENER = make_opener(use_system_proxy=not prefer_direct)
    token = d.get("token") or d.get("access_token")
    chosen = "直连(忽略系统代理)" if prefer_direct else "系统代理"
    print("[PASS] 登录成功（{} · {}）Token 30 分钟内有效".format(mode_label, chosen))

    # 2) 全球账户（没有就创建一个 USD/US 账户）
    s, d = http("GET", "/global_accounts", token=token)
    if s == 200:
        accounts = d.get("items", d) if isinstance(d, dict) else d
        print("[PASS] 全球账户：{} 个".format(len(accounts)))
    else:
        print("[FAIL] 全球账户查询 HTTP {}: {}".format(s, d.get("_error", d)))
        accounts = []
    if not accounts:
        print("       无账户，正在创建 USD/US 全球账户...")
        s2, d2 = http("POST", "/global_accounts/create", token=token, body={
            "country_code": "US",
            "required_features": [{"currency": "USD", "transfer_method": "LOCAL"}],
            "request_id": uuid.uuid4().hex,
        })
        if s2 == 200:
            print("[PASS] 已创建全球账户：{}".format(d2.get("id")))
            s, d = http("GET", "/global_accounts", token=token)
            accounts = d.get("items", d) if isinstance(d, dict) else d
        else:
            print("[FAIL] 创建账户 HTTP {}: {}".format(s2, d2.get("_error", d2)))

    # 3) 模拟存款 $25,000（主单位，25000 = $25,000）
    if accounts:
        ga_id = accounts[0].get("id")
        s, d = http("POST", "/simulation/deposit/create", token=token, body={
            "global_account_id": ga_id,
            "amount": 25000,
            "payer_name": "Seed funding",
            "request_id": uuid.uuid4().hex,
        })
        if s == 200:
            print("[PASS] 模拟存款 $25,000 → {}（resp id: {}）".format(
                ga_id, d.get("id", "ok")))
        else:
            print("[FAIL] 模拟存款 HTTP {}: {}".format(s, d.get("_error", d)))

    # 4) 钱包余额
    s, d = http("GET", "/balances/current", token=token)
    if s == 200:
        rows = d.get("items", d) if isinstance(d, dict) else d
        bal = ", ".join("{:,.2f} {}".format(amount_of(b), b.get("currency", "USD"))
                        for b in rows) if rows else "（空）"
        print("[PASS] 余额：" + bal)
    else:
        print("[FAIL] 余额查询 HTTP {}: {}".format(s, d.get("_error", d)))

    # 5) 转账记录
    s, d = http("GET", "/transfers", token=token)
    if s == 200:
        items = d.get("items", d) if isinstance(d, dict) else d
        print("[PASS] 转账记录：{} 条".format(len(items)))
    else:
        print("[FAIL] 转账查询 HTTP {}: {}".format(s, d.get("_error", d)))

    print("\n==> 如果上面多为 [PASS]，说明 PayOpsSentinel 已成功连上 Airwallex 沙盒！")
    print("    把这段输出贴回给 AI 即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
