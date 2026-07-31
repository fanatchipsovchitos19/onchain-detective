"""
AI-интерпретатор на основе OpenAI-совместимого API.
"""

import json
import yaml
from pathlib import Path
from openai import OpenAI
from ..config import settings


class AIAnalyzer:
    """AI-анализатор данных ончейн."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url or getattr(settings, 'OPENAI_BASE_URL', 'https://api.openai.com/v1')
        self.model = model or settings.AI_MODEL

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # Загружаем промпты
        prompts_dir = Path(__file__).parent / "prompts"
        self.prompts = {}
        for f in prompts_dir.glob("*.yaml"):
            with open(f, "r", encoding="utf-8") as fp:
                self.prompts[f.stem] = yaml.safe_load(fp)

    def investigate(self, cluster_data: dict, insider_data: dict = None) -> dict:
        """
        Проводит полное AI-расследование.
        
        Args:
            cluster_data: результаты кластеризации (из WalletClusterer.export_report())
            insider_data: результаты поиска инсайдеров (из InsiderDetector.analyze_token())
            
        Returns:
            Словарь с вердиктом и рекомендацией
        """
        prompt_config = self.prompts.get("investigation_report")
        if not prompt_config:
            return {"error": "Prompt investigation_report.yaml не найден"}

        # Формируем сообщение
        system_msg = prompt_config["system"]
        user_msg = prompt_config["user_template"].format(
            token_address=insider_data.get("token_address", "unknown") if insider_data else "unknown",
            creator=insider_data.get("creator", "unknown")[:10] if insider_data else "unknown",
            age_days=insider_data.get("age_days", "?") if insider_data else "?",
            total_wallets=cluster_data.get("total_wallets_analyzed", 0),
            total_connections=cluster_data.get("total_connections", 0),
            suspicious_clusters=cluster_data.get("suspicious_clusters", 0),
            cluster_details=json.dumps(cluster_data.get("cluster_details", []), indent=2),
            total_early_buyers=insider_data.get("total_early_buyers", 0) if insider_data else 0,
            suspicious_early_count=insider_data.get("suspicious_count", 0) if insider_data else 0,
            top_buyers=json.dumps(insider_data.get("top_buyers", [])[:3] if insider_data else [], indent=2),
        )

        print("[AI] Отправляю запрос...")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=settings.AI_TEMPERATURE,
                max_tokens=settings.AI_MAX_TOKENS,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            print(f"[AI] Ответ получен. Риск: {result.get('risk_level', '?')}")
            return result

        except Exception as e:
            print(f"[AI] Ошибка: {e}")
            return {
                "risk_level": "UNKNOWN",
                "summary": f"Ошибка AI-анализа: {str(e)[:200]}",
                "verdict": "Не удалось провести анализ",
                "recommendation": "WAIT",
                "red_flags": [],
            }