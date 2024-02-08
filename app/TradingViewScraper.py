import datetime
import enum
import logging
import random
import re
import string
import pandas as pd
import websockets
import requests
import json
import asyncpg
import os
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class Interval(enum.Enum):
    in_1_minute = "1"
    in_3_minute = "3"
    in_5_minute = "5"
    in_15_minute = "15"
    in_30_minute = "30"
    in_45_minute = "45"
    in_1_hour = "1H"
    in_2_hour = "2H"
    in_3_hour = "3H"
    in_4_hour = "4H"
    in_daily = "1D"
    in_weekly = "1W"
    in_monthly = "1M"


class TradingViewScraper:
    def __init__(
            self,
            username: str = None,
            password: str = None,
            db_type: str = "dev"
    ) -> None:
        self.ws_timeout = 5
        self.ws_debug = False
        self.token = self.__auth(username, password)

        if self.token is None:
            self.token = "unauthorized_user_token"
            logger.warning(
                "you are using nologin method, data you access may be limited"
            )

        self.session = self.__generate_session()
        self.chart_session = self.__generate_chart_session()

        if db_type == 'dev':
            self._DB_CONN_INFO = {
                'user': os.getenv('DEV_DB_USER'),
                'password': os.getenv('DEV_DB_PASS'),
                'host': os.getenv('DEV_DB_HOST'),
                'database': os.getenv('DEV_DB_NAME'),
                'port': os.getenv('DEV_PORT', default=5432)
            }
        elif db_type == 'prod':
            self._DB_CONN_INFO = {
                'user': os.getenv('PROD_DB_USER'),
                'password': os.getenv('PROD_DB_PASS'),
                'host': os.getenv('PROD_DB_HOST'),
                'database': os.getenv('PROD_DB_NAME'),
                'port': os.getenv('PROD_PORT', default=5432)
            }
        else:
            print('incorrect db_type')

        self.pool = None

    async def setup_pool(self):
        self.pool = await asyncpg.create_pool(**self._DB_CONN_INFO)

    async def close_pool(self):
        if self.pool:
            await self.pool.close()

    def __auth(self, username, password):
        if username is None or password is None:
            token = None

        else:
            sign_in_url = 'https://www.tradingview.com/accounts/signin/'
            data = {"username": username, "password": password, "remember": "on"}
            headers = {'Referer': 'https://www.tradingview.com'}
            try:
                response = requests.post(url=sign_in_url, data=data, headers=headers)
                json_resp = response.json()
                print(json_resp)
                token = json_resp['user']['auth_token']
            except Exception as e:
                logger.error('error while signin')
                token = None
        return token

    @staticmethod
    def __filter_raw_message(text):
        try:
            found = re.search('"m":"(.+?)",', text).group(1)
            found2 = re.search('"p":(.+?"}"])}', text).group(1)

            return found, found2
        except AttributeError:
            logger.error("error in filter_raw_message")

    @staticmethod
    def __generate_session():
        stringLength = 12
        letters = string.ascii_lowercase
        random_string = "".join(random.choice(letters)
                                for i in range(stringLength))
        return "qs_" + random_string

    @staticmethod
    def __generate_chart_session():
        stringLength = 12
        letters = string.ascii_lowercase
        random_string = "".join(random.choice(letters)
                                for i in range(stringLength))
        return "cs_" + random_string

    @staticmethod
    def __prepend_header(st):
        return "~m~" + str(len(st)) + "~m~" + st

    @staticmethod
    def __construct_message(func, param_list):
        return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

    def __create_message(self, func, paramList):
        return self.__prepend_header(self.__construct_message(func, paramList))

    async def __send_message(self, func, args, ws):
        m = self.__create_message(func, args)
        if self.ws_debug:
            print(m)
        await ws.send(m)

    @staticmethod
    def __parse_raw_data(raw_data) -> list:
        try:
            out = re.search('"s":\[(.+?)\}\]', raw_data).group(1)
            x = out.split(',{"')
            data = list()
            volume_data = True

            for xi in x:
                xi = re.split("\[|:|,|\]", xi)
                ts = datetime.datetime.fromtimestamp(float(xi[4]))

                row = [ts]

                for i in range(5, 10):

                    # skip converting volume data if does not exists
                    if not volume_data and i == 9:
                        row.append(0.0)
                        continue
                    try:
                        row.append(float(xi[i]))

                    except ValueError:
                        volume_data = False
                        row.append(0.0)
                        logger.debug('no volume data')

                data.append(row)
            return data
        except AttributeError:
            logger.error("Error Parsing Data")

    def __create_df(self, data, symbol):
        try:

            data = pd.DataFrame(
                data, columns=["datetime", "open",
                               "high", "low", "close", "volume"]
            ).set_index("datetime")
            data.insert(0, "symbol", value=symbol)
            return data
        except AttributeError:
            logger.error("no data, please check the exchange and symbol")

    async def __insert_candles_db(self, data: list, symbol: str):
        """
        Inserts list of data into the "Candles" table. On Conflicts, it skips.
        Each row in the data list should be in the format:
        [datetime, open, high, low, close, volume]
        """
        if self.pool is None:
            await self.setup_pool()
        # Add the symbol to each row of data
        # Convert numerical values to string, in a weird way theyre acc more accurate
        # than the number actually stored in memory.

        # split symbol using ":"
        exchange, symbol_ticker = symbol.split(":")
        records = [
            (
                symbol_ticker,
                exchange,
                row[0],  # datetime
                *[str(val) for val in row[1:]]  # open, high, low, close, volume
            )
            for row in data
        ]

        column_names = "symbol, exchange, dt, open, high, low, close, volume"

        placeholders = ', '.join(f'${i + 1}' for i in range(8))
        query = f"""
            INSERT INTO candles_tv ({column_names})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING;
        """

        # Using a connection from the pool to execute multiple insertions
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.executemany(query, records)

    @staticmethod
    def __format_symbol(symbol, exchange, contract: int = None):

        if ":" in symbol:
            pass
        elif contract is None:
            symbol = f"{exchange}:{symbol}"

        elif isinstance(contract, int):
            symbol = f"{exchange}:{symbol}{contract}!"

        else:
            raise ValueError("not a valid contract")

        return symbol

    async def get_historical_data(
            self,
            symbol: str,
            exchange: str = "NSE",
            interval: Interval = Interval.in_1_minute,
            n_bars: int = 5000,
            fut_contract: int = None,
            extended_session: bool = False,
    ) -> (list, str):
        """get historical data

              Args:
                  symbol (str): symbol name
                  exchange (str, optional): exchange, not required if symbol is in format EXCHANGE:SYMBOL. Defaults to None.
                  interval (str, optional): chart interval. Defaults to 'M'.
                  n_bars (int, optional): no of bars to download, max 5000. Defaults to 10.
                  fut_contract (int, optional): None for cash, 1 for continuous current contract in front, 2 for continuous next contract in front . Defaults to None.
                  extended_session (bool, optional): regular session if False, extended session if True, Defaults to False.

              Returns:
                  pd.Dataframe: dataframe with sohlcv as columns
              """
        symbol = self.__format_symbol(
            symbol=symbol, exchange=exchange, contract=fut_contract
        )
        interval = interval.value

        async with websockets.connect(
                "wss://data.tradingview.com/socket.io/websocket",
                extra_headers={"Origin": "https://data.tradingview.com"},
                ping_timeout=None,
                close_timeout=self.ws_timeout
        ) as websocket:

            await self.__send_message("set_auth_token", [self.token], websocket)
            await self.__send_message("chart_create_session", [self.chart_session, ""], websocket)
            await self.__send_message("quote_create_session", [self.session], websocket)
            await self.__send_message(
                "quote_set_fields",
                [
                    self.session,
                    "ch",
                    "chp",
                    "current_session",
                    "description",
                    "local_description",
                    "language",
                    "exchange",
                    "fractional",
                    "is_tradable",
                    "lp",
                    "lp_time",
                    "minmov",
                    "minmove2",
                    "original_name",
                    "pricescale",
                    "pro_name",
                    "short_name",
                    "type",
                    "update_mode",
                    "volume",
                    "currency_code",
                    "rchp",
                    "rtc",
                ], websocket
            )

            await self.__send_message(
                "quote_add_symbols", [self.session, symbol,
                                      {"flags": ["force_permission"]}], websocket
            )
            await self.__send_message("quote_fast_symbols", [self.session, symbol], websocket)

            await self.__send_message(
                "resolve_symbol",
                [
                    self.chart_session,
                    "symbol_1",
                    '={"symbol":"'
                    + symbol
                    + '","adjustment":"splits","session":'
                    + ('"regular"' if not extended_session else '"extended"')
                    + "}",
                ], websocket
            )
            await self.__send_message(
                "create_series",
                [self.chart_session, "s1", "s1", "symbol_1", interval, n_bars], websocket
            )
            await self.__send_message("switch_timezone", [
                self.chart_session, "exchange"], websocket)

            raw_data = ""

            logger.debug(f"getting data for {symbol}...")
            while True:
                try:
                    result = await websocket.recv()
                    raw_data += result + "\n"
                    if "series_completed" in result:
                        break
                except Exception as e:
                    logger.error(e)
                    break

        data = self.__parse_raw_data(raw_data)
        return data, symbol

    async def get_historical_df(
            self,
            symbol: str,
            exchange: str = "NSE",
            interval: Interval = Interval.in_1_minute,
            n_bars: int = 10,
            fut_contract: int = None,
            extended_session: bool = False,
    ) -> pd.DataFrame:
        raw_data, symbol = await self.get_historical_data(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            n_bars=n_bars,
            fut_contract=fut_contract,
            extended_session=extended_session
        )
        return self.__create_df(raw_data, symbol)

    async def save_historical_db(
            self,
            symbol: str,
            exchange: str = "BINANCE",
            interval: Interval = Interval.in_1_minute,
            n_bars: int = 5000,
            fut_contract: int = None,
            extended_session: bool = False,
    ) -> None:
        try:
            raw_data, symbol = await self.get_historical_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                n_bars=n_bars,
                fut_contract=fut_contract,
                extended_session=extended_session
            )
            await self.__insert_candles_db(
                data=raw_data, symbol=symbol
            )
            print(f"SUCCESSFULLY SAVED {symbol}")
        except Exception as e:
            print(f"ERROR SAVING {symbol}/{exchange} due to {e}")


    async def fetch_multiple_tickers(datafeed, tickers):
        tasks = []
        for ticker in tickers:
            task = asyncio.create_task(datafeed.get_hist_async(*ticker))
            tasks.append(task)
        return await asyncio.gather(*tasks)

    @staticmethod
    async def search_symbol(text: str, exchange: str = ''):
        search_url = 'https://symbol-search.tradingview.com/symbol_search/?text={}&hl=1&exchange={}&lang=en&type=&domain=production'
        url = search_url.format(text, exchange)

        symbols_list = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp_text = await resp.text()
                    symbols_list = json.loads(resp_text.replace('</em>', '').replace('<em>', ''))
        except Exception as e:
            logger.error(e)
        return symbols_list

    async def fetch_and_filter(self, coin: str, quote: str):
        """
        Returns all spot from search
        """
        search_result = await self.search_symbol(f'{coin}{quote}')
        return [
            (x['symbol'], x['exchange']) for x in search_result
            if x['type'] == 'spot' and x['symbol'] == f'{coin}{quote}'
        ]

    async def fetch_symbol_exchange_tuples(self, coins, quote='USDT'):
        """
        Fetches all symbol and exchnges available on trading view through the search
        """
        # Create tasks for each coin search
        tasks = [self.fetch_and_filter(coin, quote) for coin in coins]
        # Gather all tasks to run concurrently
        results = await asyncio.gather(*tasks)
        # Flatten the list of lists into a single list of tuples
        symbol_exchange_tuples = [item for sublist in results for item in sublist]
        return symbol_exchange_tuples

    async def save_multiple_tickers(self, tickers, delay_time=1):
        tasks = []
        for ticker in tickers:
            task = asyncio.create_task(self.save_historical_db(*ticker))
            tasks.append(task)
            # Manually add a sleep time to prevent Rate Limits
            await asyncio.sleep(delay_time)
        return await asyncio.gather(*tasks)

        # Sequential
        # for ticker in tickers:
        #     await self.save_historical_db(*ticker)



