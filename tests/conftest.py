"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest
import pytest_socket

from yf_learner.ui.cache import set_service_override


@pytest.fixture(autouse=True)
def configure_test_environment():
    """Ensure external network is strictly blocked while permitting Windows loopback for asyncio/AppTest."""
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["127.0.0.1", "localhost"])
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass
    set_service_override(None)
    yield
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass
    set_service_override(None)
