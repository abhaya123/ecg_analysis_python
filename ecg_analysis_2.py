import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objs as go
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
import tempfile, os, json

st.set_page_config(layout="wide")
st.title("🫀 24-hour ECG Review Tool")

uploaded_file = st.file_uploader("Upload ECG CSV file", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Constants
    fs = 200  # Hz
    samples_per_hour = fs * 60 * 60
    total_hours = len(df) // samples_per_hour

    hour_idx = st.number_input("Hour window", 0, total_hours, 0, 1)

    start_idx = hour_idx * samples_per_hour
    end_idx = min(start_idx + samples_per_hour, len(df))
    chunk = df.iloc[start_idx:end_idx]

    # --- Plot ECG ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=chunk["time"], y=chunk["data"],
                             mode="lines", line=dict(width=0.5)))
    fig.update_layout(title=f"ECG Hour {hour_idx}",
                      xaxis_title="Time (s)", yaxis_title="mV",
                      height=400)
    fig.update_yaxes(range=[-1, 1])   # lock amplitude

    # Show plot & capture interactions
    chart = st.plotly_chart(fig, use_container_width=True,
                            key=f"chart-{hour_idx}")

    # Read last interaction from Streamlit state
    if "plotly_relayout" in st.session_state:
        relayout = st.session_state["plotly_relayout"]
    else:
        relayout = {}

    # Allow technician to drag-zoom
    if "xaxis.range[0]" in relayout and "xaxis.range[1]" in relayout:
        start_time = float(relayout["xaxis.range[0]"])
        end_time = float(relayout["xaxis.range[1]"])
        duration = end_time - start_time

        st.subheader("Mark Abnormality")
        st.write(f"Selected range: {start_time:.2f}s → {end_time:.2f}s (Duration {duration:.2f}s)")
        label = st.text_input("Abnormality Label (e.g., PVC, AFib, Pause)")

        if 8 <= duration <= 12:
            if st.button("Save Abnormality"):
                if "annotations" not in st.session_state:
                    st.session_state["annotations"] = []
                st.session_state["annotations"].append({
                    "start_time": start_time,
                    "end_time": end_time,
                    "label": label
                })
                st.success(f"✅ Saved abnormality '{label}' at {start_time:.2f}s – {end_time:.2f}s")
        else:
            st.warning("⚠️ Please select around 10 seconds.")

    # Show saved abnormalities
    if "annotations" in st.session_state:
        st.subheader("Saved Abnormalities")
        st.dataframe(pd.DataFrame(st.session_state["annotations"]))

        # --- PDF Export ---
        if st.button("Generate PDF Report"):
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, "ECG_Report.pdf")
                doc = SimpleDocTemplate(pdf_path, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []

                elements.append(Paragraph("ECG Abnormality Report", styles["Title"]))
                elements.append(Spacer(1, 12))

                table_data = [["Start Time (s)", "End Time (s)", "Label"]]
                for ann in st.session_state["annotations"]:
                    table_data.append([
                        f"{ann['start_time']:.2f}",
                        f"{ann['end_time']:.2f}",
                        ann['label']
                    ])
                elements.append(Table(table_data))
                elements.append(Spacer(1, 24))

                for ann in st.session_state["annotations"]:
                    fig, ax = plt.subplots(figsize=(6, 2))
                    mask = (df["time"] >= ann["start_time"]) & (df["time"] <= ann["end_time"])
                    ax.plot(df[mask]["time"], df[mask]["data"], color="black", linewidth=0.7)
                    ax.set_ylim([-1, 1])
                    ax.set_title(f"{ann['label']} ({ann['start_time']:.2f}-{ann['end_time']:.2f}s)")
                    img_path = os.path.join(tmpdir, "plot.png")
                    fig.savefig(img_path, dpi=150)
                    plt.close(fig)
                    elements.append(Image(img_path, width=400, height=120))
                    elements.append(Spacer(1, 12))

                doc.build(elements)
                with open(pdf_path, "rb") as f:
                    st.download_button("⬇️ Download PDF", f, file_name="ECG_Report.pdf")
