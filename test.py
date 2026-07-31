from onchain_detective.config import settings
from onchain_detective.providers.etherscan import EtherscanProvider

print("✅ Config loaded!")
print(f"Network: {settings.NETWORK}")
print(f"Etherscan URL: {settings.etherscan_base_url}")

# Тест провайдера (без API ключа просто создастся объект, запросы не пойдут)
provider = EtherscanProvider(settings.ETHERSCAN_API_KEY)
print(f"✅ Provider created: {provider}")
print(f"Cache enabled: {settings.CACHE_ENABLED}")