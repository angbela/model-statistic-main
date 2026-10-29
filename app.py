from __future__ import annotations

import hashlib
import io
import re
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st


st.set_page_config(page_title="Marine Data Statistics", page_icon="🌊", layout="wide")

DATA_TYPES = {
    "Water Levels": {
        "primary": "Water Level (m)",
        "associated": [],
    },
    "Currents": {
        "primary": "Current Speed (m/s)",
        "associated": [
            ("data_2", "Current X component"),
            ("data_3", "Current Y component"),
        ],
    },
    "Waves": {
        "primary": "Wave Height (m)",
        "associated": [
            ("data_2", "Wave Period (s)"),
            ("data_3", "Wave Direction (° coming from)"),
        ],
    },
}
COMPASS_DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@st.cache_data(show_spinner=False)
def read_uploaded_file(
    content: bytes,
    extension: str,
    sheet_name: str | None,
    has_header: bool,
) -> pd.DataFrame:
    """Read an uploaded CSV or Excel worksheet."""
    header = 0 if has_header else None
    file_buffer = io.BytesIO(content)

    if extension == ".csv":
        return pd.read_csv(file_buffer, header=header, sep=None, engine="python")
    if extension == ".xlsx":
        return pd.read_excel(
            file_buffer,
            sheet_name=sheet_name,
            header=header,
            engine="openpyxl",
        )
    raise ValueError("Unsupported file type. Please upload a .csv or .xlsx file.")


def column_letter_to_index(column_letter: str) -> int:
    """Convert an Excel-style column label (A, B, ..., AA) to a zero-based index."""
    label = column_letter.strip().upper()
    if not re.fullmatch(r"[A-Z]+", label):
        raise ValueError(f'"{column_letter}" is not a valid column letter.')

    index = 0
    for character in label:
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def selected_column(
    data: pd.DataFrame,
    column_letter: str,
    field_name: str,
) -> pd.Series:
    index = column_letter_to_index(column_letter)
    if index >= len(data.columns):
        raise ValueError(
            f"{field_name} uses column {column_letter.upper()}, but the file only "
            f"has {len(data.columns)} column(s)."
        )
    return data.iloc[:, index]


def parse_dates(values: pd.Series) -> pd.Series:
    """Parse day-first dates, including timestamps whose time uses periods."""
    normalized = values.astype("string").str.replace(
        r"(\s+\d{1,2})\.(\d{2})(?:\.(\d{2}))?$",
        lambda match: (
            f"{match.group(1)}:{match.group(2)}"
            + (f":{match.group(3)}" if match.group(3) else "")
        ),
        regex=True,
    )
    return pd.to_datetime(normalized, format="mixed", dayfirst=True, errors="coerce")


def format_value(value: Any) -> str:
    if pd.isna(value):
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value)


def compass_direction(degrees: pd.Series) -> pd.Series:
    sectors = np.floor((degrees % 360 + 22.5) / 45).astype("Int64") % 8
    labels = pd.Series(pd.NA, index=degrees.index, dtype="string")
    valid = degrees.notna()
    labels.loc[valid] = sectors.loc[valid].map(
        lambda index: COMPASS_DIRECTIONS[index]
    )
    return labels


def compass_name(degrees: pd.Series) -> pd.Series:
    names = {
        "N": "North",
        "NE": "Northeast",
        "E": "East",
        "SE": "Southeast",
        "S": "South",
        "SW": "Southwest",
        "W": "West",
        "NW": "Northwest",
    }
    return compass_direction(degrees).map(names)


def percentage_distribution(counts: pd.DataFrame) -> pd.DataFrame:
    """Return a contingency table with row, column, and grand totals in percent."""
    if counts.to_numpy().sum() == 0:
        return pd.DataFrame()
    percentages = counts.astype(float) / counts.to_numpy().sum() * 100
    percentages["Total"] = percentages.sum(axis=1)
    total_row = percentages.drop(columns="Total").sum(axis=0)
    total_row["Total"] = 100.0
    percentages.loc["Total"] = total_row
    return percentages


def bin_labels(edges: np.ndarray, unit: str) -> list[str]:
    labels = []
    for lower, upper in zip(edges[:-1], edges[1:]):
        upper_text = f"{upper:g}"
        if upper == edges[-1]:
            labels.append(f"{lower:g}–{upper_text} {unit} (inclusive)")
        else:
            labels.append(f"{lower:g}–<{upper_text} {unit}")
    return labels


