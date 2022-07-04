import unittest

from logged_groups import logged_group
from unittest.mock import Mock

from ..mempool.operator_resource_mng import OperatorResourceMng


@logged_group("neon.TestCases")
class TestNeonTxSender(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pass

    def setUp(self) -> None:
        self._operator_resource_mng = OperatorResourceMng()

    def test_nothing(self):
        pass
