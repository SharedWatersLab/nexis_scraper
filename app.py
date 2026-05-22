import streamlit as st
import os
from utils import get_user, full_process, DEFAULT_START_DATE, DEFAULT_END_DATE

st.title("Nexis-Uni Downloader")

uname = st.text_input("Enter username:")

with open("basins.txt", "r") as f:
    basins = [b.strip() for b in f.readlines()]

chosen_basins = st.multiselect("Select basin code(s):", basins)

col1, col2 = st.columns(2)
with col1:
    start_date = st.text_input("Start date (MM/DD/YYYY):", value=DEFAULT_START_DATE)
with col2:
    end_date = st.text_input("End date (MM/DD/YYYY):", value=DEFAULT_END_DATE)

st.caption(
    "Leave dates at defaults for a full-range download. "
    "For high-volume basins (e.g. GRND), enter a one-year window "
    "(e.g. 06/30/2008 → 06/30/2009) to keep result counts manageable. "
    "Each year window saves into its own subfolder inside the basin folder."
)

if st.button("Start Download"):
    if uname:
        with st.spinner("Downloading..."):
            for basin in chosen_basins:
                paths, username = get_user(basin, uname)
                full_process(basin, username, paths, start_date, end_date)
    else:
        st.error("Please enter a username.")