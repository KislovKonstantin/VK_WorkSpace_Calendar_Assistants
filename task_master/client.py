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
        st.session_state.task_data = {
            "start_date": str(datetime.date.today()),
            "start_time": datetime.datetime.now().strftime("%H:%M"),
            "end_date": str(datetime.date.today()),
            "end_time": (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M"),
            "all_day": False,
            "additional_info": "",
            "prompt": "",
            "style": {"brief": False, "formal": False}
        }
        st.session_state.generation_history = []
        st.session_state.final_output = None
        st.session_state.feedback = ""

def format_task_data(task_data):
    style_map = {
        (True, True): "Краткий и официальный",
        (True, False): "Краткий и неформальный",
        (False, True): "Подробный и официальный",
        (False, False): "Подробный и неформальный"
    }
    style_key = (task_data["style"]["brief"], task_data["style"]["formal"])
    style_text = style_map.get(style_key, "Не определен")

    time_info = ""
    if task_data["all_day"]:
        time_info = f"**Весь день:** {task_data['start_date']}"
    else:
        time_info = (
            f"**Начало:** {task_data['start_date']} {task_data['start_time']}  \n"
            f"**Окончание:** {task_data['end_date']} {task_data['end_time']}"
        )

    parts = [
        time_info,
        f"**Стиль описания:** {style_text}"
    ]

    if task_data["additional_info"]:
        parts.append(f"**Дополнительная информация:**  \n{task_data['additional_info']}")
    if task_data["prompt"]:
        parts.append(f"**Описание задачи:**  \n{task_data['prompt']}")

    return "\n\n".join(parts)

def main():
    init_session_state()
    st.markdown(
        "<h1 style='text-align: center;'>ИИ-ассистент для генерации задач в Календаре VK WorkSpace</h1>",
        unsafe_allow_html=True
    )
    st.image("task_master.png", use_container_width=True)
    st.markdown(
        "<p style='text-align: center;'>Создайте название и описание задачи с помощью ИИ-ассистента</p>",
        unsafe_allow_html=True
    )
    if st.session_state.step == "input":
        render_input_step()
    elif st.session_state.step == "generation":
        render_generation_step()
    elif st.session_state.step == "final":
        render_final_step()

def render_input_step():
    with st.form("task_form"):
        st.subheader("Временные параметры")
        all_day = st.checkbox("Весь день", key="all_day")
        st.session_state.task_data["all_day"] = all_day
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Дата начала",
                value=datetime.datetime.strptime(st.session_state.task_data["start_date"], "%Y-%m-%d").date(),
                key="start_date"
            )
            st.session_state.task_data["start_date"] = str(start_date)
            if not all_day:
                start_time_val = datetime.datetime.strptime(st.session_state.task_data["start_time"], "%H:%M").time()
                start_time = st.time_input(
                    "Время начала",
                    value=start_time_val,
                    key="start_time"
                )
                st.session_state.task_data["start_time"] = start_time.strftime("%H:%M")

        with col2:
            end_date = st.date_input(
                "Дата окончания",
                value=datetime.datetime.strptime(st.session_state.task_data["end_date"], "%Y-%m-%d").date(),
                key="end_date"
            )
            st.session_state.task_data["end_date"] = str(end_date)

            if not all_day:
                end_time_val = datetime.datetime.strptime(st.session_state.task_data["end_time"], "%H:%M").time()
                end_time = st.time_input(
                    "Время окончания",
                    value=end_time_val,
                    key="end_time"
                )
                st.session_state.task_data["end_time"] = end_time.strftime("%H:%M")
        st.session_state.task_data["additional_info"] = st.text_area(
            "Дополнительная информация (ссылки, ресурсы, контакты и т.д.)",
            value=st.session_state.task_data["additional_info"],
            key="additional_info"
        )
        st.session_state.task_data["prompt"] = st.text_area(
            "Опишите задачу своими словами (цель, ожидаемый результат, критерии выполнения и т.д.)",
            value=st.session_state.task_data["prompt"],
            key="task_prompt",
            height=150
        )
        st.subheader("Стиль описания")
        col_style1, col_style2 = st.columns(2)
        with col_style1:
            brief = st.checkbox(
                "Краткий формат",
                value=st.session_state.task_data["style"]["brief"],
                key="brief_style"
            )
        with col_style2:
            formal = st.checkbox(
                "Официальный стиль",
                value=st.session_state.task_data["style"]["formal"],
                key="formal_style"
            )
        st.session_state.task_data["style"]["brief"] = brief
        st.session_state.task_data["style"]["formal"] = formal

        if st.form_submit_button("Сгенерировать название и описание", type="primary"):
            st.session_state.step = "generation"
            st.session_state.attempts = 0
            st.rerun()


def render_generation_step():
    st.subheader("Данные задачи")
    with st.expander("Просмотр введенных данных", expanded=True):
        st.markdown(format_task_data(st.session_state.task_data), unsafe_allow_html=False)

    if st.session_state.attempts == 0 or st.session_state.feedback:
        with st.spinner("Генерирую название и описание задачи..."):
            input_data = {
                "task_data": st.session_state.task_data,
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
                    "task-master",
                    "/data/input.json"
                ]
                process = subprocess.Popen(
                    docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='replace')
                    st.error(f"Ошибка при выполнении микросервиса: {error_msg}")
                    st.session_state.step = "input"
                    st.rerun()

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

            except Exception as e:
                st.error(f"Неизвестная ошибка: {str(e)}")
                st.session_state.step = "input"
                st.rerun()

    if st.session_state.final_output:
        st.success("Название и описание задачи успешно сгенерированы!")
        st.subheader("Название задачи:")
        st.write(st.session_state.final_output["title"])
        st.subheader("Описание задачи:")
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
    st.subheader("Название задачи:")
    st.write(st.session_state.final_output["title"])
    st.subheader("Описание задачи:")
    st.write(st.session_state.final_output["description"])
    st.markdown("---")

    if st.button("Создать новую задачу", type="primary"):
        st.session_state.step = "input"
        st.session_state.attempts = 0
        st.session_state.task_data = {
            "start_date": str(datetime.date.today()),
            "start_time": datetime.datetime.now().strftime("%H:%M"),
            "end_date": str(datetime.date.today()),
            "end_time": (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%H:%M"),
            "all_day": False,
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