from contextlib import contextmanager


@contextmanager
def assert_logs(caplog, level):
    caplog.clear()
    with caplog.at_level(level):
        yield
        assert caplog.records


@contextmanager
def assert_no_logs(caplog, level):
    caplog.clear()
    with caplog.at_level(level):
        yield
        assert not caplog.records
