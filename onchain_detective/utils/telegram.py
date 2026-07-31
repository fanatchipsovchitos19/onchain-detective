"""
Отправка уведомлений в Telegram.
"""

import requests
from ..config import settings


class TelegramAlerter:
    """Отправляет алерты в Telegram."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Отправить сообщение.
        
        Args:
            message: текст сообщения (поддерживает HTML)
            parse_mode: HTML или Markdown
            
        Returns:
            True если успешно
        """
        if not self.bot_token or not self.chat_id:
            print("[Telegram] Токен или chat_id не настроены")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message[:4000],  # лимит Telegram
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                print(f"[Telegram] Ошибка: {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"[Telegram] Ошибка отправки: {e}")
            return False

    def send_whale_alert(self, whale_address: str, action: str, 
                         amount_usd: float, tx_hash: str, 
                         ai_comment: str = "") -> bool:
        """
        Отправить алерт о движении кита.
        """
        emoji = "🔴" if action == "sell" else "🟢"
        
        message = f"""
{emoji} <b>КИТ АКТИВЕН</b> {emoji}

<b>Адрес:</b> <code>{whale_address[:10]}...</code>
<b>Действие:</b> {action.upper()}
<b>Сумма:</b> ${amount_usd:,.0f}
<b>TX:</b> <a href="https://etherscan.io/tx/{tx_hash}">{tx_hash[:10]}...</a>
"""
        if ai_comment:
            message += f"\n<b>AI-анализ:</b> {ai_comment}"

        return self.send(message)