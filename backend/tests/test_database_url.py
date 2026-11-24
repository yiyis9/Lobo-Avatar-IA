import os
import unittest
from unittest.mock import patch

from database import _database_url


class DatabaseUrlTests(unittest.TestCase):
    def test_mysql_url_uses_installed_pymysql_driver(self) -> None:
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "mysql://lobo:encoded%40password@mysql.internal:3306/lobo_upvt_db"},
        ):
            url = _database_url()

        self.assertEqual(url.drivername, "mysql+pymysql")
        self.assertEqual(url.host, "mysql.internal")
        self.assertEqual(url.password, "encoded@password")


if __name__ == "__main__":
    unittest.main()
