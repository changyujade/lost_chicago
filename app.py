from __future__ import annotations

import html
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components


APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR / "Lost_Chicago.csv"
CHICAGO_CENTER = {"lat": 41.8781, "lng": -87.6298}


st.set_page_config(
    page_title="Lost Chicago Map",
    page_icon="map",
    layout="wide",
)


def clean_text(value: object, fallback: str = "Unknown") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def format_year(value: object) -> str:
    if pd.isna(value):
        return "Unknown"
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return clean_text(value)


def normalize_category(value: object, fallback: str = "Unknown") -> str:
    text = clean_text(value, fallback)
    normalized = " ".join(text.replace("/", " / ").split())
    replacements = {
        "Executive / Legislative Action": "Executive / Legislative Action",
        "Executive/Legislative Action": "Executive / Legislative Action",
        "Public housing policy": "Public Housing Policy",
        "Urban renewal": "Urban Renewal",
    }
    return replacements.get(normalized, normalized)


@st.cache_data
def load_lost_chicago() -> pd.DataFrame:
    data = pd.read_csv(DATA_PATH)
    data.columns = data.columns.str.strip()
    data["lat"] = pd.to_numeric(data["lat"], errors="coerce")
    data["lon"] = pd.to_numeric(data["lon"], errors="coerce")
    data["year built"] = pd.to_numeric(data["year built"], errors="coerce")
    data["year demolished"] = pd.to_numeric(data["year demolished"], errors="coerce")
    return data


def marker_payload(data: pd.DataFrame) -> list[dict[str, object]]:
    markers: list[dict[str, object]] = []

    for _, row in data.iterrows():
        source = clean_text(row.get("source"), "")
        source_html = ""
        if source:
            if source.startswith(("http://", "https://")):
                safe_source = html.escape(source, quote=True)
                source_html = f'<a href="{safe_source}" target="_blank" rel="noopener">Source</a>'
            else:
                source_html = html.escape(source)

        description = clean_text(row.get("Description/Comments"), "")
        details = [
            ("Neighborhood", clean_text(row.get("neighborhood"))),
            ("Type", clean_text(row.get("type"))),
            ("Built", format_year(row.get("year built"))),
            ("Demolished", format_year(row.get("year demolished"))),
            ("Cause", clean_text(row.get("cause"))),
            ("Replacement", clean_text(row.get("replacement"))),
        ]

        detail_html = "".join(
            f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
            for label, value in details
            if value != "Unknown"
        )

        content = f"""
            <article class="info-window">
                <h2>{html.escape(clean_text(row.get("name"), "Lost Chicago site"))}</h2>
                <dl>{detail_html}</dl>
                {f'<p>{html.escape(description)}</p>' if description else ''}
                {f'<footer>{source_html}</footer>' if source_html else ''}
            </article>
        """

        markers.append(
            {
                "title": clean_text(row.get("name"), "Lost Chicago site"),
                "lat": float(row["lat"]),
                "lng": float(row["lon"]),
                "type": clean_text(row.get("type")),
                "content": content,
            }
        )

    return markers


