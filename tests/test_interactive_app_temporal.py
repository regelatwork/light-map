from light_map.common_types import AppConfig
from light_map.interactive_app import InteractiveApp


def test_interactive_app_advances_system_time():
    config = AppConfig(width=800, height=600)
    # Use a dummy time provider to control time
    current_time = [100.0]

    def dummy_time():
        return current_time[0]

    app = InteractiveApp(config, time_provider=dummy_time)

    # First call to initialize last_fps_time
    app.process_state()
    initial_ts = app.state.system_time_version
    initial_time = app.state.system_time

    # Advance time
    current_time[0] += 1.0
    app.process_state()

    assert app.state.system_time == initial_time + 1.0
    assert app.state.system_time_version > initial_ts
