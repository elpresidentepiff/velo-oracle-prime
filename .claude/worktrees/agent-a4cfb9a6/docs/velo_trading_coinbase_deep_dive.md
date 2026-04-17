# VÉLØ Trading Module: Coinbase Deep Dive
### A Production-Ready Technical Reference for Automated Crypto Day Trading

**Author:** Manus AI
**Date:** February 26, 2026
**Version:** 1.0

---

## Table of Contents

1. [Coinbase Agentic Wallets](#1-coinbase-agentic-wallets)
2. [Coinbase APIs for Trading](#2-coinbase-apis-for-trading)
3. [High-Frequency Trading Capabilities](#3-high-frequency-trading-hft-capabilities)
4. [Market Data and Manipulation Detection](#4-market-data--manipulation-detection)
5. [Trading Strategies for VÉLØ](#5-trading-strategies-for-vélø)
6. [VÉLØ Trading Module Architecture](#6-vélø-trading-module-architecture)
7. [Information Aggregation](#7-information-aggregation)
8. [Risk and Compliance](#8-risk-and-compliance)
9. [Setup Guide](#9-setup-guide)
10. [Cost Analysis](#10-cost-analysis)
11. [References](#11-references)

---

## 1. Coinbase Agentic Wallets

### What Are Agentic Wallets?

Coinbase launched **Agentic Wallets** on February 11, 2026 — the first wallet infrastructure built specifically for AI agents rather than human users [1]. The core premise is that the next generation of AI agents should not merely advise on financial decisions but execute them autonomously. Until now, agents hit a hard wall when money was involved: they could recommend a trade but could not execute it; they could identify a useful API but could not pay for it. Agentic Wallets remove that wall.

These are not simply embedded wallets adapted for agents. They are purpose-built infrastructure for autonomous financial operations, designed to run 24/7 without human approval at every decision point. An agent equipped with an Agentic Wallet can hold funds, send payments, trade tokens, earn yield, and pay for its own compute and API access — all without human intervention, subject to developer-configured guardrails [2].

### How They Work

Agentic Wallets are built on the **Coinbase Developer Platform (CDP)** and use **Multi-Party Computation (MPC)** cryptography combined with **Trusted Execution Environments (TEEs)**. This architecture means the agent's private keys are never exposed to the agent's own code, the LLM it runs on, or the developer's infrastructure. The keys exist only within Coinbase's secure enclave, and all signing operations occur inside that enclave [3].

Agents interact with their wallets through a curated library of **"skills"** — pre-built, audited modules for common financial operations. The available skills include `Authenticate`, `Fund`, `Send`, `Trade`, and `Earn`. These are accessible via the `coinbase/agentic-wallet-skills` repository and can be added to any agent in seconds. A command-line tool, `npx awal`, provides a streamlined interface for managing agent wallets from the terminal [1].

The underlying payment rail at the core of Agentic Wallets is the **x402 protocol** — a machine-to-machine payment standard that has already processed over 50 million transactions. x402 enables agents to pay for API access, compute resources, and other services programmatically without any human-in-the-loop approval step [1].

### Capabilities for AI Agents

The following table summarises the key capabilities that Agentic Wallets provide to an AI agent:

| Capability | Description |
| :--- | :--- |
| **Wallet Identity** | A standalone, self-custody wallet on the Base network, uniquely owned by the agent. |
| **Autonomous Spending** | The agent can send USDC and other tokens without human approval, within pre-set limits. |
| **Gasless Trading on Base** | Token swaps on Base are executed without requiring the agent to hold ETH for gas, ensuring uninterrupted 24/7 operation. |
| **Earning** | Agents can deploy idle capital into yield-generating protocols autonomously. |
| **Machine Payments (x402)** | The agent can pay for APIs, data streams, compute, and storage using the x402 protocol. |
| **Skill Extensibility** | New capabilities can be added to the agent by installing skills from the official repository. |
| **CDP Portal Monitoring** | All agent activity is logged and visible through the CDP Portal dashboard for human oversight. |

### Security Model — How Funds Are Protected

The security architecture of Agentic Wallets operates on four distinct layers, each providing a different form of protection:

**Key Isolation via TEEs.** Private keys are generated and stored exclusively within Coinbase's Trusted Execution Environments. The agent's code, the LLM, and the developer's server never have access to the raw private key. All transaction signing occurs inside the enclave, and only the signed transaction is returned to the agent. This means that even a complete compromise of the agent's application layer cannot result in key theft [3].

**Programmable Spending Guardrails.** Before an agent is deployed, the developer configures hard limits at the infrastructure level — not in application code that can be bypassed. These include a maximum spend per individual transaction and a maximum spend per session. The agent is physically incapable of exceeding these limits, regardless of what instruction it receives [1].

**KYT (Know Your Transaction) Screening.** Every transaction initiated by an agent is automatically screened against Coinbase's compliance database before execution. Transactions involving high-risk addresses, sanctioned wallets, or known exploit contracts are blocked at the infrastructure level before they can be broadcast to the network [2].

**CDP Security Suite.** The entire system runs on the same infrastructure that secures millions of Coinbase consumer accounts, providing battle-tested DDoS protection, anomaly detection, and security monitoring [1].

### What Transactions Can an Agent Execute Autonomously?

An agent can autonomously execute any transaction for which it has a corresponding installed skill and which falls within its configured spending limits. In practice, this includes sending USDC and other ERC-20 tokens on the Base network, executing token swaps on Base DEXs (gaslessly), paying for services via the x402 protocol, and deploying capital into yield protocols. Limits on autonomous trading are not defined by trading frequency or volume but are enforced strictly through the per-transaction and per-session spending caps set by the developer at configuration time.

### Important Distinction: Agentic Wallets vs. Advanced Trade API

It is critical to understand that **Agentic Wallets operate on the Base blockchain (Layer 2)** and are designed for on-chain DeFi operations. They are **not** a direct interface to the Coinbase centralised exchange order book. For the VÉLØ module to execute trades on the Coinbase Advanced Trade platform (the centralised exchange with deep liquidity for pairs like BTC-USD), it must use the **Coinbase Advanced Trade API** described in Section 2. Agentic Wallets and the Advanced Trade API serve different but complementary purposes within the VÉLØ architecture.

---

## 2. Coinbase APIs for Trading

### Overview

The **Coinbase Advanced Trade API** is the primary interface for programmatic trading on Coinbase's centralised exchange. It replaced the deprecated Coinbase Pro API and provides access to the same deep order books used by institutional traders. The API is structured around a `v3` endpoint namespace and offers both a REST API for order management and account operations, and a WebSocket API for real-time streaming market data [4].

**Production Base URL:** `https://api.coinbase.com/api/v3/brokerage/`
**Sandbox Base URL:** `https://api-sandbox.coinbase.com/api/v3/brokerage/`

### REST API: Key Endpoints

The following table lists the most important REST endpoints for a trading module:

| Operation | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Create Order** | `POST` | `/orders` | Places a new order (market, limit, stop-limit, bracket). |
| **Cancel Orders** | `POST` | `/orders/batch_cancel` | Cancels one or more open orders in a single request. |
| **Edit Order** | `POST` | `/orders/edit` | Modifies the price or size of an open limit order. |
| **Preview Order** | `POST` | `/orders/preview` | Simulates an order to see estimated fees and fills without placing it. |
| **Get Order** | `GET` | `/orders/historical/{order_id}` | Retrieves the details of a specific order. |
| **List Orders** | `GET` | `/orders/historical/batch` | Retrieves a paginated list of historical orders. |
| **List Fills** | `GET` | `/orders/historical/fills` | Retrieves a list of all trade fills (executions). |
| **List Open Orders** | `GET` | `/orders` | Retrieves all currently open orders. |
| **Get Best Bid/Ask** | `GET` | `/best_bid_ask` | Returns the current best bid and ask for one or more products. |
| **Get Product Book** | `GET` | `/product_book` | Returns the full order book for a product up to a specified depth. |
| **Get Product** | `GET` | `/products/{product_id}` | Returns details for a product, including min order size and price increment. |
| **Get Candles** | `GET` | `/products/{product_id}/candles` | Returns historical OHLCV data for a product. |
| **Get Market Trades** | `GET` | `/products/{product_id}/ticker` | Returns the latest trades for a product. |
| **List Accounts** | `GET` | `/accounts` | Lists all trading accounts and their balances. |
| **Get Account** | `GET` | `/accounts/{account_uuid}` | Returns details for a specific account. |
| **Get Transaction Summary** | `GET` | `/transaction_summary` | Returns fee tier and volume summary for the authenticated user. |

### Rate Limits

Rate limits are the most critical operational constraint for any automated trading system. Coinbase enforces the following limits:

| Limit Type | Value | Scope |
| :--- | :--- | :--- |
| **Private REST Endpoints** | 15 requests/second | Per profile |
| **Public REST Endpoints** | 10 requests/second (burst: 15) | Per IP address |
| **General Hourly Limit** | 10,000 requests/hour | Per API key |
| **WebSocket Connections** | 8 connections/second | Per IP address |
| **WebSocket Unauthenticated Messages** | Rate-limited more aggressively | Per IP address |

Exceeding any of these limits returns an `HTTP 429 Too Many Requests` response. The VÉLØ module must implement an intelligent rate limiter with exponential backoff to handle 429 responses gracefully and avoid being temporarily blocked [5] [6] [7].

### WebSocket Feeds

The WebSocket API is the backbone of any real-time trading system. It eliminates the need to poll REST endpoints for market data, providing a persistent, low-latency stream of updates. The WebSocket endpoint is `wss://advanced-trade-ws.coinbase.com`.

| Channel | Auth Required | Data Provided | Use Case for VÉLØ |
| :--- | :--- | :--- | :--- |
| `heartbeats` | No | Periodic keep-alive messages | Maintaining connection health |
| `level2` | No | Full order book snapshot + incremental updates | Order book analysis, depth monitoring, manipulation detection |
| `market_trades` | No | Real-time stream of every executed trade | Momentum detection, volume analysis |
| `ticker` | No | Best bid/ask and last trade price on each match | Fast price feeds for strategy signals |
| `candles` | No | Real-time updates to 1-minute OHLCV candles | Technical indicator calculation |
| `user` | **Yes** | Real-time updates on the user's own orders and fills | Order status tracking, fill confirmation |

To subscribe to a channel, the VÉLØ module sends a JSON subscription message over the WebSocket connection. For authenticated channels, a valid JWT must be included in the subscription message.

### Order Types

Coinbase Advanced Trade supports a comprehensive set of order types that give the VÉLØ module significant flexibility in strategy execution:

**Market Order** executes immediately at the best available price. It guarantees execution but not price, making it suitable for urgent entries or exits where speed is more important than price precision. Market orders are always taker orders and incur the higher taker fee.

**Limit Order** is placed at a specific price and will only execute if the market reaches that price. If the limit order is placed such that it would immediately match (i.e., a buy limit above the current ask), it executes as a taker. If it rests on the order book waiting to be matched, it executes as a maker and incurs the lower maker fee. The VÉLØ module should favour limit orders wherever possible to reduce fee drag.

**Stop-Limit Order** is a two-stage conditional order. When the market price reaches the specified stop price, a limit order is automatically placed at the specified limit price. This is the primary tool for automated stop-loss management.

**Bracket Order** is an advanced order type that bundles a main entry order with two exit orders: a take-profit limit order and a stop-loss limit order. When the entry order fills, both exit orders are automatically placed. This is highly useful for the VÉLØ module's risk management, as it automates the entire trade lifecycle in a single API call.

**TWAP Order** (Time-Weighted Average Price) is available for larger orders, splitting execution across a defined time window to minimise market impact.

**Minimum Order Sizes** are product-specific. For BTC-USD, the minimum order size is 0.000016 BTC (approximately $1.50 at current prices). For ETH-USD, the minimum is 0.00031 ETH. Exact values for any product can be retrieved from the `/products/{product_id}` endpoint, specifically the `base_min_size` field.

### Fee Structure

Coinbase Advanced Trade uses a **maker-taker fee model** tiered by 30-day trailing USD trading volume. Maker orders (those that add liquidity to the order book) are always cheaper than taker orders (those that remove liquidity). The fee schedule as of early 2026 is as follows [8] [9]:

| 30-Day Volume (USD) | Maker Fee | Taker Fee |
| :--- | :--- | :--- |
| $0 – $10,000 | 0.40% | 0.60% |
| $10,000 – $50,000 | 0.25% | 0.40% |
| $50,000 – $100,000 | 0.15% | 0.25% |
| $100,000 – $1,000,000 | 0.10% | 0.15% |
| $1,000,000 – $15,000,000 | 0.08% | 0.12% |
| $15,000,000 – $75,000,000 | 0.06% | 0.10% |
| $75,000,000 – $250,000,000 | 0.05% | 0.08% |
| $250,000,000 – $400,000,000 | 0.03% | 0.05% |
| > $400,000,000 | 0.00% | 0.02% |

**Fee Impact Example:** On a $10,000 trade at the entry tier, a taker order costs $60 in fees. A maker order costs $40. Over 100 trades per month, this difference is $2,000. Maximising maker order usage is therefore a significant profitability lever for the VÉLØ module.

### Authentication

The Advanced Trade API uses **CDP API Keys** with JWT-based authentication. Every request to a private endpoint requires a freshly generated JWT, which expires after 2 minutes. The process is as follows:

1. A CDP API Key is created on the Coinbase Developer Platform using the **ECDSA (ES256)** signature algorithm. Ed25519 keys are explicitly not supported for Coinbase App APIs and will cause authentication failures [10].
2. For each API request, the VÉLØ module generates a JWT by signing a payload containing the request method, path, and a nonce with the API key's private key.
3. The JWT is passed in the `Authorization: Bearer <JWT>` header of the HTTP request.

The official `coinbase-advanced-py` Python SDK handles JWT generation automatically, which is the recommended approach for the VÉLØ module.

### Sandbox Environment

Coinbase provides a **static sandbox environment** for testing integrations without using real funds. The sandbox returns pre-defined, static responses that mirror the format of the production API. It does not simulate a live order book or execute real paper trades, but it is invaluable for testing the authentication flow, request formatting, and response parsing logic of the VÉLØ module before going live [11].

---

## 3. High-Frequency Trading (HFT) Capabilities

### The Reality of HFT on Coinbase

True high-frequency trading — as practised by institutional firms operating at microsecond latencies — is not feasible on the Coinbase Advanced Trade API. This is a hard technical reality, not a policy choice. The API architecture, rate limits, and network topology simply do not support the order throughput or latency characteristics required for genuine HFT. However, it is important to reframe the question: the VÉLØ module does not need to compete with institutional HFT firms. It needs to execute automated strategies faster and more consistently than a human trader, which is an entirely achievable goal.

### Order Throughput

The hard ceiling for order actions on the Advanced Trade API is **15 requests per second** on private endpoints [5]. In practice, accounting for network round-trip time (typically 50–200ms to Coinbase's servers from a European VPS), the realistic throughput is closer to **5–10 order actions per second**. This translates to a minimum inter-order interval of approximately 100–200 milliseconds. For context, institutional HFT systems execute thousands of orders per second.

### WebSocket Latency

The WebSocket feed for market data is not subject to the same rate limits as the REST API, but it is subject to network latency. Coinbase does not publish official WebSocket latency figures. Based on industry benchmarks for comparable centralised crypto exchanges, realistic WebSocket latency from a European cloud server to Coinbase's infrastructure is in the range of **20–150 milliseconds** for market data updates [12]. This is the time between a trade occurring on the exchange and the VÉLØ module receiving notification of it.

### Co-location and Institutional Connectivity

Coinbase does offer low-latency connectivity options, but these are exclusively for its institutional products:

| Service | Product | Location | Access Method |
| :--- | :--- | :--- | :--- |
| **Physical Co-location** | Derivatives Exchange | Equinix CH4, Chicago | Direct server placement |
| **Physical Co-location** | Derivatives Exchange | Equinix NY5, New Jersey | Direct server placement |
| **AWS PrivateLink** | Derivatives Exchange | AWS US-East-1 | Virtual private connection |
| **FIX Protocol** | Coinbase Prime | N/A | Dedicated FIX session |

These options are **not available** for the standard Advanced Trade API. The VÉLØ module, operating on the Advanced Trade API, will connect over the public internet and is subject to standard internet latency [13] [14].

### Achievable Trading Frequency

Given these constraints, the following table provides a realistic assessment of what is achievable:

| Strategy Type | Typical Hold Time | Feasibility on Advanced Trade API | Notes |
| :--- | :--- | :--- | :--- |
| **True HFT** (microseconds) | < 1ms | Not feasible | Requires co-location and FIX protocol. |
| **Scalping** (seconds) | 1–60 seconds | Marginally feasible | Rate limits are a significant constraint; requires careful management. |
| **Day Trading** (minutes) | 5–60 minutes | Fully feasible | The primary target frequency for VÉLØ. |
| **Swing Trading** (hours) | 1–24 hours | Fully feasible | Well within API capabilities. |
| **Position Trading** (days) | Days to weeks | Fully feasible | No meaningful API constraints. |

The optimal operating frequency for the VÉLØ module is **day trading in the minutes-to-hours timeframe**. This range is fast enough to capture intraday opportunities and react to market events, while remaining well within the API's rate limits and latency characteristics.

### Comparison with Other Exchanges

For reference, the retail-level API constraints on major exchanges are broadly comparable:

| Exchange | Private REST Limit | WebSocket | Co-location (Retail) |
| :--- | :--- | :--- | :--- |
| **Coinbase Advanced Trade** | 15 req/s | Available | No |
| **Binance** | 10 orders/s (1,200/min) | Available | No |
| **Kraken** | ~15 req/s (varies by tier) | Available | No |

No major exchange offers co-location or sub-millisecond latency to retail API users. For the VÉLØ module's target strategy profile, Coinbase's API is competitive with its peers.

---

## 4. Market Data & Manipulation Detection

### Real-Time Order Book Data

The `level2` WebSocket channel is the primary source of real-time order book data. Upon subscription, it delivers a full snapshot of the current order book (all bids and asks up to a configurable depth), followed by a continuous stream of incremental updates as orders are placed, modified, or cancelled. The VÉLØ module must maintain an in-memory representation of this order book, applying each update as it arrives, to have an accurate, real-time view of market depth and liquidity.

The order book is the most information-rich data source available to a trading system. Beyond simply knowing the current price, it reveals the distribution of buy and sell interest at different price levels, the presence of large orders that may act as support or resistance, and the overall balance between buyers and sellers. These insights are fundamental to many of the manipulation detection techniques described below.

### Detecting Market Manipulation

The VÉLØ module's manipulation detection capability is one of its most important differentiators. By continuously analysing order book and trade data, the system can identify patterns that suggest artificial price movements and either avoid trading during those periods or, in some cases, trade against the manipulation.

**Wash Trading Detection.** Wash trading involves a single entity simultaneously buying and selling the same asset to create the illusion of high trading volume. The VÉLØ module can flag potential wash trading by monitoring for a high frequency of trades that are very small in size but very high in number, occurring in rapid succession with minimal price movement. On-chain analysis tools can further confirm wash trading by identifying circular fund flows between a small cluster of wallets.

**Spoofing and Layering Detection.** Spoofing involves placing large orders on the book with no intention of executing them, to create a false impression of supply or demand. The VÉLØ module can detect spoofing by tracking large orders that appear on the book and then monitoring whether they are cancelled before execution. A pattern of large orders consistently appearing and disappearing as the price approaches them is a strong spoofing signal. Layering is a more sophisticated variant where multiple orders at different price levels are placed and then cancelled in a coordinated fashion.

**Pump and Dump Detection.** These schemes are characterised by a sudden, dramatic spike in both price and volume, often accompanied by a surge in social media activity. The VÉLØ module can detect this pattern by combining on-exchange volume anomaly detection (flagging assets where volume has increased by more than a configurable multiple of its recent average) with social media sentiment monitoring. An asset experiencing a 500% volume spike alongside a flood of promotional posts on X/Twitter should be treated with extreme caution.

**Whale Order Detection.** The appearance of an unusually large order on the order book — a "whale wall" — can signal an impending price move. The VÉLØ module can monitor the `level2` feed for orders that exceed a configurable size threshold and use their presence (and subsequent removal) as a signal for the direction of the next significant price move.

### On-Chain Data Integration

On-chain data provides a layer of transparency that is unique to cryptocurrency markets. By monitoring blockchain activity, the VÉLØ module can gain insights that are invisible to purely on-exchange analysis. Key on-chain signals include exchange inflows and outflows (large transfers of crypto to exchanges typically precede selling pressure), whale wallet movements (tracking the activity of known large holders), and smart contract interactions (monitoring DeFi protocol activity for signs of stress or opportunity).

---

## 5. Trading Strategies for VÉLØ

The VÉLØ module is designed to be strategy-agnostic at the architecture level, with a pluggable signal engine that can implement multiple strategies simultaneously. The following strategies are well-suited to the capabilities and constraints of the Coinbase Advanced Trade API.

### Momentum and Trend Following

Momentum strategies capitalise on the tendency of assets that are moving strongly in one direction to continue moving in that direction. The VÉLØ module would implement this by calculating momentum indicators (such as the Rate of Change, RSI, or MACD) on the real-time candle data from the WebSocket feed. When a strong trend is detected above a confidence threshold, the module enters a position in the direction of the trend and uses a trailing stop-loss to protect profits as the trend continues.

### Mean Reversion

Mean reversion strategies are based on the statistical observation that asset prices tend to revert to their historical average after significant deviations. The VÉLØ module can implement this using Bollinger Bands or Z-score analysis on the price series. When the price deviates more than two standard deviations from its moving average, the module takes a position betting on a return to the mean. This strategy performs best in ranging, sideways markets and should be disabled when a strong trend is detected.

### Statistical Arbitrage

Statistical arbitrage exploits the historically stable price relationships between correlated assets. For example, many altcoins maintain a relatively stable ratio to Bitcoin's price. When this ratio deviates significantly from its historical norm, the VÉLØ module can simultaneously buy the underperforming asset and sell the outperforming one, profiting when the ratio reverts. This is a market-neutral strategy that can generate returns regardless of the overall market direction.

### Event-Driven Trading

This strategy uses the information aggregation pipeline described in Section 7 to trade on news and market-moving events. When the VÉLØ module detects a significant event — such as a major exchange listing announcement, a regulatory decision, or a large protocol hack — it can execute a pre-programmed response. For example, a new exchange listing announcement typically causes a significant short-term price increase in the listed asset, which can be traded programmatically if the news is detected quickly enough.

### Grid Trading

Grid trading involves placing a series of buy and sell limit orders at predefined price intervals above and below the current price. As the price oscillates within the grid, orders are filled and new orders are placed, generating small but consistent profits from volatility. This strategy is particularly effective in sideways markets and is well-suited to the VÉLØ module's ability to manage many open orders simultaneously. Because grid orders are limit orders, they benefit from the lower maker fee tier.

### Intelligent Dollar-Cost Averaging (DCA)

Rather than buying a fixed amount at regular intervals, an intelligent DCA strategy adjusts the purchase amount based on market conditions. The VÉLØ module can implement this by buying more when the Fear & Greed Index is in "Extreme Fear" territory (historically a good buying opportunity) and less when it is in "Extreme Greed" territory. This strategy is best suited for building a long-term position in high-conviction assets rather than short-term day trading.

---

## 6. VÉLØ Trading Module Architecture

### System Overview

The VÉLØ trading module is best conceptualised as a data-driven intelligence pipeline with five distinct stages: data ingestion, analysis, signal generation, risk management, and execution. Each stage is designed to be modular and independently scalable, allowing the system to be upgraded incrementally without requiring a full rebuild.

The following table maps the VÉLØ racing intelligence framework to the trading module's components:

| VÉLØ Racing Intelligence | VÉLØ Trading Module Equivalent | Function |
| :--- | :--- | :--- |
| Race Analysis | **Market Analysis Engine** | Processes all incoming data streams to build a real-time model of the market environment. |
| RPD-C Tagging | **Signal Detection Engine** | Identifies specific, actionable trading signals from the analysed data. |
| Confidence Bands | **Risk Management Engine** | Assesses signal confidence and determines appropriate position sizing and risk parameters. |
| Selections | **Execution Engine** | Translates approved signals into API calls that place, manage, and close orders. |
| SIGMA Audit | **Post-Trade Analytics** | Analyses completed trades to measure performance and identify areas for improvement. |
| Memory Brain | **Pattern Database** | A persistent store of historical market patterns, trade outcomes, and learned correlations. |

### Component Architecture

**1. Real-Time Data Pipeline.** This is the foundation of the entire system. It consists of multiple concurrent WebSocket connections to the Coinbase Advanced Trade API (for order book, trades, and candle data) and HTTP polling connections to external data APIs (for news, sentiment, on-chain data, and macro indicators). All incoming data is normalised into a consistent internal format and written to a time-series database (such as InfluxDB or TimescaleDB) for both real-time consumption and historical analysis.

**2. Market Analysis Engine.** This component consumes the normalised data stream and performs continuous calculations of technical indicators, statistical metrics, and composite market state signals. It maintains a real-time order book model, calculates rolling statistics (moving averages, volatility, correlation matrices), and produces a continuously updated "market state" object that summarises the current environment across multiple timeframes.

**3. Signal Detection Engine.** This is the core intelligence layer of the VÉLØ module. It applies the configured trading strategies to the market state object and generates trading signals. Each signal includes the asset, direction (buy/sell), confidence score, and the strategy that generated it. The signal engine can run multiple strategies simultaneously, and signals from different strategies can be combined or filtered based on configurable rules.

**4. Risk Management Engine.** Every signal from the detection engine must pass through the risk management engine before it can be executed. This component enforces the following rules: maximum position size as a percentage of total portfolio value; maximum number of concurrent open positions; stop-loss and take-profit levels for each trade; maximum daily drawdown limit (if breached, all trading is halted); and correlation checks to prevent over-concentration in correlated assets.

**5. Execution Engine.** The execution engine is responsible for translating approved trading signals into actual orders on the Coinbase exchange. It manages the full order lifecycle: placing orders, monitoring their status via the `user` WebSocket channel, handling partial fills, and cancelling orders that have not been filled within a configurable timeout. It also implements the rate limiter to ensure the module never exceeds Coinbase's API limits.

**6. Post-Trade Analytics and Pattern Database.** After each trade is closed, the post-trade analytics module records the full trade history (entry price, exit price, hold time, P&L, fees, market conditions at entry) to the pattern database. Over time, this database becomes a rich source of training data for improving the signal detection engine and identifying which strategies perform best under which market conditions.

### Technology Stack Recommendation

| Component | Recommended Technology | Rationale |
| :--- | :--- | :--- |
| **Primary Language** | Python 3.11+ | Excellent ecosystem for data science, trading, and Coinbase's official SDK. |
| **WebSocket Client** | `websockets` or `aiohttp` | Async WebSocket handling for low-latency data ingestion. |
| **REST Client** | `coinbase-advanced-py` (official SDK) | Handles JWT generation and request formatting automatically. |
| **Time-Series DB** | InfluxDB or TimescaleDB | Optimised for high-frequency time-series data storage and querying. |
| **Message Queue** | Redis Pub/Sub or Apache Kafka | Decouples data ingestion from analysis for resilience and scalability. |
| **Task Scheduler** | APScheduler or Celery | For periodic tasks like portfolio rebalancing and report generation. |
| **Monitoring** | Prometheus + Grafana | Real-time dashboards for system health and trading performance. |

---

## 7. Information Aggregation

### The Multi-Signal Intelligence Model

The VÉLØ module's edge over simpler trading bots comes from its ability to synthesise signals from a wide variety of sources into a single, coherent view of the market. No single data source tells the whole story. On-exchange price data tells you what is happening but not why. On-chain data reveals the movement of large capital. Social sentiment captures the psychology of market participants. News feeds provide the narrative context. Derivatives data (funding rates, open interest) reveals the positioning of leveraged traders. Together, these sources create a multi-dimensional picture of the market that is far more powerful than any single signal.

### Data Source Reference

The following table provides a comprehensive reference for all data sources the VÉLØ module should integrate:

| Category | Source | API Endpoint / Access Method | Key Data Points | Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Exchange Data** | Coinbase Advanced Trade | `wss://advanced-trade-ws.coinbase.com` | Order book, trades, candles, ticker | Free |
| **Exchange Data** | Binance (reference) | `wss://stream.binance.com:9443` | Comparative price, volume, funding rates | Free |
| **On-Chain** | Etherscan | `https://api.etherscan.io/api` | Wallet balances, transaction history, token transfers | Free tier available |
| **On-Chain Analytics** | Glassnode | `https://api.glassnode.com/v1/` | Exchange inflows/outflows, SOPR, MVRV, active addresses | Paid subscription |
| **Social Sentiment** | X/Twitter (via API v2) | `https://api.twitter.com/2/` | Mentions, sentiment, trending topics | Paid (Basic tier ~$100/mo) |
| **Social Sentiment** | Reddit | `https://www.reddit.com/dev/api/` | Post sentiment, community activity | Free |
| **News** | CoinDesk | RSS feed / news API | Breaking news, market analysis | Free RSS; paid API |
| **News** | CoinTelegraph | RSS feed / news API | Breaking news, project announcements | Free RSS; paid API |
| **DeFi Data** | DeFiLlama | `https://api.llama.fi/` | TVL per protocol/chain, yields, liquidations | Free |
| **Whale Alerts** | Whale Alert | `https://api.whale-alert.io/v1/` | Large on-chain transactions (> configurable threshold) | Free tier; paid for real-time |
| **Market Sentiment** | Alternative.me | `https://api.alternative.me/fng/` | Fear & Greed Index (0–100 score, daily) | Free |
| **Derivatives** | CoinGlass | `https://open-api.coinglass.com/` | Funding rates, open interest, liquidations across exchanges | Free tier; paid for full access |
| **Macro Sentiment** | CoinMarketCap | `https://pro-api.coinmarketcap.com/v3/fear-and-greed/` | CMC Fear & Greed Index | Free personal use |

### Signal Synthesis Architecture

Raw data from these sources must be processed and fused into actionable signals. The recommended approach for the VÉLØ module is a **weighted multi-factor scoring model** that can be progressively enhanced over time:

**Stage 1 (Initial Deployment):** Each data source generates a normalised score between -1 (strongly bearish) and +1 (strongly bullish). These scores are combined using a weighted average, where weights are initially set based on domain knowledge (e.g., on-exchange price action is weighted more heavily than social sentiment). The composite score drives the signal detection engine's buy/sell/hold decisions.

**Stage 2 (Learning Phase):** As the VÉLØ module accumulates trade history in its pattern database, it can begin to analyse which data sources were most predictive of profitable trades under different market conditions. This analysis can be used to dynamically adjust the weights assigned to each data source.

**Stage 3 (ML Enhancement):** With sufficient historical data, a machine learning model (such as a gradient boosting classifier or a recurrent neural network) can be trained to predict short-term price movements based on the full feature set. This model can replace or augment the weighted scoring model, potentially capturing non-linear relationships between signals that the simpler model would miss.

### Key Derived Signals

Beyond raw data, the following derived signals are particularly valuable for the VÉLØ module's decision-making:

**Funding Rate Signal.** When perpetual futures funding rates are significantly positive (longs paying shorts), it indicates the market is over-leveraged to the long side and a correction may be imminent. When rates are significantly negative, the opposite is true. This signal is especially powerful for timing entries and exits in trending markets.

**Exchange Flow Signal.** A sustained increase in the net flow of Bitcoin or Ethereum from wallets to exchange addresses (measured via on-chain data) typically precedes selling pressure, as traders are moving assets to exchanges in preparation for selling. The reverse — net outflows from exchanges — is typically bullish.

**Fear & Greed Contrarian Signal.** Historically, periods of "Extreme Fear" (index score 0–25) have been among the best buying opportunities, while periods of "Extreme Greed" (index score 75–100) have often preceded corrections. The VÉLØ module can use this as a contrarian signal to bias its position sizing.

---

## 8. Risk and Compliance

### Coinbase Terms of Service for Automated Trading

Automated trading via the Coinbase API is explicitly permitted and supported by Coinbase. The **Coinbase Markets Trading Rules** confirm that traders access the central order book through Coinbase Advanced Trade and that the platform is designed for programmatic access [15]. There are no restrictions on the use of trading bots, algorithmic strategies, or automated order management systems.

However, Coinbase's trading rules contain strict prohibitions on market manipulation that apply equally to automated and manual trading. The relevant clause states:

> **2.62 Market Manipulation of any kind is strictly prohibited.** Market Manipulation is defined as actions taken by any market participant or a person acting in concert with a participant which are intended to: Deceive, mislead, or improperly take advantage of other Traders or Coinbase; Artificially control or manipulate the price or trading volume of an Asset; or Aid, abet, enable, finance, support, or endorse either of the above. [15]

The prohibited activities explicitly listed include front-running, wash trading, spoofing, layering, churning, and quote stuffing. The VÉLØ module must be designed to avoid any trading pattern that could be interpreted as falling into these categories. In particular, strategies that involve placing and rapidly cancelling large orders (even if not intentionally manipulative) could be flagged by Coinbase's surveillance systems. The module should implement a minimum order lifetime before cancellation to avoid any appearance of spoofing.

### UK Tax Implications

For a UK-based operator, all profits from cryptocurrency trading are subject to HMRC tax rules. The applicable tax treatment depends on the nature and frequency of the trading activity.

For most individuals, cryptocurrency trading profits are treated as **Capital Gains** and are subject to Capital Gains Tax (CGT). The current CGT rates for the 2024/2025 tax year are 18% for basic rate taxpayers and 24% for higher and additional rate taxpayers, applied to gains above the annual exempt amount of £3,000 [16].

In cases where trading activity is very frequent, systematic, and constitutes a primary income source, HMRC may classify the individual as a **professional trader**. In this case, profits would be treated as trading income and subject to Income Tax rates (20%, 40%, or 45% depending on the tax band), which are generally less favourable than CGT rates. HMRC has not published a specific threshold for this classification, and it is assessed on a case-by-case basis considering factors such as the frequency of trades, the sophistication of the strategy, and whether the activity is organised in a business-like manner.

The VÉLØ module's post-trade analytics component must maintain comprehensive records for tax reporting purposes. For each trade, HMRC requires: the type of token, the date of the transaction, the price in GBP at the time of the transaction, the number of tokens bought or sold, and a running total of the cost basis for each asset held. The **same-day rule** and the **30-day bed-and-breakfasting rule** also apply to crypto, meaning that disposals and acquisitions of the same asset on the same day (or within 30 days) must be matched for CGT calculation purposes.

### Risk of Account Restriction

Coinbase reserves the right to restrict or terminate accounts for violations of its terms of service. The primary risks for an automated trading account are as follows. Persistently exceeding API rate limits can lead to temporary or permanent suspension of the API key. Trading patterns that resemble market manipulation — even if unintentional — will be flagged by Coinbase's internal trade surveillance systems. Unusual login activity or signs of account compromise can trigger a security hold. To mitigate these risks, the VÉLØ module must implement robust rate limit management, use strategies that are clearly compliant with market integrity rules, store API keys securely, and restrict API key permissions to only those required for trading (no withdrawal permissions).

---

## 9. Setup Guide

### Step 1: Generate CDP API Keys

The VÉLØ module requires a **CDP API Key** with ECDSA signing to interact with the Advanced Trade API. Legacy API keys are not recommended and may be deprecated.

Navigate to the [Coinbase Developer Platform](https://cdp.coinbase.com/) and log in with your existing Coinbase account. Under the **API Keys** tab, select **Secret API Keys** and click **Create API key**. Assign a descriptive nickname such as `VELO_Trading_Module`. Under **API restrictions**, grant the following permissions: `wallet:accounts:read`, `wallet:orders:read`, `wallet:orders:create`, `wallet:orders:cancel`, and `wallet:fills:read`. Do **not** grant `wallet:withdrawal:create` or `wallet:transfers:create` to a trading bot. Under **Advanced Settings**, change the signature algorithm from the default to **ECDSA**. Optionally, add the IP address of your hosting server to the allowlist for additional security. Click **Create API key**, then securely store the API Key Name and Private Key — the private key is shown only once.

### Step 2: Install the Coinbase Advanced Trade SDK

```bash
pip install coinbase-advanced-py
```

Configure your environment variables to store the API credentials securely:

```bash
export COINBASE_API_KEY_NAME="organizations/{org_id}/apiKeys/{key_id}"
export COINBASE_API_KEY_SECRET="-----BEGIN EC PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END EC PRIVATE KEY-----\n"
```

### Step 3: Verify Authentication

Test that your credentials are working correctly by making a simple authenticated request:

```python
from coinbase.rest import RESTClient
import os

client = RESTClient(
    api_key=os.environ["COINBASE_API_KEY_NAME"],
    api_secret=os.environ["COINBASE_API_KEY_SECRET"]
)

accounts = client.get_accounts()
print(accounts)
```

If the response contains your account details, authentication is working correctly.

### Step 4: Set Up Agentic Wallet (for On-Chain Operations)

For on-chain operations on the Base network, install the Agentic Wallet CLI:

```bash
npm install -g @coinbase/awal
```

Authenticate the agent with your Coinbase account:

```bash
npx awal auth
```

Add the trading skills to your agent:

```bash
npx skills add coinbase/agentic-wallet-skills
```

Fund the agent's wallet with USDC from your Coinbase account:

```bash
npx awal fund <amount_in_usdc>
```

### Step 5: Test Order Execution in Sandbox

Configure the VÉLØ module to use the sandbox URL and execute a test order to verify the full order lifecycle:

```python
from coinbase.rest import RESTClient
import os

# Use sandbox URL for testing
client = RESTClient(
    api_key=os.environ["COINBASE_API_KEY_NAME"],
    api_secret=os.environ["COINBASE_API_KEY_SECRET"],
    base_url="https://api-sandbox.coinbase.com"
)

# Place a test limit order
order = client.create_order(
    client_order_id="velo_test_001",
    product_id="BTC-USD",
    side="BUY",
    order_configuration={
        "limit_limit_gtc": {
            "base_size": "0.001",
            "limit_price": "10000.00",  # Well below market to avoid fill
            "post_only": True
        }
    }
)
print(f"Order placed: {order['order_id']}")

# Cancel the test order
cancel = client.cancel_orders(order_ids=[order['order_id']])
print(f"Order cancelled: {cancel}")
```

### Step 6: Going Live Checklist

Before deploying the VÉLØ module with real capital, verify each of the following:

| Item | Status |
| :--- | :--- |
| Production API keys configured (not sandbox) | [ ] |
| API keys stored as environment variables, not in code | [ ] |
| IP allowlist configured on the API key | [ ] |
| Withdrawal permissions NOT granted to the API key | [ ] |
| Rate limiter implemented and tested | [ ] |
| Stop-loss and max drawdown limits configured conservatively | [ ] |
| Logging and monitoring system operational | [ ] |
| Tax record-keeping module active | [ ] |
| Initial capital set to a small test amount (e.g., £500–£1,000) | [ ] |
| Emergency kill switch tested (halts all trading and cancels open orders) | [ ] |

---

## 10. Cost Analysis

### Trading Fees

Trading fees are the dominant ongoing cost for the VÉLØ module and have a direct impact on the profitability of any strategy. At the entry tier (0–$10K monthly volume), a taker fee of 0.60% means that a round-trip trade (one buy and one sell) costs 1.20% of the trade value in fees alone. For a strategy targeting a 1–2% profit per trade, this leaves very little margin for error.

The most important fee optimisation strategy is to maximise the proportion of **maker orders** (limit orders that rest on the book). At the entry tier, the maker fee is 0.40% versus the taker fee of 0.60% — a 33% reduction. At higher volume tiers, the savings are even more significant. The VÉLØ module should be designed to use limit orders wherever possible, accepting the risk of non-execution in exchange for lower fees.

### API and Data Feed Costs

Access to the Coinbase Advanced Trade REST API and WebSocket feeds is **free**. There are no charges for API usage itself. The costs arise from the external data sources required for the information aggregation pipeline. A realistic budget for a well-equipped VÉLØ module's data feeds is as follows:

| Data Source | Free Tier | Paid Tier (approx.) |
| :--- | :--- | :--- |
| Coinbase Advanced Trade API | Full access, free | N/A |
| Alternative.me Fear & Greed | Full access, free | N/A |
| DeFiLlama API | Full access, free | N/A |
| Reddit API | Free (rate-limited) | N/A |
| CoinGlass API | Limited free tier | ~$30–$100/month |
| Whale Alert API | 10 req/min free | ~$30–$99/month |
| X/Twitter API | Very limited free | ~$100/month (Basic) |
| Glassnode (on-chain) | Limited free | ~$39–$799/month |
| News APIs (CoinDesk, etc.) | RSS free | ~$50–$200/month |

A practical starting configuration for VÉLØ would use the free tiers of all available sources (Coinbase, DeFiLlama, Alternative.me, Reddit, RSS news feeds) and selectively add paid tiers as the module proves its profitability. An initial data budget of **£0–£50/month** is achievable without sacrificing core functionality.

### Infrastructure Costs

The VÉLØ module requires a server that runs 24/7. A Virtual Private Server (VPS) is the most cost-effective option for initial deployment. The recommended minimum specification is 2 vCPUs, 4GB RAM, and 50GB SSD storage, which is sufficient to run the Python trading bot, a time-series database, and a Redis instance simultaneously.

| Provider | Plan | Monthly Cost | Suitable For |
| :--- | :--- | :--- | :--- |
| DigitalOcean | Basic Droplet (2 vCPU / 4GB) | ~$18/month | Initial deployment, testing |
| AWS EC2 | t3.medium (2 vCPU / 4GB) | ~$30/month | Production, with AWS ecosystem benefits |
| Hetzner Cloud | CX22 (2 vCPU / 4GB) | ~€5/month | Best value for European deployment |

For a production deployment prioritising low latency to Coinbase's servers (which are hosted on AWS US-East), an AWS EC2 instance in the `us-east-1` region would provide the best network performance.

### Minimum Capital for Meaningful Returns

There is no hard minimum capital requirement on Coinbase, but the economics of trading fees impose a practical minimum. At the entry-tier taker fee of 0.60%, a round-trip trade on a $100 position costs $1.20 in fees. To generate a 1% net profit on that trade, the gross profit must be at least 2.20% — a significant hurdle for short-term strategies.

The following table illustrates the relationship between capital, fees, and required gross profit per trade to achieve a 1% net return:

| Capital per Trade | Round-Trip Fee (1.20%) | Required Gross Profit for 1% Net | Required Gross % |
| :--- | :--- | :--- | :--- |
| $500 | $6.00 | $11.00 | 2.20% |
| $1,000 | $12.00 | $22.00 | 2.20% |
| $5,000 | $60.00 | $110.00 | 2.20% |
| $10,000 | $120.00 | $220.00 | 2.20% |

The fee percentage is constant regardless of trade size, but the absolute dollar amount of fees becomes more manageable relative to potential profits as capital increases. A recommended starting capital for the VÉLØ module is **£2,000–£5,000 (approximately $2,500–$6,500)**. This is large enough to generate profits that meaningfully exceed fees, while being small enough to limit losses during the initial live deployment phase. As the module demonstrates consistent profitability, capital can be scaled up progressively.

---

## 11. References

[1]: https://www.coinbase.com/developer-platform/discover/launches/agentic-wallets "Coinbase. (2026, February 11). Introducing Agentic Wallets: Give Your Agents the Power of Autonomy."

[2]: https://financialit.net/news/artificial-intelligence/coinbase-unveils-agentic-wallets-power-autonomous-ai-agents "Financial IT. (2026, February 11). Coinbase Unveils 'Agentic Wallets' to Power Autonomous AI Agents."

[3]: https://docs.cdp.coinbase.com/agentic-wallet/welcome "Coinbase Developer Documentation. Agentic Wallet."

[4]: https://docs.cdp.coinbase.com/advanced-trade/docs/welcome "Coinbase Developer Documentation. Welcome to Advanced Trade API."

[5]: https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits "Coinbase Developer Documentation. REST Rate Limits Overview."

[6]: https://docs.cdp.coinbase.com/coinbase-app/api-architecture/rate-limiting "Coinbase Developer Documentation. Coinbase App Rate Limiting."

[7]: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-rate-limits "Coinbase Developer Documentation. Advanced Trade WebSocket Rate Limits."

[8]: https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees "Coinbase Help. Coinbase Advanced Trade Fees."

[9]: https://www.bitdegree.org/crypto/tutorials/coinbase-fees "BitDegree. (2026, January 9). Coinbase Fees 2026: A Detailed Breakdown."

[10]: https://docs.cdp.coinbase.com/coinbase-app/authentication-authorization/api-key-authentication "Coinbase Developer Documentation. Coinbase App API Key Authentication."

[11]: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox "Coinbase Developer Documentation. Advanced Trade API Sandbox."

[12]: https://medium.com/@laostjen/high-frequency-trading-in-crypto-latency-infrastructure-and-reality-594e994132fd "Medium. (2025, December 14). High-Frequency Trading in Crypto: Latency, Infrastructure, and Reality."

[13]: https://docs.cdp.coinbase.com/derivatives/introduction/connectivity "Coinbase Developer Documentation. Derivatives Connectivity."

[14]: https://docs.cdp.coinbase.com/prime/concepts/trading/fix "Coinbase Developer Documentation. FIX Protocol."

[15]: https://www.coinbase.com/legal/trading_rules "Coinbase. Coinbase Markets Trading Rules."

[16]: https://www.blockpit.io/tax-guides/crypto-tax-united-kingdom-hmrc "Blockpit. (2026, January 15). Crypto Tax UK: Ultimate Tax Guide for 2026 [HMRC Rules]."

---

*This document was compiled by Manus AI on February 26, 2026 for the VÉLØ Trading Module project. All API specifications, rate limits, and fee structures are accurate as of the document date and should be verified against official Coinbase documentation before production deployment, as these values are subject to change.*