st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        background: #f3f8fa;
        border: 1px solid #dce8ed;
        padding: 1rem 1.15rem;
        border-radius: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌊 Marine Data Statistics")
st.markdown(
    "Explore water-level, current, and wave observations. Upload a file, map its "
    "columns, and run a time-series summary."
)

st.sidebar.header("1. Import data")
uploaded_file = st.sidebar.file_uploader(
    "Choose a data file",
    type=["csv", "xlsx"],
    help="Supported formats: comma-separated CSV and Excel workbooks (.xlsx).",
)

if uploaded_file is None:
    st.info("Upload a .csv or .xlsx file in the sidebar to get started.")
    st.stop()

extension = "." + uploaded_file.name.rsplit(".", 1)[-1].lower()
file_content = uploaded_file.getvalue()
file_signature = hashlib.sha256(file_content).hexdigest()

has_header = st.sidebar.checkbox("First row contains column names", value=True)
sheet_name: str | None = None

if extension == ".xlsx":
    try:
        workbook = pd.ExcelFile(io.BytesIO(file_content), engine="openpyxl")
        sheet_name = st.sidebar.selectbox("Worksheet", workbook.sheet_names)
    except Exception as error:
        st.error(f"Could not read the Excel workbook: {error}")
        st.stop()

try:
    source_data = read_uploaded_file(file_content, extension, sheet_name, has_header)
except Exception as error:
    st.error(f"Could not read the uploaded file: {error}")
    st.stop()

if source_data.empty or len(source_data.columns) == 0:
    st.error("The uploaded file does not contain any data columns or rows.")
    st.stop()

st.sidebar.header("2. Identify data")
location_name = st.sidebar.text_input("Location Name", value="")
data_type = st.sidebar.radio("Data type", list(DATA_TYPES))
field_definitions = DATA_TYPES[data_type]
date_column = st.sidebar.text_input("Column of Date", value="A", max_chars=3)
data_1_column = st.sidebar.text_input(
    f"Column of Data 1 ({field_definitions['primary']})",
    value="B",
    max_chars=3,
)

associated_columns: dict[str, str] = {}
for key, label in field_definitions["associated"]:
    default_column = {"data_2": "C", "data_3": "D"}[key]
    associated_columns[key] = st.sidebar.text_input(
        f"Column of {key.replace('_', ' ').title()} ({label})",
        value=default_column,
        max_chars=3,
    )

input_signature = (
    file_signature,
    extension,
    sheet_name,
    has_header,
    location_name.strip(),
    data_type,
    date_column,
    data_1_column,
    *associated_columns.values(),
)
if st.session_state.get("input_signature") != input_signature:
    st.session_state.input_signature = input_signature
    st.session_state.analysis = None

st.sidebar.caption("Enter Excel-style column letters, such as A, B, or AA.")
run_analysis = st.sidebar.button(
    "Run Analysis",
    type="primary",
    use_container_width=True,
)

with st.expander("Preview uploaded data", expanded=st.session_state.get("analysis") is None):
    st.caption(f"{uploaded_file.name} · {len(source_data):,} rows · {len(source_data.columns)} columns")
    st.dataframe(source_data.head(10), use_container_width=True)

