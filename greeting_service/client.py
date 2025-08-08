import streamlit as st
import json
import os
import subprocess
import datetime
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
INPUT_FILE = DATA_DIR / "input.json"
CONFIG_FILE = "config.json"

def main():
    if 'use_current' not in st.session_state:
        st.session_state.use_current = True
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = datetime.date.today()
    if 'selected_time' not in st.session_state:
        st.session_state.selected_time = datetime.datetime.now().time()

    st.markdown(
        "<h1 style='text-align: center;'>Генератор приветствий для Календаря VK WorkSpace</h1>",
        unsafe_allow_html=True
    )

    st.image("greeting_service.jpeg", use_container_width=True)
    st.markdown("Создайте персонализированное приветствие с учетом праздников и времени суток")

    def update_use_current():
        st.session_state.use_current = not st.session_state.use_current

    use_current = st.checkbox(
        "Использовать текущую дату и время",
        value=st.session_state.use_current,
        on_change=update_use_current,
        key="use_current_cb"
    )

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Дата")
            if st.session_state.use_current:
                current_date = datetime.date.today()
                st.date_input(
                    "Выберите дату",
                    value=current_date,
                    disabled=True,
                    key="date_disabled",
                    label_visibility="collapsed"
                )
                st.session_state.selected_date = current_date
            else:
                date = st.date_input(
                    "Выберите дату",
                    value=st.session_state.selected_date,
                    key="date_enabled",
                    label_visibility="collapsed"
                )
                st.session_state.selected_date = date
        with col2:
            st.subheader("Время")
            if st.session_state.use_current:
                current_time = datetime.datetime.now().time()
                st.time_input(
                    "Выберите время",
                    value=current_time,
                    disabled=True,
                    key="time_disabled",
                    label_visibility="collapsed"
                )
                st.session_state.selected_time = current_time
            else:
                time_input = st.time_input(
                    "Выберите время",
                    value=st.session_state.selected_time,
                    key="time_enabled",
                    label_visibility="collapsed"
                )
                st.session_state.selected_time = time_input

    if st.button("Сгенерировать приветствие", type="primary", use_container_width=True):
        date_to_use = st.session_state.selected_date
        time_to_use = st.session_state.selected_time
        input_data = {
            "date": str(date_to_use),
            "time": time_to_use.strftime("%H:%M"),
            "greeting": ""
        }

        with open(INPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(input_data, f, ensure_ascii=False, indent=2)

        with st.spinner("Создаю уникальное приветствие..."):
            try:
                docker_cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{os.getcwd()}/data:/data",
                    "-v", f"{os.getcwd()}/config.json:/app/config.json",
                    "greeting-service",
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

                st.success("Приветствие успешно сгенерировано!")
                st.subheader("Ваше приветствие:")
                st.markdown(f"**{result_data['greeting']}**")
                st.markdown("---")

                if st.button("Сгенерировать новое приветствие", use_container_width=True):
                    st.experimental_rerun()

            except subprocess.CalledProcessError as e:
                st.error("Ошибка при выполнении микросервиса")
                st.code(f"Статус: {e.returncode}\nОшибка: {e.stderr}")
            except FileNotFoundError:
                st.error("Docker не найден")
            except json.JSONDecodeError:
                st.error("Ошибка формата JSON в файле результата")
            except Exception as e:
                st.error(f"Неизвестная ошибка: {str(e)}")

if __name__ == "__main__":
    main()