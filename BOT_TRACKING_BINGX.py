import sys
import json
import pandas as pd

from time import sleep
from core.engine.bingx import BingXEngine

from utils.logger import print_log, save_json_locally


class BotTrackingBingX:
    def __init__(self, api_key, api_secret, path):
        self.client = BingXEngine(api_key, api_secret, True)
        self.params = pd.read_excel(path)
        try:
            with open('data/tracking_data.json', 'r') as f:
                self.tracking_data = json.load(f)
        except:
            self.tracking_data = {}

    def check_roe(self, position):
        symbol = position['symbol']
        position_id = position['positionId']
        position_side = position['positionSide']
        
        if position_side == 'LONG':
            side_weight = 1
            dca_side = 'BUY'
            close_side = 'SELL'
        elif position_side == 'SHORT':
            side_weight = -1
            dca_side = 'SELL'
            close_side = 'BUY'

        leverage = float(position['leverage'])
        quantity = float(position['positionAmt'])
        # mark_price = float(position['markPrice'])
        entry_price = float(position['avgPrice'])

        if entry_price == 0: return

        try:
            lastest_price = float(self.client.latest_price(symbol)['price'])
        except Exception as e:
            print_log(f"Error getting latest price of {symbol}: {e}")

        # roe_v1  = side_weight * (mark_price / entry_price - 1) * leverage * 100
        roe_v2  = side_weight * (lastest_price / entry_price - 1) * leverage * 100
        
        # min_roe = min(roe_v1, roe_v2)
        # max_roe = max(roe_v1, roe_v2)

        min_roe = roe_v2
        max_roe = roe_v2

        for i, row in self.params.iterrows():
            if str(i) in self.tracking_data[position_id]['trackingData']: continue

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

            if order_type == 'TP':
                order_params = {
                    'symbol': symbol,
                    'type': 'LIMIT',
                    'side': close_side,
                    'positionSide': position_side,
                    'price': (side_weight * roe / leverage / 100 + 1) * entry_price,
                    'quantity': new_quantity,
                    'stopPrice': None,
                }
            elif order_type == 'SL':
                stop_price = (-side_weight * roe / leverage / 100 + 1) * entry_price
                stop_roe = side_weight * (stop_price / lastest_price - 1) * leverage * 100
                order_params = {
                    'symbol': symbol,
                    'type': 'STOP_MARKET' if stop_roe < 0 else 'TAKE_PROFIT_MARKET',
                    'side': close_side,
                    'positionSide': position_side,
                    'quantity': new_quantity,
                    'stopPrice': stop_price,
                }
            elif order_type == 'CLOSE':
                order_params = {
                    'symbol': symbol,
                    'type': 'MARKET',
                    'side': close_side,
                    'positionSide': position_side,
                    'quantity': new_quantity,
                }
            elif order_type == 'DCA':
                order_params = {
                    'symbol': symbol,
                    'type': 'MARKET',
                    'side': dca_side,
                    'positionSide': position_side,
                    'quantity': new_quantity,
                }
            
            print_log(f"ROE {operator} {value}")
            for _ in range(3):
                try:
                    if order_type in ['TP', 'SL', 'CLOSE', 'DCA']:
                        order = self.client.futures_create_order_freestyle(order_params)['order']
                        print_log(f"Success: orderId = {order['orderId']}")
                        print_log("-----")
                        self.tracking_data[position_id]['trackingData'][str(i)] = order['orderId']
                    elif order_type == 'CANCEL':
                        _index = str(row['Quantity'])
                        _orderIdList = [self.tracking_data[position_id]['trackingData'][_index]]
                        response = self.client.cancel_orders(symbol, _orderIdList)
                        print(response)
                        print_log(f"Success: canceled {_orderIdList}")
                        print_log("-----")
                        self.tracking_data[position_id]['trackingData'][str(i)] = True
                    break
                except Exception as e:
                    print_log(f"Error ordering open order: {e}")
                    print_log(order_params)
                    print_log("-----")
                    sleep(1)


    def interval_fn(self):
        try:
            list_open_position = self.client.futures_position_information(symbol='')
        except Exception as e:
            print_log(f"Error getting open positions: {e}")
            return
        
        list_prev_position_id = list(self.tracking_data.keys())
        list_curr_position_id = [p['positionId'] for p in list_open_position]

        list_closed_position_id = list(set(list_prev_position_id) - set(list_curr_position_id))
        list_opened_position_id = list(set(list_curr_position_id) - set(list_prev_position_id))

        for position_id in list_opened_position_id:
            print_log(f"Opened: {position_id}")
            pos = [p for p in list_open_position if p['positionId'] == position_id][0]
            self.tracking_data[pos['positionId']] = pos
            self.tracking_data[pos['positionId']]['trackingData'] = {}

        for position_id in list_closed_position_id:
            print_log(f"Closed: {position_id}")
            symbol = self.tracking_data[position_id]['symbol']
            try:
                self.client.cancel_all_orders(symbol)
                del self.tracking_data[position_id]
            except Exception as e:
                print_log(f"Error cancelling open orders: {e}")

        for pos in list_open_position: self.check_roe(pos)

    def run_until_disconnected(self):
        counter = 0
        while True:
            try:
                self.interval_fn()
                counter += 1
                if counter % 10 == 0:
                    save_json_locally('data/tracking_data.json', self.tracking_data)
                sleep(2)
            except KeyboardInterrupt:
                sys.exit()
            except Exception as e:
                print(e)
                pass
    