if run_analysis:
    st.session_state.analysis = None
    try:
        mapped_columns = {
            "Date": date_column,
            field_definitions["primary"]: data_1_column,
            **{
                label: associated_columns[key]
                for key, label in field_definitions["associated"]
            },
        }
        column_indexes = {
            name: column_letter_to_index(letter)
            for name, letter in mapped_columns.items()
        }
        if len(set(column_indexes.values())) != len(column_indexes):
            raise ValueError("Each measurement must use a different column.")

        selected_data = pd.DataFrame(index=source_data.index)
        selected_data["Date"] = parse_dates(
            selected_column(source_data, date_column, "Date")
        )
        primary_label = field_definitions["primary"]
        selected_data[primary_label] = pd.to_numeric(
            selected_column(source_data, data_1_column, primary_label),
            errors="coerce",
        )
        for key, label in field_definitions["associated"]:
            associated_values = selected_column(
                source_data,
                associated_columns[key],
                label,
            )
            if data_type == "Water Levels":
                selected_data[label] = associated_values
            else:
                selected_data[label] = pd.to_numeric(associated_values, errors="coerce")

        if data_type == "Currents":
            x_component = selected_data["Current X component"]
            y_component = selected_data["Current Y component"]
            direction_valid = x_component.notna() & y_component.notna()
            direction_degrees = pd.Series(np.nan, index=selected_data.index)
            nonzero_vectors = direction_valid & ((x_component != 0) | (y_component != 0))
            direction_degrees.loc[nonzero_vectors] = (
                np.degrees(
                    np.arctan2(
                        x_component.loc[nonzero_vectors],
                        y_component.loc[nonzero_vectors],
                    )
                )
                % 360
            )
            selected_data["Current Direction (° towards)"] = direction_degrees
            selected_data["Current Direction (compass, towards)"] = compass_name(
                direction_degrees
            )
        elif data_type == "Waves":
            wave_direction = "Wave Direction (° coming from)"
            selected_data["Wave Direction (compass, coming from)"] = compass_name(
                selected_data[wave_direction] % 360
            )

        if data_type == "Currents":
            selected_data = selected_data.drop(
                columns=["Current X component", "Current Y component"]
            )

        selected_data["Timestep"] = selected_data.index.to_series() + 1
        valid_rows = selected_data["Date"].notna() & selected_data[primary_label].notna()
        excluded_rows = int((~valid_rows).sum())
        analysis_data = selected_data.loc[valid_rows].copy()
        if analysis_data.empty:
            raise ValueError(
                "No usable rows were found. Check the date and primary-data "
                "columns and make sure they contain valid values."
            )

        max_index = analysis_data[primary_label].idxmax()
        min_index = analysis_data[primary_label].idxmin()
        maximum = analysis_data.loc[max_index]
        minimum = analysis_data.loc[min_index]
        average = analysis_data[primary_label].mean()
        if data_type == "Currents":
            associated_labels = [
                "Current Direction (° towards)",
                "Current Direction (compass, towards)",
            ]
        elif data_type == "Waves":
            associated_labels = [
                "Wave Period (s)",
                "Wave Direction (° coming from)",
                "Wave Direction (compass, coming from)",
            ]
        else:
            associated_labels = []

        summary_rows = []
        for statistic, row, value in (
            ("Maximum", maximum, maximum[primary_label]),
            ("Average", None, average),
            ("Minimum", minimum, minimum[primary_label]),
        ):
            summary_row: dict[str, Any] = {
                "Statistic": statistic,
                primary_label: value,
                "Timestep": int(row["Timestep"]) if row is not None else "—",
                "Date": row["Date"] if row is not None else "—",
            }
            for label in associated_labels:
                summary_row[label] = row[label] if row is not None else "—"
            summary_rows.append(summary_row)

        summary_columns = [
            "Statistic",
            primary_label,
            *associated_labels,
            "Timestep",
            "Date",
        ]
        st.session_state.analysis = {
            "location_name": location_name.strip(),
            "data_type": data_type,
            "primary_label": primary_label,
            "associated_labels": associated_labels,
            "data": analysis_data,
            "summary": pd.DataFrame(
                summary_rows,
                columns=summary_columns,
            ).round(2),
            "excluded_rows": excluded_rows,
        }
    except (TypeError, ValueError, IndexError) as error:
        st.error(f"Could not run the analysis: {error}")

analysis = st.session_state.get("analysis")
if analysis is None:
    st.caption(
        "Map the date and measurement columns in the sidebar, then select "
        "**Run Analysis**."
    )
    st.stop()

st.subheader(f"{analysis['data_type']} results")

result_data = analysis["data"]
primary_label = analysis["primary_label"]
location_name = analysis["location_name"]
if location_name:
    st.caption(f"Location: {location_name}")
maximum_value = result_data[primary_label].max()
average_value = result_data[primary_label].mean()
minimum_value = result_data[primary_label].min()

st.markdown("#### Summary and associated observations")
st.caption(
    "Maximum and minimum rows include their original data timestep and associated "
    "measurements. The average is calculated only for the primary measurement."
)
st.dataframe(
    analysis["summary"].style.format(precision=2),
    hide_index=True,
    use_container_width=True,
)

