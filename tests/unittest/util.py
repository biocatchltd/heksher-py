import re
from contextlib import contextmanager
from typing import Pattern, Union


@contextmanager
def assert_logs(caplog, level, pattern: Union[Pattern[str], str]):
    pattern = re.compile(pattern)
    caplog.clear()
    with caplog.at_level(level):
        yield
        assert any(pattern.fullmatch(record.msg) for record in caplog.records)


@contextmanager
def assert_no_logs(caplog, level):
    caplog.clear()
    with caplog.at_level(level):
        yield
        assert not caplog.records