if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(level=logging.DEBUG)

    async def main():
        username = os.getenv("TV_USERNAME")
        password = os.getenv("TV_PASSWORD")
        tv = TradingViewScraper(username=username, password=password, db_type="prod")
        coins_100_market_cap = [
                                "BTC",
                                "ETH",
                                "USDT",
                                "BNB",
                                "SOL",
                                "XRP",
                                "USDC",
                                "ADA",
                                "AVAX",
                                "DOGE",
                                "TRX",
                                "DOT",
                                "LINK",
                                "TON",
                                "MATIC",
                                "DAI",
                                "SHIB",
                                "ICP",
                                "LTC",
                                "BCH",
                                "LEO",
                                "ATOM",
                                "UNI",
                                "ETC",
                                "XLM",
                                "INJ",
                                "APT",
                                "OKB",
                                "XMR",
                                "OP",
                                "FDUSD",
                                "NEAR",
                                "TIA",
                                "LDO",
                                "FIL",
                                "IMX",
                                "HBAR",
                                "KAS",
                                "ARB",
                                "STX",
                                "CRO",
                                "VET",
                                "MNT",
                                "MKR",
                                "TUSD",
                                "SEI",
                                "RNDR",
                                "GRT",
                                "BSV",
                                "SUI",
                                "RUNE",
                                "ALGO",
                                "EGLD",
                                "AAVE",
                                "QNT",
                                "ORDI",
                                "FLOW",
                                "HNT",
                                "MINA",
                                "SAND",
                                "AXS",
                                "SNX",
                                "KCS",
                                "THETA",
                                "FTM",
                                "ASTR",
                                "XTZ",
                                "1000SATS",
                                "BEAM",
                                "FTT",
                                "CHZ",
                                "WEMIX",
                                "MANA",
                                "BGB",
                                "BLUR",
                                "ETHDYDX",
                                "BTT",
                                "EOS",
                                "FXS",
                                "KAVA",
                                "NEO",
                                "MANTA",
                                "OSMO",
                                "USDD",
                                "FLR",
                                "IOTA",
                                "BONK",
                                "RON",
                                "SC",
                                "KLAY",
                                "CFX",
                                "ROSE",
                                "WOO",
                                "XDC",
                                "GALA",
                                "CAKE",
                                "AKT",
                                "XEC",
                                "RPL",
                                "AR", ]
        symbol_ex_tuples = await tv.fetch_symbol_exchange_tuples(coins_100_market_cap)
        print(symbol_ex_tuples)
        # Save to DB
        await tv.save_multiple_tickers(symbol_ex_tuples)


    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
