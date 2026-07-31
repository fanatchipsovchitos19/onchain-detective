# 🔍 On-Chain Detective Framework

AI-powered blockchain detective. Turns raw on-chain data into plain-language investigation reports.

## Features

- **Wallet Clustering** — finds hidden connections and insider rings
- **Insider Detector** — identifies wallets that systematically buy before pumps
- **Whale Monitor** — tracks large movements (>$50k) with AI interpretation
- **AI Investigation** — DeepSeek / ChatGPT analyzes data and returns verdict (RED/YELLOW/GREEN)

## Quick Start

### 1. Installation

git clone [repo]
cd onchain_detective
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

### 2. Configuration

Create .env from template:

cp .env.example .env

Add your API keys:

ETHERSCAN_API_KEY=your_key
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1  # or https://api.routerai.ru/api/v1
AI_MODEL=gpt-4o-mini  # or deepseek/deepseek-v4-pro

### 3. Launch

jupyter notebook notebooks/01_quick_start.ipynb

Run cells in order and get AI-powered investigation reports.

## Requirements

- Python 3.10+
- API keys: Etherscan, OpenAI (or RouterAI)

## License

MIT