st.markdown("#### Time series")
plot_data = result_data.sort_values("Date")
figure, axis = plt.subplots(figsize=(12, 5))
axis.plot(
    plot_data["Date"],
    plot_data[primary_label],
    color="red",
    linewidth=2.4,
    label="Observed",
)
axis.set_ylabel(primary_label)
axis.set_title(f"{primary_label} Time Series")
axis.set_xlabel("Date and time")
axis.legend(frameon=False, handlelength=3)
axis.grid(False)
figure.autofmt_xdate()
figure.tight_layout()
st.pyplot(figure, use_container_width=True)
plt.close(figure)

if analysis["data_type"] == "Currents":
    st.markdown("#### Current rose")
    rose_data = result_data["Current Direction (° towards)"].dropna()
    if rose_data.empty:
        st.info("A current rose cannot be shown because there are no valid non-zero current vectors.")
    else:
        sector_indexes = np.floor((rose_data % 360 + 22.5) / 45).astype(int) % 8
        sector_percentages = (
            pd.Series(sector_indexes)
            .value_counts(normalize=True)
            .reindex(range(8), fill_value=0)
            .sort_index()
            .to_numpy()
            * 100
        )
        figure, axis = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"})
        bar_angles = np.deg2rad(np.arange(8) * 45)
        axis.bar(
            bar_angles,
            sector_percentages,
            width=np.deg2rad(45),
            color="#159eaa",
            edgecolor="white",
            linewidth=1,
        )
        axis.set_theta_zero_location("N")
        axis.set_theta_direction(-1)
        axis.set_xticks(bar_angles, COMPASS_DIRECTIONS)
        axis.set_ylabel("Observations (%)")
        axis.set_title("Current Direction (° towards)")
        axis.grid(alpha=0.3)
        figure.tight_layout()
        st.pyplot(figure, use_container_width=True)
        plt.close(figure)

