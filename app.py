from jinja2 import Environment, FileSystemLoader
from orm import create_pool, destroy_pool
import factories
from filters import datetime_filter
from coroweb import add_routes, add_static
import os

import asyncio
from aiohttp import web
import logging
logging.basicConfig(level=logging.INFO)


def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape=kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%'),
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'templates')
    # path = kw.get('path', os.path.join(__path__[0], 'templates'))
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env

async def init(loop):
    await create_pool(loop=loop, host='localhost', port=3306, user='www-data',
                      password='www-data', db='awesome')
    app = web.Application(loop=loop, middlewares=[factories.logger_factory,
                                                  factories.auth_factory,
                                                  factories.response_factory])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

#
# def index(request):
#     return web.Response(body=b'<h1>Awesome</h1>')
#
# loop = asyncio.get_event_loop()
# async def test1(loop):
#     await create_pool(loop=loop, host='localhost', port=3306,
#                           user='www-data', password='www-data', db='awesome')
#     u = User(name='Test4', email='test4@1example.com', passwd='123456',
#              image='about:blank')
#     await u.save()
#     await destroy_pool()  # 这里先销毁连接池
#     print('test ok')

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
