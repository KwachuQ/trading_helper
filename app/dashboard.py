import streamlit as st

st.set_page_config(page_title="Trading Analysis", layout="wide")

pg = st.navigation([
    st.Page("pages/1_Info.py", title="Info"),
    st.Page("pages/2_Dashboard.py", title="Dashboard"),
    st.Page("pages/3_Data_Tables.py", title="Data Tables"),
])
pg.run()
