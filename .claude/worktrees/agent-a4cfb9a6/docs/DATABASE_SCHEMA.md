# VÉLØ Oracle 2.0 - Database Schema Guide

This document provides an overview of the PostgreSQL database schema used in VÉLØ Oracle 2.0.

## Schema Philosophy

The database is designed to be the Oracle's long-term memory, capturing everything from raw historical data to live market movements, ML predictions, and betting outcomes. It is structured to support both deep historical analysis and real-time decision-making.

## Core Tables

- **`racing_data`**: Stores raw historical race results, primarily from Kaggle datasets.
- **`sectional_data`**: Contains sectional timing data for detailed pace analysis.
- **`racecards`**: Holds daily racecard information scraped from sources like `rpscrape`.

## Oracle 2.0 Extension Tables

- **`betfair_markets`**: Stores information about each Betfair market.
- **`betfair_odds`**: Logs time-series data of odds for each runner, forming the basis for market movement analysis.
- **`manipulation_alerts`**: Records detected market manipulation events, a key feature of Oracle 2.0.
- **`predictions`**: A log of all predictions made by the ML engine, including probabilities, recommended bets, and eventually, the actual outcome.
- **`model_versions`**: Tracks versions of the trained ML models and their performance metrics.
- **`race_analysis`**: The core of the Genesis Protocol, storing post-race insights and learned lessons.
- **`learned_patterns`**: A library of validated racing patterns (e.g., "favorite_drift_trap").
- **`betting_ledger`**: A complete and immutable record of all bets placed, stakes, odds, and profit/loss, providing full transparency and bankroll tracking.

For the complete and detailed schema, please refer to the SQL file: `database/schema_v2.sql`.

