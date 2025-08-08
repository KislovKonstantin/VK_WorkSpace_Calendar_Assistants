import streamlit as st
import json
import os
import subprocess
import datetime
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
INPUT_FILE = DATA_DIR / "input.json"

def init_session_state():
    if 'step' not in st.session_state:
        st.session_state.step = "input"
        st.session_state.attempts = 0
        st.session_state.max_attempts = 5
        st.session_state.event_data = {
            "date": str(datetime.date.today()),
            "time": datetime.datetime.now().strftime("%H:%M"),
            "address": "",
            "additional_info": "",
            "prompt": "",
            "style": {"brief": False, "formal": False}
        }
        st.session_state.generation_history = []
        st.session_state.final_output = None
        st.session_state.feedback = ""

def format_event_data(event_data):
    style_map = {
        (True, True): "Краткий и официальный",
        (True, False): "Краткий и неформальный",
        (False, True): "Подробный и официальный",
        (False, False): "Подробный и неформальный"
    }
    style_key = (event_data["style"]["brief"], event_data["style"]["formal"])
    style_text = style_map.get(style_key, "Не определен")
    event_type = "Онлайн" if event_data["address"] == "online" else "Офлайн"

    formatted = f"""
    **Дата:** {event_data["date"]}  
    **Время:** {event_data["time"]}  
    **Тип мероприятия:** {event_type}  
    **Стиль описания:** {style_text}  
    """

    if event_type == "Офлайн":
        formatted += f"**Адрес:** {event_data['address']}  \n"
    if event_data["additional_info"]:
        formatted += f"**Дополнительная информация:**  \n{event_data['additional_info']}  \n"
    if event_data["prompt"]:
        formatted += f"**Описание события:**  \n{event_data['prompt']}  \n"

    return formatted


def main():
    init_session_state()
    st.markdown(
        "<h1 style='text-align: center;'>ИИ-ассистент для генерации событий в Календаре VK WorkSpace</h1>",
        unsafe_allow_html=True
    )
    st.image("event_helper.png", use_container_width=True)
    st.markdown(
        "<p style='text-align: center;'>Создайте название и описание события с помощью ИИ-ассистента</p>",
        unsafe_allow_html=True
    )
    if st.session_state.step == "input":
        render_input_step()
    elif st.session_state.step == "generation":
        render_generation_step()
    elif st.session_state.step == "final":
        render_final_step()


def render_input_step():
    with st.form("event_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input(
                "Дата события",
                value=datetime.datetime.strptime(st.session_state.event_data["date"], "%Y-%m-%d").date(),
                key="event_date"
            )
            st.session_state.event_data["date"] = str(date)

        with col2:
            time_val = datetime.datetime.strptime(st.session_state.event_data["time"], "%H:%M").time()
            time_input = st.time_input(
                "Время события",
                value=time_val,
                key="event_time"
            )
            st.session_state.event_data["time"] = time_input.strftime("%H:%M")

        is_online = st.checkbox("Онлайн мероприятие", key="is_online")
        address = st.text_input(
            "Адрес мероприятия",
            value=st.session_state.event_data["address"],
            key="event_address"
        )
        if is_online:
            st.session_state.event_data["address"] = "online"
        else:
            st.session_state.event_data["address"] = address

        st.session_state.event_data["additional_info"] = st.text_area(
            "Дополнительная информация (ссылки, названия документов и т.д.)",
            value=st.session_state.event_data["additional_info"],
            key="additional_info"
        )
        st.session_state.event_data["prompt"] = st.text_area(
            "Опишите событие своими словами (цель, задачи, план и т.д.)",
            value=st.session_state.event_data["prompt"],
            key="event_prompt"
        )

        st.subheader("Стиль описания")
        col_style1, col_style2 = st.columns(2)
        with col_style1:
            brief = st.checkbox(
                "Краткий формат",
                value=st.session_state.event_data["style"]["brief"],
                key="brief_style"
            )
        with col_style2:
            formal = st.checkbox(
                "Официальный стиль",
                value=st.session_state.event_data["style"]["formal"],
                key="formal_style"
            )
        st.session_state.event_data["style"]["brief"] = brief
        st.session_state.event_data["style"]["formal"] = formal

        if st.form_submit_button("Сгенерировать название и описание", type="primary"):
            st.session_state.step = "generation"
            st.session_state.attempts = 0
            st.rerun()


