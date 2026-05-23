import streamlit as st
import pandas as pd
import plotly.express as px
from service.job_service import JobService
from service.storage_adapter import ChromaStorageAdapter
from service.analytics_service import (
    get_area_distribution,
    get_experience_distribution,
    get_top_skills,
    get_top_libraries,
)


def format_plotly_dark(fig):
    fig.update_layout(
        paper_bgcolor="#0f1720",
        plot_bgcolor="#0f1720",
        font_color="#d1fae5",
        legend=dict(font_color="#d1fae5"),
    )
    fig.update_xaxes(showgrid=False, gridcolor="#131a26", zeroline=False, tickfont=dict(color="#d1fae5"))
    fig.update_yaxes(showgrid=False, gridcolor="#131a26", zeroline=False, tickfont=dict(color="#d1fae5"))
    return fig


def flatten_query_results(results):
    rows = []
    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    distances = results.get("distances", [])

    for group_index, metadata_group in enumerate(metadatas):
        distance_group = distances[group_index] if group_index < len(distances) else []
        id_group = ids[group_index] if group_index < len(ids) else []
        for index, metadata in enumerate(metadata_group):
            row = dict(metadata)
            row["distance"] = distance_group[index] if index < len(distance_group) else None
            row["vector_id"] = id_group[index] if index < len(id_group) else None
            rows.append(row)
    return rows


def main():
    st.set_page_config(page_title="ML Job Explorer", layout="wide")
    st.markdown(
        """
        <style>
        .reportview-container { background-color: #0f1720; color: #d1fae5; }
        .stApp { background-color: #0f1720; }
        .css-1d391kg { background-color: #111827; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🧠 ML Job Explorer")
    st.subheader("Dark-mode analytics for machine learning job data")

    storage = ChromaStorageAdapter()
    service = JobService(storage)
    jobs = service.list_jobs(limit=500)
    df = pd.DataFrame(jobs)

    if df.empty:
        st.warning("No jobs are available in the local vector store yet. Run ingestion first.")
        return

    total_jobs = len(df)
    total_sources = df["source"].nunique() if "source" in df.columns else 0
    total_locations = df["location"].nunique() if "location" in df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total jobs", total_jobs, delta=None)
    col2.metric("Sources", total_sources, delta=None)
    col3.metric("Locations", total_locations, delta=None)
    col4.metric("Average experience", "N/A")

    st.markdown("---")

    sidebar_query = st.sidebar.text_input("Vector search query", "machine learning engineer")
    search_top_k = st.sidebar.slider("Top results", 1, 20, 8)
    if st.sidebar.button("Search jobs"):
        results = service.search_jobs(sidebar_query, top_k=search_top_k)
        matched = flatten_query_results(results)
        if matched:
            st.subheader("Search results")
            st.dataframe(pd.DataFrame(matched), use_container_width=True)
        else:
            st.info("No vector search results yielded yet.")

    st.subheader("Area distribution")
    area_data = get_area_distribution(jobs)
    area_df = pd.DataFrame(area_data)
    fig_area = px.bar(area_df, x="category", y="count", color="category", color_discrete_sequence=["#22c55e", "#10b981", "#2dd4bf", "#4ade80", "#86efac"])
    fig_area = format_plotly_dark(fig_area)
    st.plotly_chart(fig_area, use_container_width=True)

    st.subheader("Top skill tags")
    skills_data = get_top_skills(jobs, n=12)
    skills_df = pd.DataFrame(skills_data)
    fig_skills = px.bar(skills_df, x="count", y="value", orientation="h", color="count", color_continuous_scale=["#10b981", "#22c55e"])
    fig_skills = format_plotly_dark(fig_skills)
    st.plotly_chart(fig_skills, use_container_width=True)

    st.subheader("Top libraries and frameworks")
    libs_data = get_top_libraries(jobs, n=12)
    libs_df = pd.DataFrame(libs_data)
    fig_libs = px.bar(libs_df, x="count", y="value", orientation="h", color="count", color_continuous_scale=["#22c55e", "#4ade80"])
    fig_libs = format_plotly_dark(fig_libs)
    st.plotly_chart(fig_libs, use_container_width=True)

    st.subheader("Experience distribution")
    exp_data = get_experience_distribution(jobs)
    exp_df = pd.DataFrame(exp_data)
    fig_exp = px.bar(exp_df, x="bucket", y="count", color="bucket", color_discrete_sequence=["#22c55e", "#10b981", "#2dd4bf", "#5eead4"])
    fig_exp = format_plotly_dark(fig_exp)
    st.plotly_chart(fig_exp, use_container_width=True)

    st.markdown("---")
    st.subheader("Latest jobs")
    if "created_at" in df.columns:
        latest_df = df.sort_values(by="created_at", ascending=False).head(20)
    else:
        latest_df = df.head(20)
    st.dataframe(latest_df[["title", "source", "location", "salary", "tags", "link"]].fillna("N/A"), use_container_width=True)


if __name__ == "__main__":
    main()
