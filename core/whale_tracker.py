# ============================================================
# Trade Lak Bot - Whale Tracker (On-Chain Analysis)
# تتبع تحركات الحيتان والمحافظ الكبيرة على البلوكشين
# Updated: May 2026
#
# APIs Used:
#   - Etherscan API v2  (Ethereum chain_id=1) ✅ ACTIVE
#   - BSC Public RPC    (BNB Chain - free, no key needed) ✅ ACTIVE
#   - Whale Alert API   (Large transfer alerts - optional)
#
# Note: BSC via Etherscan v2 requires paid plan.
#       We use BSC public RPC as free alternative.
# ============================================================

import requests
import logging
import time

logger = logging.getLogger(__name__)

# ---- Etherscan API v2 ----
ETHERSCAN_API_KEY = "W994R5JJQQVGX1ZI8KD8ZIFAFZ52RSUMMC"
ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"
ETH_CHAIN_ID      = 1   # Ethereum Mainnet

# ---- BSC Public RPC (free, no API key needed) ----
BSC_RPC_ENDPOINTS = [
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.defibit.io/",
    "https://bsc-dataseed1.ninicoin.io/",
]

# ---- Whale Thresholds ----
WHALE_TRANSFER_USD   = 500_000
EXCHANGE_INFLOW_USD  = 1_000_000
EXCHANGE_OUTFLOW_USD = 1_000_000

# ---- Known Exchange Addresses ----
KNOWN_EXCHANGES = {
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": "Binance ETH",
    "0xd551234ae421e3bcba99a0da6d736074f22192ff": "Binance ETH 2",
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0xa090e606e30bd747d4e6245a1517ebe430f0057e": "Coinbase",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance BSC",
}

KNOWN_WHALES = {
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance Hot Wallet",
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8": "Binance Cold Wallet",
    "0x40b38765696e3d5d8d9d834d8aad4bb6e418e489": "Robinhood",
}

# ---- Token Contracts ----
TOKEN_CONTRACTS_ETH = {
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
}


