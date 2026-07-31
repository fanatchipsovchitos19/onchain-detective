import time
import threading
from collections import deque
from functools import wraps


class RateLimiter:
    """Ограничитель частоты запросов (Token Bucket)."""

    def __init__(self, max_calls: int, period: float = 1.0):
        """
        Args:
            max_calls: максимальное количество вызовов за period секунд
            period: период в секундах
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.lock = threading.Lock()

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                now = time.time()
                
                # Удаляем старые вызовы (старше period)
                while self.calls and self.calls[0] < now - self.period:
                    self.calls.popleft()
                
                # Если превысили лимит — ждём
                if len(self.calls) >= self.max_calls:
                    sleep_time = self.calls[0] - (now - self.period)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                
                # Регистрируем вызов
                self.calls.append(time.time())
            
            return func(*args, **kwargs)
        return wrapper


# Глобальный лимитер (5 запросов/сек для Etherscan бесплатного тира)
etherscan_limiter = RateLimiter(max_calls=5, period=1.0)