import functools
import logging
import inspect
import os
import asyncio
import errors
from aiohttp import web
from urllib import parse
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


def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

# RequestHandler目的就是从URL函数中分析其需要接受的参数，从request中获取必要的参数，
# URL函数不一定是一个coroutine，因此用RequestHandler()封装一个URL处理函数
class RequestHandler(object):

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    # # 任何一个类，只需要定义一个__call__()方法，就可以直接对实例进行调用
    # async def __call__(self, request):
    #     # inspect.signature.parameters:返回一个含有变量名称的有序表
    #     # 获取函数参数表
    #     required_args = inspect.signature(self._func).parameters
    #     logging.info('required args: %s' % required_args)
    #
    #     # 获取从GET或POST传进来的参数值，如果函数参数表
    #     kw = {arg: value for arg, value in request.__data__.items() if arg in required_args}
    #
    #     # 获取match_info的参数值，例如@get('/blog/{id}')之类的参数值
    #     kw.update(request.match_info)
    #
    #     #如果有request参数的话，也加入
    #     if 'request' in required_args:
    #         kw['request'] = request
    #
    #     #检查参数表中是否有参数缺失
    #     for key, arg in required_args.items():
    #         # request参数不能为可变长度
    #         if key == 'request' and arg.kind in (arg.VAR_POSITIONAL,
    #                                              arg.VAR_KEYWORD):
    #             return web.HTTPBadRequest(text='request parameter cannot be '
    #                                            'the var argument.')
    #         # 如果参数类型不是变长列表和变长字典，变长参数是可缺省的
    #         if arg.kind not in (arg.VAR_POSITIONAL,arg.VAR_KEYWORD):
    #             # 如果没有默认值，而且没有传值的话就报错
    #             if arg.default == arg.empty and arg.name not in kw:
    #                 return web.HTTPBadRequest(text='Missing argument: %s' %
    #                                                arg.name)
    #     logging.info('call with args: %s' % kw)
    #     try:
    #         return await self._func(**kw)
    #     except errors.APIError as e:
    #         return dict(error=e.error, data=e.data, message=e.message)
    async def __call__(self, request):
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith(
                        'application/x-www-form-urlencoded') or ct.startswith(
                        'multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(
                        'Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning(
                        'Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except errors.APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s ==> %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))

# 添加一个模块的所有路由
def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n + 1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]),
                      name)
    # try:
    #     mod = __import__(module_name, fromlist=['get_submodule'])
    # except ImportError as e:
    #     raise e
    # # 遍历所有处理方法，由于被@get或@post修饰过，所以方法里会有'__method__'和'__route__'属性
    for attr in dir(mod):
        # 忽略以'_'开头的，因为定义的处理方法不以'_'开头
        if attr.startswith('_'):
            continue
        # 获取非'_'开头的属性或方法
        fn = getattr(mod, attr)
        # 取能调用的，说明是方法
        if callable(fn):
            # 检测'__method__'和'__route__'属性
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            # 如果method和path均不为空，说明是定义的处理方法，加到app对象里处理route
            if method and path:
                add_route(app, fn)
                # func = asyncio.coroutine(func)
                # args = ','.join(inspect.signature(func).parameters.keys())
                # logging.info('add route %s %s => %s(%s)' % (method, path,
                #                                             func.__name__,
                #                                             args))
                # app.router.add_route(method, path, RequestHandler(func))

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))