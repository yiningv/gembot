import requests
import json
import time
import os
from datetime import datetime
import schedule
from typing import Dict, List, Tuple, Optional


class BinanceFundingRateTracker:
    def __init__(self, data_file="funding_rates_stats.json"):
        self.data_file = data_file
        self.previous_rates = {}  # 用于缓存上一次的费率
        self.current_rates = {}  # 当前费率

        # 如果文件存在，加载之前的数据
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    if 'previous_rates' in data:
                        self.previous_rates = data['previous_rates']
            except Exception as e:
                print(f"Error loading previous data: {e}")

    def get_usdt_perpetual_symbols(self) -> List[str]:
        """获取所有USDT结尾的永续合约交易对"""
        try:
            response = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo")
            data = response.json()

            usdt_symbols = []
            for symbol_info in data['symbols']:
                if symbol_info['symbol'].endswith('USDT') and symbol_info['status'] == 'TRADING' and symbol_info[
                    'contractType'] == 'PERPETUAL':
                    usdt_symbols.append(symbol_info['symbol'])

            return usdt_symbols
        except Exception as e:
            print(f"Error fetching symbols: {e}")
            return []

    def get_funding_rates(self) -> Dict[str, float]:
        """获取所有USDT交易对的资金费率"""
        try:
            response = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex")
            data = response.json()

            funding_rates = {}
            for item in data:
                symbol = item['symbol']
                if symbol.endswith('USDT'):
                    funding_rate = float(item['lastFundingRate'])
                    funding_rates[symbol] = funding_rate

            return funding_rates
        except Exception as e:
            print(f"Error fetching funding rates: {e}")
            return {}

    def get_top_n(self, rates: Dict[str, float], n: int, reverse: bool = True) -> List[Tuple[str, float]]:
        """获取费率最高/最低的n个交易对"""
        sorted_rates = sorted(rates.items(), key=lambda x: x[1], reverse=reverse)
        return sorted_rates[:n]

    def get_biggest_changes(self, current: Dict[str, float], previous: Dict[str, float], n: int,
                            increasing: bool = True) -> List[Tuple[str, float]]:
        """获取费率变化最大的n个交易对"""
        changes = {}
        for symbol, rate in current.items():
            if symbol in previous:
                change = rate - previous[symbol]
                if (increasing and change > 0) or (not increasing and change < 0):
                    changes[symbol] = change

        sorted_changes = sorted(changes.items(), key=lambda x: x[1], reverse=increasing)
        return sorted_changes[:n]

    def run_task(self):
        """执行主要任务"""
        print(f"Running task at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 获取当前所有USDT交易对的资金费率
        self.current_rates = self.get_funding_rates()

        if not self.current_rates:
            print("Failed to get funding rates, skipping this run")
            return

        # 统计1: 费率最高的5个symbol
        highest_rates = self.get_top_n(self.current_rates, 5, reverse=True)

        # 统计2: 费率最低的5个symbol
        lowest_rates = self.get_top_n(self.current_rates, 5, reverse=False)

        # 统计3 & 4: 费率变化最大的交易对
        increasing_rates = []
        decreasing_rates = []

        if self.previous_rates:
            # 统计3: 费率上升最大的5个symbol
            increasing_rates = self.get_biggest_changes(self.current_rates, self.previous_rates, 5, increasing=True)

            # 统计4: 费率下降最大的5个symbol
            decreasing_rates = self.get_biggest_changes(self.current_rates, self.previous_rates, 5, increasing=False)

        # 准备保存的数据
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        stats = {
            "timestamp": timestamp,
            "highest_rates": [{"symbol": s, "rate": r} for s, r in highest_rates],
            "lowest_rates": [{"symbol": s, "rate": r} for s, r in lowest_rates],
            "biggest_increases": [{"symbol": s, "change": c} for s, c in increasing_rates],
            "biggest_decreases": [{"symbol": s, "change": c} for s, c in decreasing_rates],
            "previous_rates": self.current_rates  # 保存当前费率作为下次比较的基准
        }

        # 保存到JSON文件
        try:
            with open(self.data_file, 'w') as f:
                json.dump(stats, f, indent=4)
            print(f"Data saved to {self.data_file}")
        except Exception as e:
            print(f"Error saving data: {e}")

        # 更新previous_rates为当前rates，以便下次比较
        self.previous_rates = self.current_rates.copy()

        # 打印结果
        print("\n===== Funding Rate Statistics =====")
        print("\nHighest Funding Rates:")
        for symbol, rate in highest_rates:
            print(f"{symbol}: {rate:.6f}")

        print("\nLowest Funding Rates:")
        for symbol, rate in lowest_rates:
            print(f"{symbol}: {rate:.6f}")

        if increasing_rates:
            print("\nBiggest Increases:")
            for symbol, change in increasing_rates:
                print(f"{symbol}: +{change:.6f}")

        if decreasing_rates:
            print("\nBiggest Decreases:")
            for symbol, change in decreasing_rates:
                print(f"{symbol}: {change:.6f}")

        print("\n================================\n")


def run_scheduler():
    tracker = BinanceFundingRateTracker()

    # 立即运行一次
    tracker.run_task()

    # 每5分钟运行一次
    schedule.every(5).minutes.do(tracker.run_task)

    print("Funding rate tracker started. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Tracker stopped by user.")

