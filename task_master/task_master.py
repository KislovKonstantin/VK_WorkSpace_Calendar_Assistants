import json
import os
import re
import sys
import logging
from typing import Dict, List, TypedDict, Any, Optional
from langchain_openai import ChatOpenAI
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
logger = logging.getLogger("TaskAgent")

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

class TaskAgent:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.agent = self._init_agent()
        self.workflow = self._build_workflow()

    def _init_agent(self) -> ChatOpenAI:
        return ChatOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=self.config['GEMINI_API_KEY'],
            model="gemini-2.5-pro",
            temperature=0.2
        )

    def _build_system_prompt(self, state: Dict[str, Any]) -> str:
        task = state["task_data"]
        style_description = ""
        if task["style"]["brief"] and task["style"]["formal"]:
            style_description = "Краткое и официальное описание"
        elif task["style"]["brief"] and not task["style"]["formal"]:
            style_description = "Краткое и неформальное (но профессиональное) описание"
        elif not task["style"]["brief"] and task["style"]["formal"]:
            style_description = "Подробное и официальное описание"
        else:
            style_description = "Подробное и неформальное (но профессиональное) описание"

        time_info = ""
        if task["all_day"]:
            time_info = f"Весь день: {task['start_date']}"
        else:
            time_info = f"Начало: {task['start_date']} {task['start_time']}\nОкончание: {task['end_date']} {task['end_time']}"

        prompt = f"""
Ты профессиональный ассистент для сервиса Календарь VK WorkSpace, который помогает придумать 
название и описание задачи для добавления ее в календарь. Твоя задача - создать четкое, 
понятное и информативное описание задачи, которое поможет участникам точно понять, 
что нужно сделать и какие результаты ожидаются.

Данные о задаче:
- Временные параметры: {time_info}
- Стиль: {style_description}
- Дополнительная информация: 
{task['additional_info']}

Требования к генерации:
1. Название задачи:
   - Максимально точно отражает суть задачи
   - Содержит глагол действия (сделать, подготовить, проверить и т.д.)
   - Лаконичное (не длиннее 7-8 слов)
   - Позволяет сразу понять суть задачи

2. Описание задачи:
   - Начинается с краткого введения/контекста
   - Четко описывает ожидаемый результат
   - Перечисляет ключевые шаги для выполнения (если применимо)
   - Указывает ответственных и участников (если есть в additional_info)
   - Включает все необходимые ссылки и ресурсы
   - Заканчивается четкими критериями успешного выполнения
   - Соответствует выбранному стилю

ВАЖНО! Всегда выводи полный ответ в строго заданном формате:
[NAME] Название задачи
[DESCRIPTION] Текст описания
"""
        return prompt.strip()

    def _initialize_conversation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if state.get("messages"):
            return state
        logger.info("Инициализация диалога...")
        system_prompt = self._build_system_prompt(state)
        user_prompt = state["task_data"]["prompt"]
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
            logger.info("Название и описание задачи успешно сгенерированы")
        else:
            state["final_output"] = {
                "title": "Не удалось сгенерировать название задачи",
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
            "content": f"Пользовательский фидбек: {state['user_feedback']}\nПожалуйста, учти эти замечания при обновлении названия и описания. Далее твоя задача: заново сгенерировать название и описание задачи в нужном формате с учетом всех своих предыдущих ответов и фидбека от пользователя"
        })
        if "final_output" in state:
            del state["final_output"]
        if "user_feedback" in state:
            del state["user_feedback"]
        return state

    def _build_workflow(self) -> Any:
        logger.info("Построение графа агента...")

        class AgentState(TypedDict):
            task_data: Dict[str, Any]
            messages: List[Dict[str, str]]
            final_output: Optional[Dict[str, str]]
            user_feedback: Optional[str]

        workflow = StateGraph(AgentState)
        workflow.add_node("init_conversation", RunnableLambda(self._initialize_conversation))
        workflow.add_node("process_feedback", RunnableLambda(self._process_feedback))
        workflow.add_node("call_agent", RunnableLambda(self._call_agent))
        workflow.set_entry_point("init_conversation")
        workflow.add_edge("init_conversation", "process_feedback")
        workflow.add_edge("process_feedback", "call_agent")
        workflow.add_edge("call_agent", END)
        return workflow.compile()

    def process_request(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.info("Начало обработки запроса задачи...")
            result = self.workflow.invoke(input_data)
            logger.info("Запрос задачи успешно обработан")
            return result
        except Exception as e:
            logger.error(f"Ошибка обработки запроса задачи: {str(e)}")
            return {
                "error": f"Ошибка обработки запроса задачи: {str(e)}",
                "input_data": input_data
            }


def main(input_file: str, config: Dict[str, str]) -> bool:
    logger.info(f"Обработка файла задачи: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        agent = TaskAgent(config)
        result = agent.process_request(input_data)
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("Результат задачи успешно сохранен")
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
        logger.error("Использование: python task_master.py <input.json>")
        sys.exit(1)
    config = ConfigLoader.load_config()
    success = main(sys.argv[1], config)
    sys.exit(0 if success else 1)