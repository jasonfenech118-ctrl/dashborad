"""Use PyMySQL as the MySQL driver when one is configured.

PyMySQL is pure Python, so it installs on PythonAnywhere without a compiler
(unlike mysqlclient). This shim makes Django's mysql backend use it. It is a
no-op for the sqlite and postgres backends.
"""
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # PyMySQL not installed (e.g. sqlite-only local run)
    pass
