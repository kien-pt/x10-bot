import sys
import json

from time import sleep
from core.engine.bingx import BingXEngine

from utils.logger import print_log, save_json_locally

class BingXTrackingBot:
    def __init__(self, api_key, api_secret):
        self.client = BingXEngine(api_key, api_secret, True)
        self.tracking_data = {}

    def check_roe(self, position):
        symbol = position['symbol']
        position_id = position['positionId']
        position_side = position['positionSide']
        
        side_weight = { 'LONG': 1, 'SHORT': -1 }[position_side]
        close_side = { 1: 'SELL', -1: 'BUY' }[side_weight]

        leverage = float(position['leverage'])
        quantity = float(position['positionAmt']) * side_weight
        mark_price = float(position['markPrice'])
        entry_price = float(position['entryPrice'])

        lastest_price = self.client.latest_price(symbol)

        roe_v1  = side_weight * (mark_price / entry_price - 1) * leverage * 100
        roe_v2  = side_weight * (lastest_price / entry_price - 1) * leverage * 100
        
        min_roe = min(roe_v1, roe_v2)
        max_roe = max(roe_v1, roe_v2)

        for i, row in PARAMS.itterrows():
            if self.tracking_data[position_id]['trackingData'][i]: continue

            roe = row['ROE']
            value = row['Value']
            operator = row['Operator']
            order_type = row['OrderType']
            new_quantity = row['Quantity'] * quantity / 100

            checked = False
            if operator == '>=': checked = max_roe >= value
            elif operator == '>': checked = max_roe > value
            elif operator == '<': checked = min_roe < value
            elif operator == '<=': checked = min_roe <= value

            if not checked: continue

            order_params = {
                'TP': {
                    'symbol': symbol,
                    'type': 'LIMIT',
                    'side': close_side,
                    'positionSide': position_side,
                    'price': (side_weight * roe / leverage / 100 + 1) * entry_price,
                    'quantity': new_quantity,
                    'stopPrice': None,
                },
                'SL': {
                    'symbol': symbol,
                    'type': 'STOP_MARKET' if roe < 0 else 'TAKE_PROFIT_MARKET',
                    'side': close_side,
                    'positionSide': position_side,
                    'price': (-side_weight * roe / leverage / 100 + 1) * entry_price,
                    'quantity': new_quantity,
                    'stopPrice': None,
                },
                'CLOSE': {
                    'symbol': symbol,
                    'type': 'MARKET',
                    'side': close_side,
                    'positionSide': position_side,
                    'quantity': new_quantity,
                },
                'DCA': {
                    'symbol': symbol,
                    'type': 'MARKET',
                    'side': close_side,
                    'positionSide': position_side,
                    'quantity': new_quantity,
                }
            }

    def interval_fn(self):
        try:
            list_open_position = self.client.positions(symbol='')
        except Exception as e:
            print_log(f"Error getting open positions: {e}")
            return
        
        list_prev_position_id = list(self.tracking_data.keys())
        list_curr_position_id = [p['positionId'] for p in list_open_position]

        list_closed_position_id = list(set(list_prev_position_id) - set(list_curr_position_id))
        list_latest_position_id = list(set(list_curr_position_id) - set(list_prev_position_id))

        for position_id in list_latest_position_id:
            pos = [p for p in list_open_position if p['positionId'] == position_id][0]
            self.tracking_data[pos['positionId']] = pos
            self.tracking_data[pos['positionId']]['trackingData'] = {}

        for position_id in list_closed_position_id:
            symbol = self.tracking_data[position_id]['symbol']
            try:
                self.client.cancel_all_orders(symbol)
            except Exception as e:
                print_log(f"Error cancelling open orders: {e}")

        for pos in list_open_position: self.check_roe(pos)

    def run_until_disconnected(self):
        while True:
            try:
                self.interval_fn()
                sleep(2)
            except KeyboardInterrupt:
                sys.exit()
            except:
                raise
    

