import functools
import logging
import inspect
import os
import asyncio
import errors
from aiohttp import web

# *********RequestHandler模块的主要任务为在View（网页）向Controller（路由）之间建立桥梁，与response_factory之间相对应。web框架把Controller的指令构造成一个request发送给View，然后动态生成前段页面；用户在前端页面的某些操作，然后通过request传回到后端，在传回到后端之前先将request进行解析，转变成后端可以处理的事务。RequestHandler负责对这些request进行标准化处理。**************

def get(path):
    # Define decorator @get('/path')
    # 函数经过该函数后，即加入__method__、__route__属性
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator


def post(path):
    # Define decorator @post('/path')
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


# RequestHandler目的就是从URL函数中分析其需要接受的参数，从request中获取必要的参数，
# URL函数不一定是一个coroutine，因此用RequestHandler()封装一个URL处理函数
class RequestHandler(object):

    def __init__(self, func):
        self._func = func

    # 任何一个类，只需要定义一个__call__()方法，就可以直接对实例进行调用
    async def __call__(self, request):
        # inspect.signature.parameters:返回一个含有变量名称的有序表
        # 获取函数参数表
        required_args = inspect.signature(self._func).parameters
        logging.info('required args: %s' % required_args)

        # 获取从GET或POST传进来的参数值，如果函数参数表
        kw = {arg: value for arg, value in request.__data__.items() if arg in required_args}

        # 获取match_info的参数值，例如@get('/blog/{id}')之类的参数值
        kw.update(request.match_info)

        #如果有request参数的话，也加入
        if 'request' in required_args:
            kw['request'] = request

        #检查参数表中是否有参数缺失
        for key, arg in required_args.items():
            # request参数不能为可变长度
            if key == 'request' and arg.kind in (arg.VAR_POSITIONAL,
                                                 arg.VAR_KEYWORD):
                return web.HTTPBadRequest(text='request parameter cannot be '
                                               'the var argument.')
            # 如果参数类型不是变长列表和变长字典，变长参数是可缺省的
            if arg.kind not in (arg.VAR_POSITIONAL,arg.VAR_KEYWORD):
                # 如果没有默认值，而且没有传值的话就报错
                if arg.default == arg.empty and arg.name not in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s' %
                                                   arg.name)
        logging.info('call with args: %s' % kw)
        try:
            return await self._func(**kw)
        except errors.APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

# 添加一个模块的所有路由
def add_routes(app, module_name):
    try:
        mod = __import__(module_name, fromlist=['get_submodule'])
    except ImportError as e:
        raise e
    # 遍历所有处理方法，由于被@get或@post修饰过，所以方法里会有'__method__'和'__route__'属性
    for attr in dir(mod):
        # 忽略以'_'开头的，因为定义的处理方法不以'_'开头
        if attr.startswith('_'):
            continue
        # 获取非'_'开头的属性或方法
        func = getattr(mod, attr)
        # 取能调用的，说明是方法
        if callable(func):
            # 检测'__method__'和'__route__'属性
            method = getattr(func, '__method__', None)
            path = getattr(func, '__route__', None)
            # 如果method和path均不为空，说明是定义的处理方法，加到app对象里处理route
            if method and path:
                func = asyncio.coroutine(func)
                args = ','.join(inspect.signature(func).parameters.keys())
                logging.info('add route %s %s => %s(%s)' % (method, path,
                                                            func.__name__,
                                                            args))
                app.route.add_route(method, path, RequestHandler(func))

def add_static(app):
    path = os.path.join(os.path.dirname(__path__[0], 'static'))
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))