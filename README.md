# TradingView Scraper

## Overview

The TradingView Scraper is a tool designed for extracting historical market data from TradingView. It leverages asynchronous programming to efficiently fetch historical candlestick data for various symbols across multiple exchanges. The scraper supports a range of time intervals and can handle both authentication and non-authenticated access, providing flexibility for data access.

## Features

- **Flexible Time Intervals**: Supports various intervals from 1 minute to monthly, catering to different analysis needs.
- **Authentication Support**: Optional login for accessing premium data.
- **Database Integration**: Includes functionality for saving fetched data into a PostgreSQL database, with support for both development and production environments.
- **Asynchronous Fetching**: Utilizes asynchronous programming for efficient data retrieval and database operations.
- **Multi-Ticker Support**: Capable of fetching data for multiple tickers simultaneously, optimizing the data collection process.
- **Customizable Queries**: Offers the ability to customize queries based on symbol, exchange, interval, and more.

## Prerequisites

Before using the TradingView Scraper, ensure you have the following installed:

- Python 3.11
- `pandas`, `websocket-client`, `matplotlib`, `requests`, `websockets`, `python-dotenv`, `asyncpg`, `aiohttp`, libraries
- PostgreSQL database
- Docker (optional, for running a local database instance)

## Quick Start

1. **Set up a PostgreSQL Database**: You can use Docker for a quick LOCAL setup:

```bash
docker run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=password123! timescale/timescaledb:latest-pg14
```

2. **Environment Configuration**: Add the following credentials to your `.env` file:

```.env
DEV_DB_USER="postgres"
DEV_DB_HOST="localhost"
DEV_DB_PASS="password123!"
DEV_DB_NAME="postgres"
DEV_PORT="5432"
TV_USERNAME="<YourTradingViewUsername>"
TV_PASSWORD="<YourTradingViewPassword>"
```

3. **Database Schema**: Execute the following SQL commands to create the required table:

```sql
CREATE TABLE candles_tv (
    dt TIMESTAMP NOT NULL,
    symbol VARCHAR(255) NOT NULL,
    exchange VARCHAR(255) NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    PRIMARY KEY (dt, symbol, exchange)
);

CREATE INDEX ON candles_tv (dt DESC, symbol, exchange);
SELECT create_hypertable('candles_tv', 'dt');
```

4. As a demo, to scrape the historical minute candles for the top 100 Market Cap Cryptocurrencies, run the following command:

```bash
python app/main.py
```

The scraper will fetch the data and save it to the PostgreSQL database. You can monitor the progress in the terminal:

![Terminal](/img/terminal.png)

5. As a result, you will see the historical minute candles for the top 100 Market Cap Cryptocurrencies in the `candles_tv` table in the database:

![Candle Data in PostgreSQL](/img/image.png)

## Usage

1. **Initialize the Scraper**: Create an instance of `TradingViewScraper` with optional TradingView credentials for logged-in access.

   ```python
   from dotenv import load_dotenv
   import asyncio

   load_dotenv()

   tv = TradingViewScraper(username=os.getenv("TV_USERNAME"), password=os.getenv("TV_PASSWORD"), db_type="prod")
   ```

2. **Fetch Historical Data**: Use the `get_historical_df` or `get_historical_data` methods to fetch historical market data.

   ```python
   data = await tv.get_historical_df(symbol="AAPL", exchange="NASDAQ", interval=Interval.in_1_minute, n_bars=100)
   print(data)
   ```

3. **Save Data to Database**: Use the `save_historical_db` method to save fetched data directly to the PostgreSQL database.

   ```python
   await tv.save_historical_db(symbol="AAPL", exchange="NASDAQ", interval=Interval.in_1_minute, n_bars=100)
   ```

4. **Handling Multiple Tickers**: The scraper allows fetching and saving data for multiple tickers concurrently.

   ```python
   tickers = [("AAPL", "NASDAQ"), ("GOOGL", "NASDAQ")]
   await tv.save_multiple_tickers(tickers)
   ```

## Customization

- **Database Configuration**: Modify the `db_type` parameter when initializing the scraper to switch between development (`dev`) and production (`prod`) databases.
- **Session Customization**: Adjust `ws_timeout` and `ws_debug` attributes to customize WebSocket connection behavior.
- **Symbol Formatting**: Use the `__format_symbol` method to format symbols correctly for different exchanges and contract types.