class WhaleTracker:
    """
    يراقب تحركات الحيتان والمحافظ الكبيرة على البلوكشين
    Monitors whale movements and large wallet activities on-chain

    Chains supported:
    - Ethereum: Etherscan API v2 (full support with free key)
    - BSC:      Public RPC (balance/block queries, free)
    """

    def __init__(self):
        self.etherscan_key   = ETHERSCAN_API_KEY
        self.whale_alert_key = "YourWhaleAlertKey"  # optional
        self.cache     = {}
        self.cache_ttl = 300  # 5 minutes
        logger.info("✅ WhaleTracker initialized (Etherscan v2 + BSC RPC)")

    # ----------------------------------------------------------------
    # Etherscan API v2 Helper
    # ----------------------------------------------------------------
    def _etherscan(self, chain_id, module, action, params={}):
        """Make Etherscan API v2 call. Returns (ok, result, msg)."""
        try:
            p = {
                "chainid": chain_id,
                "module":  module,
                "action":  action,
                "apikey":  self.etherscan_key,
                **params,
            }
            r = requests.get(ETHERSCAN_V2_BASE, params=p, timeout=5)
            data = r.json()
            status = data.get("status", "0")
            msg    = data.get("message", "")
            result = data.get("result", [])
            ok = (status == "1" or msg == "OK")
            return ok, result, msg
        except Exception as e:
            logger.error(f"Etherscan API error [{module}/{action}]: {e}")
            return False, [], str(e)

    # ----------------------------------------------------------------
    # BSC Public RPC Helper
    # ----------------------------------------------------------------
    def _bsc_rpc(self, method, params=[]):
        """Make BSC JSON-RPC call via public endpoint."""
        for rpc_url in BSC_RPC_ENDPOINTS:
            try:
                r = requests.post(
                    rpc_url,
                    json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
                    timeout=5,
                )
                data = r.json()
                if "result" in data:
                    return data["result"]
            except Exception as e:
                logger.debug(f"BSC RPC {rpc_url} failed: {e}")
                continue
        return None

    # ----------------------------------------------------------------
    # Balance Queries
    # ----------------------------------------------------------------
    def get_eth_balance(self, address):
        """Get ETH balance of an address."""
        ok, result, _ = self._etherscan(ETH_CHAIN_ID, "account", "balance",
                                        {"address": address, "tag": "latest"})
        return int(result) / 1e18 if ok and result else 0.0

    def get_bnb_balance(self, address):
        """Get BNB balance via BSC public RPC."""
        result = self._bsc_rpc("eth_getBalance", [address, "latest"])
        return int(result, 16) / 1e18 if result else 0.0

    # ----------------------------------------------------------------
    # ERC-20 Token Transfers (Ethereum)
    # ----------------------------------------------------------------
    def get_eth_token_transfers(self, address, token="USDT", limit=20):
        """Get recent ERC-20 token transfers on Ethereum."""
        params = {"address": address, "page": "1", "offset": str(limit), "sort": "desc"}
        contract = TOKEN_CONTRACTS_ETH.get(token)
        if contract:
            params["contractaddress"] = contract
        ok, result, _ = self._etherscan(ETH_CHAIN_ID, "account", "tokentx", params)
        if not ok or not isinstance(result, list):
            return []
        transfers = []
        for tx in result:
            decimals = int(tx.get("tokenDecimal", 18))
            value    = int(tx.get("value", 0)) / (10 ** decimals)
            transfers.append({
                "hash":      tx.get("hash", ""),
                "from":      tx.get("from", ""),
                "to":        tx.get("to", ""),
                "value":     value,
                "token":     tx.get("tokenSymbol", token),
                "timestamp": int(tx.get("timeStamp", 0)),
                "block":     tx.get("blockNumber", ""),
                "chain":     "ETH",
            })
        return transfers

    # ----------------------------------------------------------------
    # Large ETH Transactions
    # ----------------------------------------------------------------
    def get_large_eth_transactions(self, address, min_eth=10.0, limit=20):
        """Get large ETH transactions for whale tracking."""
        ok, result, _ = self._etherscan(ETH_CHAIN_ID, "account", "txlist", {
            "address": address, "page": "1", "offset": str(limit), "sort": "desc"
        })
        if not ok or not isinstance(result, list):
            return []
        return [
            {
                "hash":      tx.get("hash", ""),
                "from":      tx.get("from", ""),
                "to":        tx.get("to", ""),
                "value_eth": int(tx.get("value", 0)) / 1e18,
                "timestamp": int(tx.get("timeStamp", 0)),
                "block":     tx.get("blockNumber", ""),
                "chain":     "ETH",
            }
            for tx in result
            if int(tx.get("value", 0)) / 1e18 >= min_eth
        ]

    # ----------------------------------------------------------------
    # Gas Price
    # ----------------------------------------------------------------
    def get_eth_gas_price(self):
        """Get current ETH gas prices."""
        ok, result, _ = self._etherscan(ETH_CHAIN_ID, "gastracker", "gasoracle", {})
        if ok and isinstance(result, dict):
            return {
                "safe":     float(result.get("SafeGasPrice", 0)),
                "standard": float(result.get("ProposeGasPrice", 0)),
                "fast":     float(result.get("FastGasPrice", 0)),
            }
        return {"safe": 0, "standard": 0, "fast": 0}

    # ----------------------------------------------------------------
    # Block Numbers
    # ----------------------------------------------------------------
    def get_eth_latest_block(self):
        """Get latest Ethereum block number."""
        ok, result, _ = self._etherscan(ETH_CHAIN_ID, "proxy", "eth_blockNumber", {})
        if result and isinstance(result, str) and result.startswith("0x"):
            return int(result, 16)
        return 0

    def get_bsc_latest_block(self):
        """Get latest BSC block number via public RPC."""
        result = self._bsc_rpc("eth_blockNumber", [])
        return int(result, 16) if result else 0

    # ----------------------------------------------------------------
    # Exchange Flow Analysis
    # ----------------------------------------------------------------
    def analyze_exchange_flows(self, symbol):
        """
        تحليل التدفقات من/إلى البورصات
        Exchange Inflow  = ضغط بيع قادم = إشارة هبوط
        Exchange Outflow = تخزين طويل   = إشارة صعود
        """
        cache_key = f"flow_{symbol}"
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]

        inflow_count  = 0
        outflow_count = 0
        inflow_usd    = 0
        outflow_usd   = 0

        # Analyze USDT flows on Ethereum as proxy
        eth_exchanges = {k: v for k, v in KNOWN_EXCHANGES.items() if "BSC" not in v}
        for addr in list(eth_exchanges.keys())[:3]:
            transfers = self.get_eth_token_transfers(addr, "USDT", limit=10)
            for tx in transfers:
                val = tx["value"]
                if val < EXCHANGE_INFLOW_USD:
                    continue
                if tx["to"].lower() == addr.lower():
                    inflow_count += 1
                    inflow_usd   += val
                else:
                    outflow_count += 1
                    outflow_usd   += val

        if inflow_usd > outflow_usd * 2 and inflow_count >= 2:
            signal = "BEARISH"
            reason = f"تدفق كبير للبورصات (${inflow_usd/1e6:.1f}M) = ضغط بيع قادم"
        elif outflow_usd > inflow_usd * 2 and outflow_count >= 2:
            signal = "BULLISH"
            reason = f"خروج كبير من البورصات (${outflow_usd/1e6:.1f}M) = تخزين طويل"
        else:
            signal = "NEUTRAL"
            reason = "تدفق متوازن"

        result = {
            "signal":      signal,
            "reason":      reason,
            "inflow_usd":  inflow_usd,
            "outflow_usd": outflow_usd,
        }
        self._set_cache(cache_key, result)
        return result

    # ----------------------------------------------------------------
    # Whale Sentiment
    # ----------------------------------------------------------------
    def get_whale_sentiment(self, symbol):
        """تحليل مشاعر الحيتان بناءً على بيانات On-Chain — خاص بكل عملة."""
        cache_key = f"sentiment_{symbol}"
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]
        score = 0
        bullish_signals = []
        bearish_signals = []
        # استخراج اسم العملة الأساسية
        base = symbol.replace("/USDT", "").replace("/USDC", "").replace("-USDT", "").replace("-USDC", "").upper()
        # فحص ETH فقط لعملات الـ ETH ecosystem
        if base in ("ETH", "WETH", "STETH"):
            binance_eth = self.get_eth_balance("0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE")
            if binance_eth > 1000:
                bearish_signals.append(f"Binance يحتفظ بـ {binance_eth:,.0f} ETH (ضغط بيع محتمل)")
                score -= 1
            elif binance_eth < 500:
                bullish_signals.append(f"Binance ETH holdings منخفضة ({binance_eth:,.0f}) = ضغط بيع منخفض")
                score += 1
        # فحص BNB فقط لعملات الـ BSC ecosystem
        elif base in ("BNB", "WBNB", "CAKE"):
            binance_bnb = self.get_bnb_balance("0x8894e0a0c962cb723c1976a4421c95949be2d4e3")
            if binance_bnb > 100000:
                bullish_signals.append(f"Binance BSC يحتفظ بـ {binance_bnb:,.0f} BNB (احتياطي قوي)")
                score += 1
            elif binance_bnb < 50000:
                bearish_signals.append(f"Binance BSC holdings منخفضة ({binance_bnb:,.0f} BNB)")
                score -= 1
        else:
            # للعملات الأخرى: تحليل تدفق USDT كمؤشر سيولة عام
            try:
                flow_data = self.analyze_exchange_flows(symbol)
                if flow_data["signal"] == "BULLISH":
                    bullish_signals.append(f"تدفق سيولة إيجابي لـ {base}: {flow_data['reason']}")
                    score += 1
                elif flow_data["signal"] == "BEARISH":
                    bearish_signals.append(f"تدفق سيولة سلبي لـ {base}: {flow_data['reason']}")
                    score -= 1
                else:
                    bullish_signals.append(f"تدفق {base} متوازن — لا ضغط بيع")
            except Exception:
                pass
        result = {
            "score":           score,
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals,
            "sentiment":       "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL",
        }
        self._set_cache(cache_key, result)
        return result

    def detect_smart_money_accumulation(self, symbol):
        """اكتشاف تراكم الأموال الذكية قبل الارتفاع."""
        cache_key = f"accumulation_{symbol}"
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]

        accumulation_count = 0
        distribution_count = 0
        total_accumulated_usd = 0

        eth_exchanges = {k: v for k, v in KNOWN_EXCHANGES.items() if "BSC" not in v}
        for addr in list(eth_exchanges.keys())[:2]:
            transfers = self.get_eth_token_transfers(addr, "USDT", limit=20)
            for tx in transfers:
                val = tx["value"]
                if val < 100_000:
                    continue
                if tx["from"].lower() == addr.lower():
                    accumulation_count    += 1
                    total_accumulated_usd += val
                else:
                    distribution_count += 1

        total_txs = accumulation_count + distribution_count
        if total_txs == 0:
            result = {"signal": "NEUTRAL", "confidence": 0,
                      "accumulation_count": 0, "distribution_count": 0,
                      "total_accumulated_usd": 0}
        else:
            ratio = accumulation_count / total_txs
            if ratio > 0.7 and accumulation_count >= 3:
                signal     = "STRONG_ACCUMULATION"
                confidence = min(ratio * 100, 95)
            elif ratio > 0.5:
                signal     = "MILD_ACCUMULATION"
                confidence = ratio * 80
            elif ratio < 0.3 and distribution_count >= 3:
                signal     = "DISTRIBUTION"
                confidence = (1 - ratio) * 80
            else:
                signal     = "NEUTRAL"
                confidence = 50
            result = {
                "signal":                signal,
                "confidence":            confidence,
                "accumulation_count":    accumulation_count,
                "distribution_count":    distribution_count,
                "total_accumulated_usd": total_accumulated_usd,
            }

        self._set_cache(cache_key, result)
        return result

    # ----------------------------------------------------------------
    # Whale Alert (optional)
    # ----------------------------------------------------------------
    def get_recent_whale_transactions(self, min_usd=500_000, limit=20):
        """Get recent large transactions from Whale Alert API (optional)."""
        if self.whale_alert_key == "YourWhaleAlertKey":
            return []
        try:
            r = requests.get(
                "https://api.whale-alert.io/v1/transactions",
                params={"api_key": self.whale_alert_key, "min_value": min_usd,
                        "limit": limit, "start": int(time.time()) - 3600},
                timeout=5,
            )
            data = r.json()
            if data.get("result") == "success":
                return data.get("transactions", [])
        except Exception as e:
            logger.error(f"Whale Alert API error: {e}")
        return []

    # ----------------------------------------------------------------
    # Full On-Chain Analysis
    # ----------------------------------------------------------------
    def full_onchain_analysis(self, symbol):
        """
        تحليل On-Chain شامل يدمج Etherscan v2 + BSC RPC
        Returns: score (-10 to +10) and detailed signals
        """
        # Cache result for 15 minutes to avoid repeated slow API calls
        cache_key = f'full_onchain_{symbol}'
        if self._is_cached(cache_key):
            return self.cache[cache_key]['data']
        score   = 0
        signals = []

        flow = self.analyze_exchange_flows(symbol)
        if flow["signal"] == "BULLISH":
            score += 3
            signals.append(f"تدفق إيجابي: {flow['reason']}")
        elif flow["signal"] == "BEARISH":
            score -= 3
            signals.append(f"تدفق سلبي: {flow['reason']}")

        sentiment = self.get_whale_sentiment(symbol)
        score += sentiment["score"]
        signals.extend(sentiment["bullish_signals"][:2])
        signals.extend(sentiment["bearish_signals"][:2])

        accumulation = self.detect_smart_money_accumulation(symbol)
        if accumulation["signal"] == "STRONG_ACCUMULATION":
            score += 4
            signals.append(f"تراكم قوي للأموال الذكية (ثقة: {accumulation['confidence']:.0f}%)")
        elif accumulation["signal"] == "MILD_ACCUMULATION":
            score += 2
            signals.append("تراكم خفيف للأموال الذكية")
        elif accumulation["signal"] == "DISTRIBUTION":
            score -= 3
            signals.append("توزيع — الحيتان تبيع")

        if score >= 5:
            onchain_signal = "STRONG_BUY"
        elif score >= 3:
            onchain_signal = "BUY"
        elif score <= -4:
            onchain_signal = "STRONG_SELL"
        elif score <= -2:
            onchain_signal = "SELL"
        else:
            onchain_signal = "NEUTRAL"

        logger.info(f"On-Chain Analysis for {symbol}: {onchain_signal} (score: {score})")
        result = {
            "signal":       onchain_signal,
            "score":        score,
            "signals":      signals,
            "flow":         flow,
            "sentiment":    sentiment,
            "accumulation": accumulation,
        }
        self._set_cache(cache_key, result)
        return result

    # ----------------------------------------------------------------
    # Test Connection
    # ----------------------------------------------------------------
    def test_connection(self):
        """Test all API connections and return status dict."""
        results = {}

        # Etherscan v2 - ETH
        ok, result, msg = self._etherscan(ETH_CHAIN_ID, "account", "balance", {
            "address": "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE", "tag": "latest"
        })
        results["etherscan_v2_eth"] = ok
        if ok:
            eth = int(result) / 1e18
            results["binance_eth"] = f"{eth:.4f} ETH"
            logger.info(f"✅ Etherscan v2 ETH: OK | Binance: {eth:.4f} ETH")
        else:
            logger.warning(f"❌ Etherscan v2 ETH: {msg}")

        # BSC Public RPC
        bnb = self.get_bnb_balance("0x8894e0a0c962cb723c1976a4421c95949be2d4e3")
        results["bsc_rpc"] = bnb > 0
        if bnb > 0:
            results["binance_bnb"] = f"{bnb:,.0f} BNB"
            logger.info(f"✅ BSC RPC: OK | Binance: {bnb:,.0f} BNB")
        else:
            logger.warning("❌ BSC RPC: Failed")

        # ETH Gas
        gas = self.get_eth_gas_price()
        results["eth_gas"] = gas["safe"] > 0
        if gas["safe"] > 0:
            results["gas_gwei"] = f"{gas['safe']:.3f} Gwei"
            logger.info(f"✅ ETH Gas: {gas['safe']:.3f} Gwei")

        # Block numbers
        eth_block = self.get_eth_latest_block()
        bsc_block = self.get_bsc_latest_block()
        results["eth_block"] = eth_block
        results["bsc_block"] = bsc_block
        if eth_block:
            logger.info(f"✅ ETH Block: {eth_block:,}")
        if bsc_block:
            logger.info(f"✅ BSC Block: {bsc_block:,}")

        return results

    # ----------------------------------------------------------------
    # Cache Helpers
    # ----------------------------------------------------------------
    def _is_cached(self, key):
        if key in self.cache:
            if time.time() - self.cache[key]["time"] < self.cache_ttl:
                return True
        return False

    def _set_cache(self, key, data):
        self.cache[key] = {"data": data, "time": time.time()}
