from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="EdgeSense-MA", layout="wide")

st.title("EdgeSense-MA")
st.caption(
    "Multi-Agent Multimodal AI at the Edge - Raspberry Pi 5 - "
    "Real BME280 + Real MQ-135 + Audio + Vision + Reasoning"
)

st.divider()


def api_get(path: str, timeout: int = 30) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, timeout: int = 35) -> dict:
    response = requests.post(f"{API_BASE}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def risk_badge(risk: str) -> str:
    colors = {
        "LOW": "#22c55e",
        "MEDIUM": "#f59e0b",
        "HIGH": "#ef4444",
        "UNKNOWN": "#94a3b8",
    }
    color = colors.get(risk, colors["UNKNOWN"])
    return f"""
    <div style="
        display:inline-block;
        padding: 10px 18px;
        border-radius: 14px;
        background-color: {color};
        color: #0f172a;
        font-size: 28px;
        font-weight: 800;
        letter-spacing: 1px;
    ">
        {risk}
    </div>
    """


def level_badge(level: str) -> str:
    colors = {
        "normal": "#22c55e",
        "warning": "#f59e0b",
        "critical": "#ef4444",
    }
    color = colors.get(str(level).lower(), "#94a3b8")
    return f"""
    <div style="
        display:inline-block;
        padding: 8px 14px;
        border-radius: 12px;
        background-color: {color};
        color: #0f172a;
        font-size: 22px;
        font-weight: 800;
    ">
        {level}
    </div>
    """


def service_badge(status: str) -> str:
    color = "#22c55e" if status == "online" else "#ef4444"
    return f"""
    <span style="
        display:inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        background-color: {color};
        color: #0f172a;
        font-weight: 700;
    ">
        {status}
    </span>
    """


def parse_utc_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def calculate_cache_age_seconds(value: object) -> float | None:
    timestamp = parse_utc_datetime(value)

    if timestamp is None:
        return None

    age = datetime.now(timezone.utc) - timestamp
    return max(0.0, age.total_seconds())


def render_worker_health(snapshot_data: dict) -> None:
    worker = snapshot_data.get("worker") or {}
    source = (
        snapshot_data.get("source")
        or snapshot_data.get("analysis_mode")
        or "manual_full_pipeline"
    )

    with st.container(border=True):
        st.subheader("Live Pipeline Health")
        st.caption(f"Data source: {source}")

        if not worker:
            st.info("No background worker metadata is available.")
            return

        worker_name = str(worker.get("worker", "unknown-worker"))
        state = str(worker.get("state", "unknown")).lower()
        is_motion_worker = worker_name == "motion-vision-worker"

        health_timestamp = (
            worker.get("updated_at")
            if is_motion_worker
            else worker.get("last_success_at")
        )

        cache_age_seconds = calculate_cache_age_seconds(
            health_timestamp
        )

        interval_seconds = float(
            worker.get("interval_seconds", 0) or 0
        )

        periodic_scan_seconds = float(
            worker.get("periodic_scan_seconds", 0) or 0
        )

        if is_motion_worker:
            stale_after_seconds = max(
                15.0,
                interval_seconds * 3.0,
            )
        else:
            stale_after_seconds = max(
                30.0,
                interval_seconds * 3.0,
                periodic_scan_seconds * 2.0,
            )

        cache_stale = (
            cache_age_seconds is None
            or cache_age_seconds > stale_after_seconds
        )

        displayed_state = state

        if cache_stale and state not in {"error", "stopped"}:
            displayed_state = "stale"

        if is_motion_worker:
            first_row = st.columns(4)

            first_row[0].metric(
                "Worker State",
                displayed_state.upper(),
            )
            first_row[1].metric(
                "Heartbeat Age",
                (
                    f"{cache_age_seconds:.1f} s"
                    if cache_age_seconds is not None
                    else "N/A"
                ),
            )
            first_row[2].metric(
                "Camera State",
                str(
                    worker.get(
                        "camera_capture_state",
                        "unknown",
                    )
                ).upper(),
            )
            first_row[3].metric(
                "Failures",
                int(worker.get("failures", 0) or 0),
            )

            second_row = st.columns(4)

            second_row[0].metric(
                "Frames Captured",
                int(worker.get("frames_processed", 0) or 0),
            )
            second_row[1].metric(
                "Motion Events",
                int(worker.get("motion_events", 0) or 0),
            )
            second_row[2].metric(
                "YOLO Requests",
                int(worker.get("inference_requests", 0) or 0),
            )
            second_row[3].metric(
                "Model Latency",
                (
                    f"{worker.get('latest_model_latency_ms')} ms"
                    if worker.get(
                        "latest_model_latency_ms"
                    ) is not None
                    else "N/A"
                ),
            )

            pir_row = st.columns(4)

            pir_state = str(
                worker.get("pir_state", "unavailable")
            ).upper()

            pir_row[0].metric(
                "PIR State",
                pir_state,
            )
            pir_row[1].metric(
                "PIR Triggers",
                int(worker.get("pir_trigger_count", 0) or 0),
            )
            pir_row[2].metric(
                "PIR GPIO",
                worker.get("pir_gpio", "N/A"),
            )
            pir_row[3].metric(
                "PIR Hardware",
                (
                    "READY"
                    if worker.get("pir_available")
                    else "UNAVAILABLE"
                ),
            )

            if worker.get("pir_motion_detected"):
                st.warning(
                    "PIR hardware sensor currently detects motion."
                )

            st.caption(
                f"PIR last motion: "
                f"{worker.get('pir_last_motion_at', 'N/A')} | "
                f"PIR last clear: "
                f"{worker.get('pir_last_clear_at', 'N/A')}"
            )

            if worker.get("pir_error"):
                st.error(
                    f"PIR error: {worker.get('pir_error')}"
                )

            camera_row = st.columns(4)

            camera_row[0].metric(
                "Primary Camera",
                f"CAM {worker.get('primary_camera_index', 'N/A')}",
            )
            camera_row[1].metric(
                "IR Camera",
                f"CAM {worker.get('secondary_camera_index', 'N/A')}",
            )
            camera_row[2].metric(
                "Completed Captures",
                int(
                    worker.get(
                        "captures_completed",
                        0,
                    )
                    or 0
                ),
            )
            camera_row[3].metric(
                "Capture Duration",
                (
                    f"{worker.get('last_capture_duration_ms')} ms"
                    if worker.get(
                        "last_capture_duration_ms"
                    ) is not None
                    else "N/A"
                ),
            )

            st.caption(
                "Cameras remain closed during standby and "
                "open automatically after a PIR rising edge."
            )

            primary_image_path = worker.get(
                "latest_primary_annotated_image_path"
            ) or worker.get(
                "latest_primary_image_path"
            )

            ir_image_path = worker.get(
                "latest_ir_image_path"
            )

            camera_columns = st.columns(2)

            with camera_columns[0]:
                st.markdown(
                    "**Primary Camera — imx708_wide**"
                )

                if (
                    isinstance(
                        primary_image_path,
                        str,
                    )
                    and Path(
                        primary_image_path
                    ).exists()
                ):
                    st.image(
                        primary_image_path,
                        caption=(
                            "Latest automatic primary "
                            "camera capture"
                        ),
                        use_container_width=True,
                    )
                else:
                    st.caption(
                        "Waiting for the first PIR capture."
                    )

            with camera_columns[1]:
                st.markdown(
                    "**IR Camera — ov5647**"
                )

                if (
                    isinstance(
                        ir_image_path,
                        str,
                    )
                    and Path(
                        ir_image_path
                    ).exists()
                ):
                    st.image(
                        ir_image_path,
                        caption=(
                            "Latest automatic IR "
                            "camera capture"
                        ),
                        use_container_width=True,
                    )
                else:
                    st.caption(
                        "Waiting for the first PIR capture."
                    )

            if worker.get(
                "primary_camera_last_error"
            ):
                st.error(
                    "Primary camera error: "
                    f"{worker.get('primary_camera_last_error')}"
                )

            if worker.get(
                "secondary_camera_last_error"
            ):
                st.warning(
                    "IR camera error: "
                    f"{worker.get('secondary_camera_last_error')}"
                )

            last_trigger_reason = worker.get(
                "last_trigger_reason",
                "N/A",
            )

            last_trigger_at = worker.get(
                "last_trigger_at",
                "N/A",
            )

            trigger_age_seconds = calculate_cache_age_seconds(
                worker.get("last_trigger_at")
            )

            if (
                last_trigger_reason
                in {"motion", "pir_motion"}
                and trigger_age_seconds is not None
                and trigger_age_seconds <= 5
            ):
                st.info(
                    "Recent PIR motion detected. "
                    "Dual-camera capture and YOLO inference "
                    "were triggered automatically."
                )

            st.caption(
                f"Worker: {worker_name} | "
                f"Last trigger: {last_trigger_reason} | "
                f"Trigger time: {last_trigger_at}"
            )

            st.caption(
                f"Last successful inference: "
                f"{worker.get('last_success_at', 'N/A')} | "
                f"Detections: "
                f"{worker.get('latest_detection_count', 'N/A')} | "
                f"Model latency: "
                f"{worker.get('latest_model_latency_ms', 'N/A')} ms"
            )

            st.caption(
                "Trigger pipeline: PIR rising edge -> "
                "primary capture -> IR capture -> "
                "YOLO inference -> persistent event."
            )

            st.caption(
                f"Capture cooldown: "
                f"{worker.get('motion_cooldown_seconds', 'N/A')}s | "
                "Standby mode: both cameras closed"
            )

        else:
            cols = st.columns(6)

            cols[0].metric(
                "Worker State",
                displayed_state.upper(),
            )
            cols[1].metric(
                "Cache Age",
                (
                    f"{cache_age_seconds:.1f} s"
                    if cache_age_seconds is not None
                    else "N/A"
                ),
            )
            cols[2].metric(
                "Completed Cycles",
                worker.get("cycles_completed", 0),
            )
            cols[3].metric(
                "Failures",
                worker.get("failures", 0),
            )
            cols[4].metric(
                "Cycle Duration",
                f"{worker.get('last_cycle_duration_ms', 'N/A')} ms",
            )
            cols[5].metric(
                "Model Latency",
                f"{worker.get('latest_model_latency_ms', 'N/A')} ms",
            )

        if state == "error":
            st.error(
                f"Worker error: "
                f"{worker.get('last_error', 'Unknown error')}"
            )
        elif state == "stopped":
            st.warning("The background vision worker is stopped.")
        elif cache_stale:
            if is_motion_worker:
                st.warning(
                    "The motion worker heartbeat is stale. "
                    "Check the worker process."
                )
            else:
                st.warning(
                    "The cached vision result is stale. "
                    "Check the camera worker and vision service."
                )
        elif int(worker.get("failures", 0) or 0) > 0:
            st.warning(
                "The worker is running, but previous failures were recorded."
            )
        else:
            if is_motion_worker:
                st.success(
                    "The PIR-triggered dual-camera pipeline is healthy."
                )
            else:
                st.success(
                    "The background vision pipeline is healthy."
                )

        with st.expander("Worker details"):
            st.json(worker)




def format_event_timestamp(value: object) -> str:
    timestamp = parse_utc_datetime(value)

    if timestamp is None:
        return str(value or "N/A")

    return timestamp.astimezone().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def render_event_timeline() -> None:
    st.subheader("Persistent Event Timeline")

    filter_columns = st.columns(5)

    with filter_columns[0]:
        event_limit = st.selectbox(
            "Events to load",
            [5, 10, 20, 50],
            index=1,
            key="persistent_event_limit",
        )

    with filter_columns[1]:
        risk_filter = st.selectbox(
            "Risk filter",
            ["All", "LOW", "MEDIUM", "HIGH"],
            index=0,
            key="persistent_event_risk_filter",
        )

    with filter_columns[2]:
        trigger_filter = st.selectbox(
            "Trigger filter",
            [
                "All",
                "pir_motion",
                "motion",
                "periodic_safety_scan",
            ],
            index=0,
            key="persistent_event_trigger_filter",
        )

    with filter_columns[3]:
        object_filter = st.selectbox(
            "Object filter",
            [
                "All",
                "person",
                "cat",
                "dog",
                "bird",
                "horse",
                "cow",
                "bear",
                "bicycle",
                "car",
                "motorcycle",
                "bus",
                "train",
                "truck",
                "backpack",
                "handbag",
                "suitcase",
                "laptop",
                "cell phone",
                "bottle",
                "chair",
                "potted plant",
                "tv",
                "keyboard",
                "mouse",
            ],
            index=0,
            key="persistent_event_object_filter",
        )

    with filter_columns[4]:
        category_filter = st.selectbox(
            "Category filter",
            [
                "All",
                "person",
                "animal",
                "vehicle",
                "carried_object",
                "general_object",
                "unknown_motion",
            ],
            index=0,
            key="persistent_event_category_filter",
        )

    option_columns = st.columns([1, 1, 2])

    with option_columns[0]:
        follow_latest = st.toggle(
            "Follow latest event",
            value=True,
            key="follow_latest_persistent_event",
        )

    query_parameters = {
        "limit": event_limit,
    }

    if risk_filter != "All":
        query_parameters["risk"] = risk_filter

    if trigger_filter != "All":
        query_parameters["trigger"] = trigger_filter

    if object_filter != "All":
        query_parameters["object_label"] = object_filter

    if category_filter != "All":
        query_parameters["category"] = category_filter

    event_query = urlencode(query_parameters)

    try:
        event_history = api_get(
            f"/events?{event_query}",
            timeout=10,
        )
    except Exception as exc:
        st.error(f"Could not load persistent events: {exc}")
        return

    events = event_history.get("events") or []

    with option_columns[1]:
        st.metric(
            "Loaded Events",
            len(events),
        )

    active_filters = []

    if risk_filter != "All":
        active_filters.append(f"risk={risk_filter}")

    if trigger_filter != "All":
        active_filters.append(f"trigger={trigger_filter}")

    if object_filter != "All":
        active_filters.append(f"object={object_filter}")

    if category_filter != "All":
        active_filters.append(
            f"category={category_filter}"
        )

    with option_columns[2]:
        st.caption(
            "Active filters: "
            + (
                ", ".join(active_filters)
                if active_filters
                else "none"
            )
        )

    if not events:
        st.info(
            "No persistent events match the selected filters."
        )
        return

    event_labels = {}

    for event in events:
        event_id = str(event.get("event_id", "unknown"))
        created_at = format_event_timestamp(
            event.get("created_at")
        )
        risk = str(
            event.get("final_risk")
            or "UNKNOWN"
        ).upper()
        primary_category = str(
            event.get("primary_category")
            or "legacy_unclassified"
        )

        category_text = (
            primary_category
            .replace("_", " ")
            .upper()
        )

        objects = event.get("detected_objects") or []
        object_text = (
            ", ".join(str(item) for item in objects)
            if objects
            else "no filtered objects"
        )
        motion_percent = float(
            event.get("motion_percent", 0) or 0
        )

        event_labels[event_id] = (
            f"{created_at} | {risk} | "
            f"{category_text} | "
            f"{object_text} | motion {motion_percent:.2f}%"
        )

    if follow_latest:
        selected_event_id = str(
            events[0].get("event_id")
        )

        st.caption(
            "Automatically displaying the latest persistent event."
        )
    else:
        selected_event_id = st.selectbox(
            "Select event",
            options=list(event_labels.keys()),
            format_func=lambda event_id: event_labels.get(
                event_id,
                event_id,
            ),
            key="selected_persistent_event_id",
        )

    try:
        event = api_get(
            f"/events/{selected_event_id}",
            timeout=10,
        )
    except Exception as exc:
        st.error(f"Could not load event details: {exc}")
        return

    trigger = event.get("trigger") or {}
    vision = event.get("vision") or {}
    sensors = event.get("sensors") or {}
    audio = event.get("audio") or {}
    decision = event.get("decision") or {}
    enrichment = event.get("enrichment") or {}
    evidence = event.get("evidence") or {}
    classification = (
        event.get("classification")
        or {}
    )

    objects = vision.get("objects") or []

    primary_category = str(
        classification.get("primary_category")
        or "legacy_unclassified"
    )

    category_display = (
        primary_category
        .replace("_", " ")
        .upper()
    )

    classification_status = str(
        classification.get("status")
        or "legacy"
    ).upper()

    summary_columns = st.columns(4)

    summary_columns[0].metric(
        "Final Risk",
        str(
            decision.get("final_risk")
            or "UNKNOWN"
        ).upper(),
    )

    summary_columns[1].metric(
        "Trigger",
        str(
            trigger.get("reason")
            or "unknown"
        ),
    )

    summary_columns[2].metric(
        "Motion",
        f"{float(trigger.get('motion_percent', 0) or 0):.2f}%",
    )

    summary_columns[3].metric(
        "Objects",
        len(objects),
    )

    classification_columns = st.columns(
        [1.5, 1.0, 1.0]
    )

    classification_columns[0].metric(
        "Category",
        category_display,
    )

    classification_columns[1].metric(
        "Classification",
        classification_status,
    )

    classification_columns[2].metric(
        "Enrichment",
        str(
            enrichment.get("status")
            or "unknown"
        ).upper(),
    )

    st.caption(
        f"Event ID: {event.get('event_id', 'N/A')} | "
        f"Created: {format_event_timestamp(event.get('created_at'))}"
    )

    categories = (
        classification.get("categories")
        or []
    )

    category_list = (
        ", ".join(
            str(value)
            .replace("_", " ")
            .upper()
            for value in categories
        )
        if categories
        else category_display
    )

    st.caption(
        f"Classification: {classification_status} | "
        f"Categories: {category_list}"
    )

    if primary_category == "unknown_motion":
        st.warning(
            "Motion was confirmed and evidence was saved, "
            "but the vision model could not assign a "
            "recognized object category."
        )

    annotated_image_path = evidence.get(
        "annotated_image_path"
    )
    primary_image_path = evidence.get(
        "primary_image_path"
    )
    ir_image_path = evidence.get(
        "ir_image_path"
    )

    primary_display_path = (
        annotated_image_path
        or primary_image_path
    )

    evidence_columns = st.columns(2)

    with evidence_columns[0]:
        st.markdown(
            "**Primary Camera Evidence**"
        )

        if (
            isinstance(
                primary_display_path,
                str,
            )
            and Path(
                primary_display_path
            ).exists()
        ):
            st.image(
                primary_display_path,
                caption=(
                    "Primary camera with YOLO "
                    "annotations"
                ),
                use_container_width=True,
            )
        else:
            st.warning(
                "Primary camera evidence is unavailable."
            )

    with evidence_columns[1]:
        st.markdown(
            "**IR Camera Evidence**"
        )

        if (
            isinstance(ir_image_path, str)
            and Path(ir_image_path).exists()
        ):
            st.image(
                ir_image_path,
                caption=(
                    "Secondary OV5647 IR evidence"
                ),
                use_container_width=True,
            )
        else:
            st.caption(
                "No IR image was stored for this event."
            )

    st.markdown("#### Detected Objects")

    if objects:
        object_rows = []

        for detected_object in objects:
            object_rows.append(
                {
                    "Label": detected_object.get(
                        "label",
                        "unknown",
                    ),
                    "Confidence": round(
                        float(
                            detected_object.get(
                                "confidence",
                                0,
                            )
                            or 0
                        ),
                        4,
                    ),
                    "Bounding Box": detected_object.get(
                        "bbox",
                        [],
                    ),
                }
            )

        st.dataframe(
            object_rows,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "Motion was detected, but no relevant object "
            "passed the configured filters."
        )

    st.markdown("#### Multimodal Context")

    context_columns = st.columns(3)

    with context_columns[0]:
        st.markdown("**Environmental Sensors**")
        st.write(
            f"Temperature: "
            f"{sensors.get('temperature_c', 'N/A')} °C"
        )
        st.write(
            f"Humidity: "
            f"{sensors.get('humidity_percent', 'N/A')} %"
        )
        st.write(
            f"Pressure: "
            f"{sensors.get('pressure_hpa', 'N/A')} hPa"
        )
        st.write(
            f"MQ-135 raw: "
            f"{sensors.get('air_quality_raw', 'N/A')}"
        )
        st.write(
            f"Air quality: "
            f"{sensors.get('air_quality_level', 'N/A')}"
        )

    with context_columns[1]:
        st.markdown("**Audio Context**")
        st.write(
            f"Event: {audio.get('event', 'N/A')}"
        )
        st.write(
            f"Volume: {audio.get('volume_db', 'N/A')} dB"
        )
        st.write(
            f"Confidence: "
            f"{audio.get('confidence', 'N/A')}"
        )
        st.caption(
            "The current audio service is still operating "
            "in mock mode."
        )

    with context_columns[2]:
        st.markdown("**Vision Context**")

        frame_metadata = (
            vision.get("frame_metadata")
            or {}
        )

        st.write(
            f"Model: {vision.get('model', 'N/A')}"
        )
        st.write(
            f"Model latency: "
            f"{frame_metadata.get('model_latency_ms', 'N/A')} ms"
        )
        st.write(
            f"Frame quality: "
            f"{frame_metadata.get('frame_quality', 'N/A')}"
        )
        st.write(
            f"Lighting: "
            f"{frame_metadata.get('lighting_status', 'N/A')}"
        )
        st.write(
            f"Blur score: "
            f"{frame_metadata.get('blur_score', 'N/A')}"
        )

    st.markdown("#### Agent Decision")

    risk = str(
        decision.get("final_risk")
        or "UNKNOWN"
    ).upper()

    if risk == "HIGH":
        st.error(f"Final risk: {risk}")
    elif risk == "MEDIUM":
        st.warning(f"Final risk: {risk}")
    elif risk == "LOW":
        st.success(f"Final risk: {risk}")
    else:
        st.info(f"Final risk: {risk}")

    st.write(
        decision.get(
            "reason",
            "No decision explanation is available.",
        )
    )

    recommended_action = decision.get(
        "recommended_action"
    )

    if recommended_action:
        st.markdown(
            f"**Recommended action:** {recommended_action}"
        )

    with st.expander("Event details and raw JSON"):
        st.json(event)

    st.markdown("#### Recent Event Summary")

    timeline_rows = []

    for event_summary in events:
        detected_objects = (
            event_summary.get("detected_objects")
            or []
        )

        timeline_rows.append(
            {
                "Time": format_event_timestamp(
                    event_summary.get("created_at")
                ),
                "Risk": event_summary.get(
                    "final_risk"
                ),
                "Trigger": event_summary.get(
                    "trigger_reason"
                ),
                "Category": str(
                    event_summary.get(
                        "primary_category"
                    )
                    or "legacy_unclassified"
                )
                .replace("_", " ")
                .upper(),
                "Motion %": event_summary.get(
                    "motion_percent"
                ),
                "Detections": event_summary.get(
                    "detection_count"
                ),
                "Objects": (
                    ", ".join(
                        str(item)
                        for item in detected_objects
                    )
                    if detected_objects
                    else "-"
                ),
                "Event ID": event_summary.get(
                    "event_id"
                ),
            }
        )

    st.dataframe(
        timeline_rows,
        use_container_width=True,
        hide_index=True,
    )



def render_sensor_panel(sensors: dict) -> None:
    st.markdown("### Environmental Sensors")

    def format_value(
        value: object,
        decimals: int = 1,
    ) -> str:
        try:
            return f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            return "N/A"

    col_a, col_b = st.columns(2)

    with col_a:
        st.metric(
            "Temperature (C)",
            format_value(
                sensors.get("temperature_c"),
            ),
        )
        st.metric(
            "Humidity (%)",
            format_value(
                sensors.get("humidity_percent"),
            ),
        )

    with col_b:
        st.metric(
            "Pressure (hPa)",
            format_value(
                sensors.get("pressure_hpa"),
            ),
        )
        st.metric(
            "MQ-135 Raw",
            sensors.get(
                "air_quality_raw",
                "N/A",
            ),
        )

    level = sensors.get(
        "air_quality_level",
        "N/A",
    )

    st.markdown("Air Quality Level")
    st.markdown(
        level_badge(level),
        unsafe_allow_html=True,
    )
    st.caption(
        "BME280: real temperature, humidity, and pressure. "
        "MQ-135: real analog input through MCP3008 CH0."
    )


def render_audio_panel(audio: dict) -> None:
    source_mode = str(
        audio.get("source_mode")
        or "unknown"
    ).lower()

    hardware_ready = bool(
        audio.get("hardware_ready", False)
    )

    st.markdown("### Audio")

    if not hardware_ready:
        st.warning(
            "Audio hardware is not connected."
        )
        st.markdown(
            f"**Mode:** {source_mode.upper()}"
        )
        st.markdown(
            "**Risk scoring:** DISABLED"
        )
        st.caption(
            "Synthetic values are retained only for "
            "testing and event metadata."
        )
        return

    st.metric(
        "Detected Event",
        audio.get("event", "N/A"),
    )
    st.metric(
        "Volume (dB)",
        audio.get("volume_db", "N/A"),
    )
    st.metric(
        "Confidence",
        audio.get("confidence", "N/A"),
    )
    st.caption(
        f"Audio source: {source_mode.upper()}"
    )


def render_vision_panel(vision: dict) -> None:
    st.markdown("### Vision Inference")

    model = str(
        vision.get("model")
        or "N/A"
    )

    runtime_mode = str(
        vision.get("mode")
        or "unknown"
    )

    mode_display = {
        "real_camera_onnx_inference": (
            "REAL + ONNX"
        ),
        "real_camera": "REAL CAMERA",
        "mock": "MOCK",
    }.get(
        runtime_mode.lower(),
        runtime_mode.upper(),
    )

    st.markdown(f"**Model:** `{model}`")
    st.metric(
        "Inference Mode",
        mode_display,
    )
    st.caption(
        f"Runtime: {runtime_mode}"
    )

    performance_columns = st.columns(2)

    performance_columns[0].metric(
        "FPS",
        vision.get("fps", "N/A"),
    )
    performance_columns[1].metric(
        "Latency (ms)",
        vision.get("latency_ms", "N/A"),
    )

    objects = vision.get("objects", [])
    st.metric("Objects Detected", len(objects))

    frame_metadata = vision.get("frame_metadata", {})
    if frame_metadata:
        st.markdown("#### Frame Quality")
        meta_col_1, meta_col_2 = st.columns(2)
        with meta_col_1:
            st.metric("Frame Quality", frame_metadata.get("frame_quality", "N/A"))
            st.metric("Blur Score", frame_metadata.get("blur_score", "N/A"))
        with meta_col_2:
            st.metric("Lighting", frame_metadata.get("lighting_status", "N/A"))
            st.metric("Brightness", frame_metadata.get("brightness", "N/A"))

    annotated_image_path = frame_metadata.get("annotated_image_path")
    snapshot_path = vision.get("snapshot_path")

    if annotated_image_path and Path(annotated_image_path).exists():
        st.image(
            annotated_image_path,
            caption="Latest YOLO annotated camera frame",
            width=420,
        )
    elif snapshot_path and Path(snapshot_path).exists():
        st.image(
            snapshot_path,
            caption="Latest real camera snapshot",
            width=420,
        )

    if objects:
        st.markdown("#### Detected Objects")
        rows = [
            {
                "label": obj.get("label"),
                "confidence": obj.get("confidence"),
                "bbox": obj.get("bbox"),
            }
            for obj in objects
        ]
        st.dataframe(rows, use_container_width=True)
    else:
        st.caption("No object detected in the latest frame.")

    with st.expander("Raw vision JSON"):
        st.json(vision)


# Top controls
top_left, top_mid, top_right = st.columns([1, 1, 1.4])

with top_left.container(border=True):
    st.subheader("Device")
    st.metric(
        "Hardware",
        "Raspberry Pi 5",
    )
    st.metric(
        "Deployment",
        "LOCAL EDGE",
    )
    st.markdown(
        "**Architecture:** PIR-triggered "
        "dual-camera inference"
    )
    st.caption(
        "Real BME280 and MQ-135 sensors. "
        "Audio hardware pending."
    )

with top_mid.container(border=True):
    st.subheader("Gateway")
    try:
        health = api_get("/health", timeout=3)
        st.metric("Status", health.get("status", "unknown").upper())
        st.caption(f"Version: {health.get('gateway_version', 'unknown')}")
        st.caption(f"API: {API_BASE}")
    except Exception as exc:
        st.error(f"API Gateway unavailable: {exc}")

with top_right.container(border=True):
    st.subheader("Live Controls")
    st.write("Use live API calls instead of stale report data.")

    status_clicked = st.button("Refresh System Status", use_container_width=True)
    snapshot_clicked = st.button("Refresh Live Snapshot", use_container_width=True)
    analyze_clicked = st.button("Run Live Multi-Agent Analysis", type="primary", use_container_width=True)

    st.divider()
    st.markdown("#### Live Monitoring")
    st.toggle("Auto refresh", key="auto_live_monitoring")
    st.selectbox(
        "Refresh interval",
        [2, 5, 10, 15, 30],
        index=2,
        key="live_refresh_interval",
    )
    st.radio("Auto mode", ["Snapshot only", "Full analysis"], index=0, key="live_monitoring_mode")

    if st.session_state.get("last_auto_refresh_label"):
        st.caption(st.session_state["last_auto_refresh_label"])

    if st.session_state.get("last_auto_refresh_error"):
        st.error(st.session_state["last_auto_refresh_error"])

if status_clicked:
    try:
        st.session_state["system_status"] = api_get("/system/status", timeout=5)
    except Exception as exc:
        st.error(f"Status failed: {exc}")

if snapshot_clicked:
    try:
        st.session_state["latest_snapshot"] = api_get("/system/snapshot", timeout=35)
    except Exception as exc:
        st.error(f"Snapshot failed: {exc}")

if analyze_clicked:
    try:
        st.session_state["latest_result"] = api_post("/system/analyze", timeout=35)
        st.session_state["latest_snapshot"] = {
            "system": st.session_state["latest_result"].get("system"),
            "generated_at": st.session_state["latest_result"].get("generated_at"),
            **st.session_state["latest_result"].get("input_snapshot", {}),
        }
    except Exception as exc:
        st.error(f"Analysis failed: {exc}")

# Load status once
if "system_status" not in st.session_state:
    try:
        st.session_state["system_status"] = api_get("/system/status", timeout=5)
    except Exception:
        st.session_state["system_status"] = None

# Load the latest cached worker result on startup.
if "latest_snapshot" not in st.session_state:
    try:
        st.session_state["latest_snapshot"] = api_get("/system/live", timeout=10)
    except Exception:
        st.session_state["latest_snapshot"] = None


# Auto live monitoring mode.
if st.session_state.get("auto_live_monitoring"):
    interval_seconds = int(st.session_state.get("live_refresh_interval", 10))
    mode = st.session_state.get("live_monitoring_mode", "Snapshot only")

    st_autorefresh(
        interval=interval_seconds * 1000,
        key="live_monitoring_autorefresh",
    )

    now = time.time()
    last_refresh = float(st.session_state.get("last_auto_refresh_ts", 0))

    if now - last_refresh >= interval_seconds:
        try:
            if mode == "Full analysis":
                st.session_state["latest_result"] = api_post("/system/analyze-live", timeout=15)
                st.session_state["latest_snapshot"] = {
                    "system": st.session_state["latest_result"].get("system"),
                    "generated_at": st.session_state["latest_result"].get("generated_at"),
                    "source": st.session_state["latest_result"].get(
                        "analysis_mode",
                        "manual_full_pipeline",
                    ),
                    "worker": st.session_state["latest_result"].get("worker", {}),
                    **st.session_state["latest_result"].get("input_snapshot", {}),
                }
            else:
                st.session_state["latest_snapshot"] = api_get("/system/live", timeout=10)

            st.session_state["system_status"] = api_get("/system/status", timeout=5)
            st.session_state["last_auto_refresh_ts"] = time.time()
            st.session_state["last_auto_refresh_label"] = (
                f"Last auto refresh: {time.strftime('%H:%M:%S')} | Mode: {mode}"
            )
            st.session_state["last_auto_refresh_error"] = None

        except Exception as exc:
            st.session_state["last_auto_refresh_ts"] = time.time()
            st.session_state["last_auto_refresh_error"] = f"Auto refresh failed: {exc}"

st.divider()

# System status
system_status = st.session_state.get("system_status")
if system_status:
    st.subheader("Service Status")
    status_cols = st.columns(6)
    services = system_status.get("services", {})

    for idx, name in enumerate(["camera", "sensor", "audio", "vision", "agent"]):
        service = services.get(name, {})
        with status_cols[idx].container(border=True):
            st.markdown(f"*{name.upper()}*")
            st.markdown(service_badge(service.get("status", "unknown")), unsafe_allow_html=True)
            details = service.get("details", {})
            if details:
                with st.expander("details"):
                    st.json(details)

    with status_cols[5].container(border=True):
        st.markdown("*GATEWAY*")
        st.markdown(service_badge("online"), unsafe_allow_html=True)

st.divider()

# Decision section
latest_result = st.session_state.get("latest_result")

if latest_result:
    decision = latest_result.get("decision", {})
    snapshot = latest_result.get("input_snapshot", {})
    risk = decision.get("final_risk", "UNKNOWN")

    decision_col, explain_col = st.columns([0.8, 2.2])

    with decision_col.container(border=True):
        st.subheader("Final Decision")
        st.markdown(risk_badge(risk), unsafe_allow_html=True)
        st.caption(f"Generated at: {latest_result.get('generated_at', 'N/A')}")

    with explain_col.container(border=True):
        st.subheader("Explanation")
        st.info(decision.get("reason", "No reason available."))
        st.subheader("Recommended Action")
        st.warning(decision.get("recommended_action", "No action available."))

    with st.expander("Agent Reasoning Scores", expanded=True):
        st.json(decision.get("modality_summary", {}))

else:
    st.info("Run Live Multi-Agent Analysis to generate a fresh decision from the current sensors.")

st.divider()

# Live snapshot section
snapshot_data = dict(
    st.session_state.get("latest_snapshot")
    or {}
)

try:
    worker_status_payload = api_get(
        "/system/worker-status",
        timeout=3,
    )

    live_worker = (
        worker_status_payload.get("worker")
        or {}
    )

    if live_worker:
        snapshot_data["worker"] = live_worker
        snapshot_data[
            "worker_status_source"
        ] = "live_gateway_status"

except Exception as exc:
    snapshot_data[
        "worker_status_refresh_error"
    ] = str(exc)

render_worker_health(snapshot_data)

st.divider()

st.subheader("Live Input Snapshot")

sensor_col, audio_col, vision_col = st.columns(3)

with sensor_col.container(border=True):
    render_sensor_panel(snapshot_data.get("sensors", {}))

with audio_col.container(border=True):
    render_audio_panel(snapshot_data.get("audio", {}))

with vision_col.container(border=True):
    render_vision_panel(snapshot_data.get("vision", {}))

st.divider()

show_event_timeline = st.toggle(
    "Load Persistent Event Timeline",
    value=False,
    key="show_event_timeline",
)

if show_event_timeline:
    render_event_timeline()
else:
    st.caption(
        "Event Timeline is paused to reduce dashboard load."
    )

st.divider()

show_debug_sections = st.toggle(
    "Load Reports and Raw Data",
    value=False,
    key="show_debug_sections",
)

if show_debug_sections:
    history_col, raw_col = st.columns([1, 2])

    with history_col.container(border=True):
        st.subheader("Report History")
        try:
            history = api_get("/reports/history", timeout=3)
            st.metric(
                "Saved Reports",
                history.get("count", 0),
            )

            for report in history.get("reports", []):
                st.caption(report)

        except Exception as exc:
            st.error(
                f"Could not load report history: {exc}"
            )

    with raw_col.container(border=True):
        st.subheader("Raw Data")

        with st.expander(
            "Current live snapshot JSON"
        ):
            st.json(
                st.session_state.get(
                    "latest_snapshot",
                    {},
                )
            )

        with st.expander("Latest analysis JSON"):
            st.json(
                st.session_state.get(
                    "latest_result",
                    {},
                )
            )

        with st.expander(
            "Latest saved report JSON"
        ):
            try:
                latest_report = api_get(
                    "/reports/latest",
                    timeout=3,
                )
                st.json(latest_report)

            except Exception as exc:
                st.error(
                    f"Could not load latest report: {exc}"
                )
else:
    st.caption(
        "Reports and raw JSON are paused to reduce dashboard load."
    )
