# VÉLØ Oracle 2.0 - API Integration Guide

This document outlines the integration of external APIs within the VÉLØ Oracle 2.0 system.

## 1. Betfair API

- **Purpose**: Live odds, market volume, and real-time market movement analysis.
- **Module**: `src/integrations/betfair_api.py`
- **Key Features**:
    - Session management with automatic token renewal.
    - Streaming-like functionality for market odds (`get_market_odds`).
    - Market movement and manipulation detection (`detect_market_movement`).
- **Setup**:
    - Requires `BETFAIR_USERNAME`, `BETFAIR_PASSWORD`, and `BETFAIR_APP_KEY` in the `.env` file.

## 2. The Racing API

- **Purpose**: Access to a deep historical database of over 500,000 races.
- **Module**: `src/integrations/racing_api.py`
- **Key Features**:
    - Fetching historical race results, horse form, jockey/trainer stats.
    - Caching layer to minimize redundant API calls.
    - Advanced search for finding historically similar races.
- **Setup**:
    - Requires `RACING_API_KEY` in the `.env` file.