def google_map_html(api_key: str, markers: list[dict[str, object]]) -> str:
    markers_json = json.dumps(markers)
    center_json = json.dumps(CHICAGO_CENTER)

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <style>
        html, body, #map {{
          height: 100%;
          margin: 0;
          width: 100%;
          font-family: Arial, sans-serif;
        }}

        .info-window {{
          max-width: 310px;
          color: #111827;
          line-height: 1.35;
        }}

        .info-window h2 {{
          font-size: 18px;
          margin: 0 0 10px;
        }}

        .info-window dl {{
          display: grid;
          grid-template-columns: 92px 1fr;
          gap: 5px 10px;
          margin: 0 0 10px;
        }}

        .info-window dt {{
          color: #6b7280;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
        }}

        .info-window dd {{
          margin: 0;
          font-size: 13px;
        }}

        .info-window p {{
          border-top: 1px solid #e5e7eb;
          margin: 10px 0 0;
          padding-top: 10px;
        }}

        .info-window footer {{
          margin-top: 10px;
        }}

        .info-window a {{
          color: #2563eb;
          font-weight: 700;
          text-decoration: none;
        }}
      </style>
      <script>
        const LOST_CHICAGO_MARKERS = {markers_json};
        const CHICAGO_CENTER = {center_json};

        function initMap() {{
          const map = new google.maps.Map(document.getElementById("map"), {{
            center: CHICAGO_CENTER,
            zoom: 11,
            mapTypeControl: true,
            streetViewControl: true,
            fullscreenControl: true,
          }});

          const infoWindow = new google.maps.InfoWindow();
          const bounds = new google.maps.LatLngBounds();

          LOST_CHICAGO_MARKERS.forEach((site) => {{
            const position = {{ lat: site.lat, lng: site.lng }};
            const marker = new google.maps.Marker({{
              position,
              map,
              title: site.title,
            }});

            marker.addListener("click", () => {{
              infoWindow.setContent(site.content);
              infoWindow.open({{ anchor: marker, map }});
            }});

            bounds.extend(position);
          }});

          if (LOST_CHICAGO_MARKERS.length > 1) {{
            map.fitBounds(bounds, 42);
          }}
        }}
      </script>
      <script async defer src="https://maps.googleapis.com/maps/api/js?key={html.escape(api_key, quote=True)}&callback=initMap"></script>
    </head>
    <body>
      <div id="map"></div>
    </body>
    </html>
    """


def google_maps_api_key() -> str:
    secret_key = ""
    try:
        secret_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
    except FileNotFoundError:
        pass
    except st.errors.StreamlitSecretNotFoundError:
        pass

    return os.getenv("GOOGLE_MAPS_API_KEY", secret_key)


def structure_breakdown(data: pd.DataFrame) -> pd.DataFrame:
    breakdown = data.assign(
        structure_type=data["type"].map(normalize_category),
        loss_cause=data["cause"].map(normalize_category),
    )

    return (
        breakdown.groupby(["structure_type", "loss_cause"], dropna=False)
        .size()
        .reset_index(name="places")
        .sort_values(["places", "structure_type", "loss_cause"], ascending=[False, True, True])
    )


def cause_of_loss_breakdown(data: pd.DataFrame, period: str) -> pd.DataFrame:
    demolished = data.dropna(subset=["year demolished"]).copy()
    if demolished.empty:
        return pd.DataFrame(columns=["period", "loss_cause", "demolitions"])

    demolished["year_demolished"] = demolished["year demolished"].astype(int)
    demolished["loss_cause"] = demolished["cause"].map(normalize_category)

    if period == "Year":
        demolished["period"] = demolished["year_demolished"].astype(str)
    else:
        decades = (demolished["year_demolished"] // 10) * 10
        demolished["period"] = decades.astype(str) + "s"

    return (
        demolished.groupby(["period", "loss_cause"], dropna=False)
        .size()
        .reset_index(name="demolitions")
        .sort_values(["period", "loss_cause"])
    )


data = load_lost_chicago()

st.title("Lost Chicago Places")
st.caption("Demolished, transformed, or vanished Chicago places from Lost_Chicago.csv.")

with st.sidebar:
    st.header("Map controls")
    api_key = st.text_input(
        "Google Maps API key",
        value=google_maps_api_key(),
        type="password",
        help="You can also set GOOGLE_MAPS_API_KEY in your environment or Streamlit secrets.",
    )

    types = sorted(data["type"].dropna().unique())
    neighborhoods = sorted(data["neighborhood"].dropna().unique())

    selected_types = st.multiselect("Type", types, default=types)
    selected_neighborhoods = st.multiselect(
        "Neighborhood",
        neighborhoods,
        default=neighborhoods,
    )

    min_year = int(data["year demolished"].min())
    max_year = int(data["year demolished"].max())
    year_range = st.slider(
        "Year demolished",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
    )
    include_unknown_years = st.checkbox("Include unknown demolition years", value=True)
    loss_period = st.radio(
        "Cause of loss time scale",
        ["Decade", "Year"],
        horizontal=True,
    )

year_matches = data["year demolished"].between(year_range[0], year_range[1], inclusive="both")
if include_unknown_years:
    year_matches = year_matches | data["year demolished"].isna()

filtered = data[data["type"].isin(selected_types) & data["neighborhood"].isin(selected_neighborhoods) & year_matches]

mapped = filtered.dropna(subset=["lat", "lon"]).copy()
unmapped = filtered[filtered[["lat", "lon"]].isna().any(axis=1)].copy()

metric_1, metric_2, metric_3 = st.columns(3)
metric_1.metric("Filtered places", len(filtered))
metric_2.metric("Mapped pins", len(mapped))
metric_3.metric("Missing coordinates", len(unmapped))

st.subheader("Structure Type Breakdown")
breakdown = structure_breakdown(filtered)

if breakdown.empty:
    st.info("No structure types match the current filters.")
else:
    sunburst = px.sunburst(
        breakdown,
        path=[px.Constant("Lost Chicago"), "structure_type", "loss_cause"],
        values="places",
        color="structure_type",
        hover_data={"places": ":,", "structure_type": False, "loss_cause": False},
        labels={
            "structure_type": "Structure type",
            "loss_cause": "Cause",
            "places": "Lost places",
        },
    )
    sunburst.update_traces(
        branchvalues="total",
        hovertemplate="<b>%{label}</b><br>Lost places: %{value}<br>Share of parent: %{percentParent:.1%}<extra></extra>",
        insidetextorientation="radial",
    )
    sunburst.update_layout(
        margin=dict(t=10, r=10, b=10, l=10),
        height=560,
        uniformtext=dict(minsize=11, mode="hide"),
    )
    st.plotly_chart(sunburst, width="stretch")

    with st.expander("Structure type counts", expanded=False):
        st.dataframe(
            breakdown.rename(
                columns={
                    "structure_type": "Structure type",
                    "loss_cause": "Cause",
                    "places": "Lost places",
                }
            ),
            width="stretch",
            hide_index=True,
        )

st.subheader("Cause of Loss Over Time")
loss_breakdown = cause_of_loss_breakdown(filtered, loss_period)

if loss_breakdown.empty:
    st.info("No demolition years match the current filters.")
else:
    loss_chart = px.bar(
        loss_breakdown,
        x="period",
        y="demolitions",
        color="loss_cause",
        labels={
            "period": "Year demolished" if loss_period == "Year" else "Decade demolished",
            "demolitions": "Number of demolitions",
            "loss_cause": "Cause of demolition",
        },
        hover_data={"period": False, "loss_cause": False, "demolitions": ":,"},
    )
    loss_chart.update_traces(
        hovertemplate=(
            "<b>%{fullData.name}</b><br>"
            + ("Year" if loss_period == "Year" else "Decade")
            + ": %{x}<br>Demolitions: %{y}<extra></extra>"
        )
    )
    loss_chart.update_layout(
        barmode="stack",
        height=460,
        legend_title_text="Cause of demolition",
        margin=dict(t=20, r=10, b=10, l=10),
        xaxis=dict(type="category", categoryorder="category ascending"),
        yaxis=dict(dtick=1, rangemode="tozero"),
    )
    st.plotly_chart(loss_chart, width="stretch")

    with st.expander("Cause of loss counts", expanded=False):
        st.dataframe(
            loss_breakdown.rename(
                columns={
                    "period": "Year" if loss_period == "Year" else "Decade",
                    "loss_cause": "Cause of demolition",
                    "demolitions": "Demolitions",
                }
            ),
            width="stretch",
            hide_index=True,
        )

if not api_key:
    st.warning(
        "Add a Google Maps API key in the sidebar to load the map. "
        "The app is ready to plot every row with valid lat/lon coordinates."
    )
elif mapped.empty:
    st.warning("No rows with coordinates match the current filters.")
else:
    components.html(
        google_map_html(api_key, marker_payload(mapped)),
        height=700,
        scrolling=False,
    )

with st.expander("Mapped place data", expanded=False):
    st.dataframe(
        mapped[
            [
                "name",
                "neighborhood",
                "type",
                "year built",
                "year demolished",
                "lat",
                "lon",
                "cause",
                "replacement",
                "source",
                "Description/Comments",
                "Contributor",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

if not unmapped.empty:
    with st.expander("Rows missing coordinates", expanded=True):
        st.dataframe(
            unmapped[
                [
                    "name",
                    "neighborhood",
                    "type",
                    "year built",
                    "year demolished",
                    "cause",
                    "replacement",
                    "source",
                    "Description/Comments",
                    "Contributor",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
