# VÉLØ Oracle 2.0 - Machine Learning Model Overview

This document describes the machine learning engine at the core of VÉLØ Oracle 2.0.

## Model Philosophy

The ML engine is inspired by Bill Benter's highly successful model for horse racing prediction. It is a **multinomial logit model** that calculates the probability of each horse winning a race. The model is built on the premise that a combination of fundamental horse/race characteristics and public market data can predict outcomes more accurately than either can alone.

## Core Features

- **Benter-Inspired Variables**: The model uses over 130 features, categorized into areas such as horse characteristics, recent form, jockey/trainer stats, course/distance suitability, and market indicators.
- **Two-Model Approach**: While the current implementation focuses on the fundamental model, the framework is designed to incorporate a second model that uses public odds as a primary input, eventually blending the two for a more refined prediction.
- **Dynamic Training**: The `MLEngine` class supports training new model versions, saving them, and tracking their performance over time in the `model_versions` table.
- **Kelly Criterion Staking**: The engine includes a function to calculate the optimal stake size based on the model's predicted probabilities and the market odds, using the fractional Kelly Criterion for bankroll management.
- **Backtesting**: A robust backtesting framework allows for the evaluation of model performance and profitability on historical data.

## Implementation

- **Module**: `src/ml/ml_engine.py`
- **Key Classes**:
    - `BenterModel`: Implements the core logic of the multinomial logit model, including feature preparation, training, and prediction.
    - `MLEngine`: Manages the overall ML workflow, including model versioning, training runs, prediction requests, and backtesting.

This is a living system. The model will be continuously retrained and refined as more data is collected and the Genesis Protocol uncovers new, predictive patterns.

