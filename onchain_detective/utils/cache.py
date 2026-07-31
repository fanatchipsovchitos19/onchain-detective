import diskcache
import hashlib
import json
from functools import wraps
from pathlib import Path
from ..config import settings


# Инициализируем кеш в папке data/.cache
cache_dir = settings.DATA_DIR / ".cache"
cache = diskcache.Cache(directory=str(cache_dir))


def cache_key(*args, **kwargs) -> str:
    """Генерирует уникальный ключ из аргументов функции."""
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def cached(ttl: int = None):
    """
    Декоратор для кеширования результатов вызова функции.
    
    Args:
        ttl: время жизни кеша в секундах (по умолчанию из settings)
    """
    if ttl is None:
        ttl = settings.CACHE_TTL_SECONDS

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not settings.CACHE_ENABLED:
                return func(*args, **kwargs)
            
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"
            
            result = cache.get(key)
            if result is not None:
                return result
            
            result = func(*args, **kwargs)
            cache.set(key, result, expire=ttl)
            return result
        
        def clear_cache():
            """Очистить весь кеш."""
            cache.clear()
        
        wrapper.clear_cache = clear_cache
        return wrapper
    return decorator