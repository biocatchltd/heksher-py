from logging import WARNING

from heksher.setting import Setting
from tests.unittest.util import assert_logs


def test_get_from_temp(caplog):
    a = Setting('a', int, 'abc', default_value=0)
    with assert_logs(caplog, WARNING):
        assert a.get() == 0
