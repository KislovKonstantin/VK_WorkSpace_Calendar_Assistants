import json
import os
import re
import sys
import logging
from typing import Dict, List, TypedDict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EventAgent")


class ConfigLoader:
    @staticmethod
    def load_config() -> Dict[str, str]:
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("Конфигурация успешно загружена")
                return config
        except FileNotFoundError:
            logger.error("Файл конфигурации не найден")
            sys.exit(1)
        except json.JSONDecodeError:
            logger.error("Ошибка формата в файле конфигурации")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {str(e)}")
            sys.exit(1)


class EventAgent:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.search_tool = self._init_search_tool()
        self.agent = self._init_agent()
        self.workflow = self._build_workflow()

    def _init_search_tool(self) -> TavilySearchResults:
        return TavilySearchResults(
            tavily_api_key=self.config['TAVILY_API_KEY'],
            max_results=3,
            include_answer=True,
            include_raw_content=False
        )

    def _init_agent(self) -> ChatOpenAI:
        return ChatOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=self.config['GEMINI_API_KEY'],
            model="gemini-2.5-pro",
            temperature=0.2
        )

    def _build_system_prompt(self, state: Dict[str, Any]) -> str:
        event = state["event_data"]
        style_description = ""
        if event["style"]["brief"] and event["style"]["formal"]:
            style_description = "Краткое и официальное описание"
        elif event["style"]["brief"] and not event["style"]["formal"]:
            style_description = "Краткое и неформальное (но вежливое) описание"
        elif not event["style"]["brief"] and event["style"]["formal"]:
            style_description = "Подробное и официальное описание"
        else:
            style_description = "Подробное и неформальное (но вежливое) описание"
        event_type = "онлайн-мероприятие" if event["address"] == "online" else "очное мероприятие"
        prompt = f"""
Ты профессиональный ассистент для сервиса Календарь VK WorkSpace, который помогает придумать название и описание события для добавления его в календарь. 
Твоя задача - создать привлекательное и понятное другим людям название, информативное и понятное другим людям описание для события. 

Данные о событии:
- Дата: {event['date']}
- Время: {event['time']}
- Тип: {event_type}
- Дополнительная информация: 
{event['additional_info']}
- Стиль: {style_description}

Требования к генерации:
1. Название:
   - Максимально отражает суть события
   - Привлекательное и запоминающееся
   - Соответствует выбранному стилю
   - Не длиннее 10 слов

2. Описание:
   - Начинается с краткого введения
   - Содержит ключевые детали: цель, задачи, ожидаемые результаты
   - Включает всю дополнительную информацию
   - Соответствует выбранному стилю и формату
   - Заканчивается полезной информацией из 'Дополнительной информации', если ранее в описании она не использовалась (например, ссылки на онлайн-встречу или названия рабочих документов)
   
ВАЖНО! Всегда выводи полный ответ в строго заданном формате:
[NAME] Название события
[DESCRIPTION] Текст описания
"""
        if state.get("weather") and event["address"] != "online":
            prompt += f"\nПрогноз погоды на это время, полученный из интернета при помощи Tavily:\n{state['weather']}\n"
            prompt += "Учти прогноз погоды при составлении описания. Погодная информация должна быть краткой и соответствовать времени и месту."
        return prompt.strip()

    def _get_weather_info(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if state["event_data"]["address"] == "online" or state.get("weather"):
            return state
        try:
            logger.info("Получение информации о погоде...")
            date = state["event_data"]["date"]
            time = state["event_data"]["time"]
            address = state["event_data"]["address"]
            query = f"{date}, {time}, {address} прогноз погоды"
            search_results = self.search_tool.invoke({"query": query})
            weather_info = ""
            for res in search_results:
                weather_info += f"Title: {res.get('title', '')}\n"
                weather_info += f"Content: {res.get('content', '')}\n"
            state["weather"] = weather_info.strip()
            logger.info("Информация о погоде успешно получена")
        except Exception as e:
            state["weather"] = f"Не удалось получить прогноз погоды: {str(e)}"
            logger.error(f"Ошибка получения прогноза погоды: {str(e)}")
        return state

    def _initialize_conversation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if state.get("messages"):
            return state
        logger.info("Инициализация диалога...")
        system_prompt = self._build_system_prompt(state)
        user_prompt = state["event_data"]["prompt"]
        state["messages"] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return state

    def _call_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Вызов агента для генерации...")
        lc_messages = []
        for msg in state["messages"]:
            if msg["role"] == "system":
                lc_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        response = self.agent.invoke(lc_messages)
        state["messages"].append({"role": "assistant", "content": response.content})

        title_match = re.search(r'\[NAME\](.+?)\n', response.content, re.DOTALL)
        desc_match = re.search(r'\[DESCRIPTION\](.+)', response.content, re.DOTALL)

        if title_match and desc_match:
            state["final_output"] = {
                "title": title_match.group(1).strip(),
                "description": desc_match.group(1).strip()
            }
            logger.info("Название и описание успешно сгенерированы")
        else:
            state["final_output"] = {
                "title": "Не удалось сгенерировать название",
                "description": response.content
            }
            logger.warning("Не удалось распарсить ответ агента")

        return state

    def _process_feedback(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not state.get("user_feedback"):
            return state
        logger.info("Обработка пользовательского фидбека...")
        state["messages"].append({
            "role": "user",
            "content": f"Пользовательский фидбек: {state['user_feedback']}\nПожалуйста, учти эти замечания при обновлении названия и описания. Далее твоя задача: заново сгенерировать название и описание события в нужном формате с учетом всех своих предыдущих ответов и фидбека от пользователя"
        })
        if "final_output" in state:
            del state["final_output"]
        if "user_feedback" in state:
            del state["user_feedback"]
        return state

    def _build_workflow(self) -> Any:
        logger.info("Построение графа агента...")

        class AgentState(TypedDict):
            event_data: Dict[str, Any]
            weather: Optional[str]
            messages: List[Dict[str, str]]
            final_output: Optional[Dict[str, str]]
            user_feedback: Optional[str]

        workflow = StateGraph(AgentState)
        workflow.add_node("get_weather", RunnableLambda(self._get_weather_info))
        workflow.add_node("init_conversation", RunnableLambda(self._initialize_conversation))
        workflow.add_node("process_feedback", RunnableLambda(self._process_feedback))
        workflow.add_node("call_agent", RunnableLambda(self._call_agent))
        workflow.set_entry_point("get_weather")
        workflow.add_edge("get_weather", "init_conversation")
        workflow.add_edge("init_conversation", "process_feedback")
        workflow.add_edge("process_feedback", "call_agent")
        workflow.add_edge("call_agent", END)
        return workflow.compile()

    def process_request(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.info("Начало обработки запроса...")
            result = self.workflow.invoke(input_data)
            logger.info("Запрос успешно обработан")
            return result
        except Exception as e:
            logger.error(f"Ошибка обработки запроса: {str(e)}")
            return {
                "error": f"Ошибка обработки запроса: {str(e)}",
                "input_data": input_data
            }


def main(input_file: str, config: Dict[str, str]) -> bool:
    logger.info(f"Обработка файла: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        agent = EventAgent(config)
        result = agent.process_request(input_data)
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("Результат успешно сохранен")
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
        logger.error("Использование: python event_helper.py <input.json>")
        sys.exit(1)
    config = ConfigLoader.load_config()
    success = main(sys.argv[1], config)
    sys.exit(0 if success else 1)