import json
import sys
import re
import os
import logging
from typing import Dict

from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GreetingService")

class ConfigLoader:
    @staticmethod
    def load_config() -> Dict[str, str]:
        config_path = os.getenv('CONFIG_PATH', 'config.json')
        config = {}
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    config.update(file_config)
                    logger.info(f"Конфигурация загружена из {config_path}")
        except Exception as e:
            logger.error(f"Ошибка загрузки конфига: {str(e)}")
        env_keys = {
            'TAVILY_API_KEY': os.getenv('TAVILY_API_KEY'),
            'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY')
        }
        config.update({k: v for k, v in env_keys.items() if v})
        required_keys = ['TAVILY_API_KEY', 'GEMINI_API_KEY']
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            logger.error(f"Отсутствуют обязательные ключи: {', '.join(missing_keys)}")
            sys.exit(1)
        return config


class GreetingGenerator:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.search_tool = TavilySearchResults(
            tavily_api_key=config['TAVILY_API_KEY'],
            max_results=3,
            include_answer=True,
            include_raw_content=False
        )
        self.agent = ChatOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=config['GEMINI_API_KEY'],
            model="gemini-2.5-pro",
            temperature=0.7
        )

    @staticmethod
    def get_time_greeting(time_str: str) -> str:
        try:
            hour = int(time_str.split(':')[0])
            if 5 <= hour < 12:
                return "Доброе утро"
            elif 12 <= hour < 17:
                return "Добрый день"
            elif 17 <= hour < 22:
                return "Добрый вечер"
            return "Доброй ночи"
        except (ValueError, IndexError):
            logger.warning(f"Некорректный формат времени: {time_str}. Агент определит время самостоятельно.")
            return "Необходимо выбрать корректную форму приветствия самостоятельно"

    def generate_greeting(self, date: str, time_str: str) -> str:
        try:
            query = f"{date} международные и государственные праздники в России"
            search_results = self.search_tool.invoke({"query": query})
            search_summary = '\n'.join(
                f"Title: {res.get('title', '')}\nContent: {res.get('content', '')[:300]}"
                for res in search_results
            )
            time_greeting = self.get_time_greeting(time_str)
            prompt = self._build_prompt(time_greeting, time_str, date, search_summary)
            response = self.agent.invoke([
                SystemMessage(content="Ты профессиональный ассистент календаря VK WorkSpace"),
                HumanMessage(content=prompt)
            ])
            return response.content
        except Exception as e:
            logger.error(f"Ошибка генерации приветствия: {str(e)}")
            return f"Ошибка генерации приветствия: {str(e)}"

    @staticmethod
    def _build_prompt(time_greeting: str, time_str: str, date: str, search_summary: str) -> str:
        return f"""
Ты ассистент календаря VK WorkSpace. Сгенерируй приветствие для пользователя с учетом:
1. Текущее время: {time_greeting} ({time_str})
2. Сегодняшняя дата: {date}
3. Найденная информация о праздниках: 
{search_summary}

Требования:
- Приветствие должно быть кратким (1-2 предложения)
- Косвенно упомяни 1-2 наиболее интересных НЕрелигиозных/НЕполитических праздника
- Плавно интегрируй рекламу календаря VK WorkSpace
- Стиль: дружелюбный профессиональный (не слишком формальный, но и не развязный)
- Заканчивай приветствие восклицательным знаком (!)
- После размышлений в качестве финального ответа добавь тег [GREETINGS] и само приветствие

О календаре VK WorkSpace:
- Корпоративный инструмент для планирования встреч и мероприятий
- Интеграция с почтой, видеозвонками и документами
- Поддержка on-premise решений для безопасности данных
- Умные напоминания и аналитика расписания

Примеры удачных фраз:
"А вы знали, что сегодня День программиста? Запрограммируйте свои планы с помощью Календаря VK WorkSpace!"
"В такую прекрасную дату самое время запланировать встречи на следующую неделю. VK WorkSpace поможет!"
        """.strip()

    @staticmethod
    def parse_greeting(response: str) -> str:
        match = re.search(r'\[GREETINGS\](.+)', response, re.DOTALL)
        if match:
            result = match.group(1).strip()
            result = re.sub(r'\s+', ' ', result)
            if not result.endswith('!') and not result.endswith('.'):
                result += '!'
            return result
        return response

def main(input_file: str, config: Dict[str, str]):
    logger.info(f"Обработка файла: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        required_fields = ['date', 'time']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")
            return False
        generator = GreetingGenerator(config)
        greeting = generator.generate_greeting(data['date'], data['time'])
        parsed_greeting = generator.parse_greeting(greeting)

        data['greeting'] = parsed_greeting
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("Приветствие успешно сгенерировано:")
        logger.info(parsed_greeting)
        return True

    except FileNotFoundError:
        logger.error(f"Файл не найден: {input_file}")
    except json.JSONDecodeError:
        logger.error(f"Ошибка формата JSON в файле: {input_file}")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")

    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Использование: python greeting_service.py <input.json>")
        sys.exit(1)

    config = ConfigLoader.load_config()
    success = main(sys.argv[1], config)
    sys.exit(0 if success else 1)