def render_generation_step():
    st.subheader("Данные события")
    with st.expander("Просмотр введенных данных", expanded=True):
        st.markdown(format_event_data(st.session_state.event_data))

    if st.session_state.attempts == 0 or st.session_state.feedback:
        with st.spinner("Генерирую название и описание события..."):
            input_data = {
                "event_data": st.session_state.event_data,
                "weather": None,
                "messages": st.session_state.generation_history,
                "final_output": None,
                "user_feedback": st.session_state.feedback
            }

            with open(INPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(input_data, f, ensure_ascii=False, indent=2)

            try:
                docker_cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{os.getcwd()}/data:/data",
                    "-v", f"{os.getcwd()}/config.json:/app/config.json",
                    "event-helper",
                    "/data/input.json"
                ]
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )

                with open(INPUT_FILE, "r", encoding="utf-8") as f:
                    result_data = json.load(f)

                if "error" in result_data:
                    st.error(f"Ошибка генерации: {result_data['error']}")
                    st.session_state.step = "input"
                    st.rerun()

                st.session_state.final_output = result_data["final_output"]
                st.session_state.generation_history = result_data.get("messages", [])
                st.session_state.feedback = ""
                st.session_state.attempts += 1

            except subprocess.CalledProcessError as e:
                st.error(f"Ошибка при выполнении микросервиса: {e.stderr}")
                st.session_state.step = "input"
                st.rerun()
            except Exception as e:
                st.error(f"Неизвестная ошибка: {str(e)}")
                st.session_state.step = "input"
                st.rerun()

    if st.session_state.final_output:
        st.success("Название и описание события успешно сгенерированы!")
        st.subheader("Название события:")
        st.write(st.session_state.final_output["title"])
        st.subheader("Описание события:")
        st.write(st.session_state.final_output["description"])
        st.markdown("---")
        st.write(f"Попытка: {st.session_state.attempts}/{st.session_state.max_attempts}")

        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Принять результат", type="primary"):
                st.session_state.step = "final"
                st.rerun()

        with col2:
            if st.session_state.attempts < st.session_state.max_attempts:
                with st.form("feedback_form"):
                    feedback = st.text_area(
                        "Что нужно изменить? Опишите ваши пожелания:",
                        value=st.session_state.feedback,
                        key="feedback_input"
                    )
                    if st.form_submit_button("Отправить на доработку"):
                        st.session_state.feedback = feedback
                        st.rerun()
            else:
                st.warning("Достигнуто максимальное количество попыток")
                if st.button("Принять текущий результат"):
                    st.session_state.step = "final"
                    st.rerun()

def render_final_step():
    st.success("Финальный результат принят!")
    st.subheader("Название события:")
    st.write(st.session_state.final_output["title"])
    st.subheader("Описание события:")
    st.write(st.session_state.final_output["description"])
    st.markdown("---")

    if st.button("Создать новое событие", type="primary"):
        st.session_state.step = "input"
        st.session_state.attempts = 0
        st.session_state.event_data = {
            "date": str(datetime.date.today()),
            "time": datetime.datetime.now().strftime("%H:%M"),
            "address": "",
            "additional_info": "",
            "prompt": "",
            "style": {"brief": False, "formal": False}
        }
        st.session_state.generation_history = []
        st.session_state.final_output = None
        st.session_state.feedback = ""
        st.rerun()

if __name__ == "__main__":
    main()