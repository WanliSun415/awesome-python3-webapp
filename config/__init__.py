db_config = {
    'user': 'moling',
    'password': 'www-data',
    'db': 'myblog'
}


# jinja2默认设置
jinja2_config = dict()

COOKIE_NAME = 'aweSession'
COOKIE_KEY = 'Mblog'


__all__ = ['db_config', 'jinja2_config', 'COOKIE_NAME', 'COOKIE_KEY']