if analysis["data_type"] == "Waves":
    direction_distribution = pd.DataFrame()
    height_distribution = pd.DataFrame()
    scatter_distribution = pd.DataFrame()
    st.markdown("#### Monthly wave-direction distribution")
    direction_column = "Wave Direction (° coming from)"
    direction_data = result_data.dropna(subset=["Date", direction_column]).copy()
    if not direction_data.empty:
        direction_data["Month"] = pd.Categorical(
            direction_data["Date"].dt.month_name(),
            categories=MONTHS,
            ordered=True,
        )
        direction_data["Direction"] = compass_direction(
            direction_data[direction_column] % 360
        )
        direction_counts = pd.crosstab(
            direction_data["Month"],
            direction_data["Direction"],
        ).reindex(index=MONTHS, columns=COMPASS_DIRECTIONS, fill_value=0)
        direction_distribution = percentage_distribution(direction_counts)
        st.caption(
            "Each cell and its row/column totals are percentages of all observations "
            "with a valid wave direction."
        )
        if direction_distribution.empty:
            st.info("No valid wave directions are available for the distribution.")
        else:
            st.dataframe(
                direction_distribution.style.format("{:.2f}%"),
                use_container_width=True,
            )
    else:
        st.info("No valid wave directions are available for the distribution.")

    st.markdown("#### Monthly wave-height distribution")
    height_data = result_data.dropna(subset=["Date", "Wave Height (m)"]).copy()
    height_data = height_data.loc[height_data["Wave Height (m)"] >= 0]
    height_categories = ["0–0.5 m", "0.5–1.0 m", ">1.0 m"]
    if not height_data.empty:
        height_data["Month"] = pd.Categorical(
            height_data["Date"].dt.month_name(),
            categories=MONTHS,
            ordered=True,
        )
        height_data["Height range"] = pd.cut(
            height_data["Wave Height (m)"],
            bins=[-np.inf, 0.5, 1.0, np.inf],
            labels=height_categories,
            right=True,
        )
        height_counts = pd.crosstab(
            height_data["Month"],
            height_data["Height range"],
        ).reindex(index=MONTHS, columns=height_categories, fill_value=0)
        height_distribution = percentage_distribution(height_counts)
        st.caption(
            "Each cell and its row/column totals are percentages of all observations "
            "with a valid, non-negative wave height."
        )
        st.dataframe(
            height_distribution.style.format("{:.2f}%"),
            use_container_width=True,
        )
    else:
        st.info("No valid non-negative wave heights are available for the distribution.")

    st.markdown("#### Wave scatter diagram")
    scatter_data = result_data.dropna(
        subset=["Wave Height (m)", "Wave Period (s)"]
    ).copy()
    scatter_data = scatter_data.loc[
        (scatter_data["Wave Height (m)"] >= 0)
        & (scatter_data["Wave Period (s)"] >= 0)
    ]
    if scatter_data.empty:
        st.info("A wave scatter diagram needs valid, non-negative heights and periods.")
    else:
        height_step = 0.5
        period_step = 1.0
        height_limit = max(
            height_step,
            np.ceil(scatter_data["Wave Height (m)"].max() / height_step) * height_step,
        )
        period_limit = max(
            period_step,
            np.ceil(scatter_data["Wave Period (s)"].max() / period_step) * period_step,
        )
        height_edges = np.arange(0, height_limit + height_step, height_step)
        period_edges = np.arange(0, period_limit + period_step, period_step)
        counts, _, _ = np.histogram2d(
            scatter_data["Wave Period (s)"],
            scatter_data["Wave Height (m)"],
            bins=[period_edges, height_edges],
        )
        occurrence = counts / counts.sum() * 100
        height_labels = bin_labels(height_edges, "m")
        period_labels = bin_labels(period_edges, "s")
        scatter_distribution = pd.DataFrame(
            occurrence.T,
            index=height_labels,
            columns=period_labels,
        )
        scatter_distribution.index.name = "Wave height"
        scatter_distribution.columns.name = "Wave period"

        figure, axis = plt.subplots(
            figsize=(max(8, len(period_labels) * 0.75), max(5, len(height_labels) * 0.55))
        )
        image = axis.imshow(
            occurrence.T,
            origin="lower",
            aspect="auto",
            cmap="YlGnBu",
        )
        axis.set_xticks(range(len(period_labels)), period_labels, rotation=45, ha="right")
        axis.set_yticks(range(len(height_labels)), height_labels)
        axis.set_xlabel("Wave period")
        axis.set_ylabel("Wave height")
        axis.set_title("Wave Height–Period Occurrence")
        colorbar = figure.colorbar(image, ax=axis)
        colorbar.set_label("Observations (%)")
        for height_index in range(occurrence.shape[1]):
            for period_index in range(occurrence.shape[0]):
                value = occurrence[period_index, height_index]
                if value > 0:
                    axis.text(
                        period_index,
                        height_index,
                        f"{value:.2f}%",
                        ha="center",
                        va="center",
                        color="white" if value >= occurrence.max() * 0.55 else "black",
                        fontsize=8,
                    )
        figure.tight_layout()
        st.pyplot(figure, use_container_width=True)
        plt.close(figure)

st.markdown("#### Download")
safe_location = re.sub(r"[^\w.-]+", "-", location_name, flags=re.UNICODE).strip("-.")
safe_location = safe_location or "location"
export_data = result_data.copy()
numeric_export_columns = export_data.select_dtypes(include="number").columns
export_data[numeric_export_columns] = export_data[numeric_export_columns].round(2)
export_data.insert(0, "Location Name", location_name)
excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    export_data.to_excel(writer, sheet_name="Time series", index=False)
    analysis["summary"].round(2).to_excel(
        writer,
        sheet_name="Statistics",
        index=False,
    )
    if analysis["data_type"] == "Waves":
        if not direction_distribution.empty:
            direction_distribution.round(2).to_excel(
                writer,
                sheet_name="Wave direction",
            )
        if not height_distribution.empty:
            height_distribution.round(2).to_excel(
                writer,
                sheet_name="Monthly heights",
            )
        if not scatter_distribution.empty:
            scatter_distribution.round(2).to_excel(
                writer,
                sheet_name="Wave scatter",
            )

download_columns = st.columns(2)
download_columns[0].download_button(
    "Download results (.xlsx)",
    data=excel_buffer.getvalue(),
    file_name=f"{safe_location}-marine-data-statistics.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
download_columns[1].download_button(
    "Download time series (.csv)",
    data=export_data.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"{safe_location}-marine-data-timeseries.csv",
    mime="text/csv",
    use_container_width=True,
)
