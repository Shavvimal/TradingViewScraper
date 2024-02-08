from TradingViewScraper import TradingViewScraper
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()


# logging.basicConfig(level=logging.DEBUG)

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
