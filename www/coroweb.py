#! /usr/bin/env python3
# -*- coding:utf-8 -*-

import asyncio, os , functools, logging, inspect


from urllib import parse
from aiohttp import web
from apis import APIError


#建立视图函数装饰器，用来存储、附带URl信息
def handler_decorator(path, *, method):
	def decorator(fn):
		@functools.wraps(fn)
		def warpper(*args, **kw):
			return fn(*args, **kw)
		warpper.__route__ = path
		warpper.__method__ = method
		return warpper
	return decorator
 
get = functools.partial(handler_decorator, method= 'GET')
post  = functools.partial(handler_decorator, method = 'POST')


# 使用inspect模块，检查视图函数的参数  
  
# inspect.Parameter.kind 类型：  
# POSITIONAL_ONLY          位置参数  
# KEYWORD_ONLY             命名关键词参数  
# VAR_POSITIONAL           可选参数 *args  
# VAR_KEYWORD              关键词参数 **kw  
# POSITIONAL_OR_KEYWORD    位置或必选参数  

def get_required_kw_args(fn):#获取无默认值的命名关键词参数
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

def get_named_kw_args(fn): #获取命名关键词参数
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

def has_named_kw_arg(fn): #判断是否有命名关键词参数
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

def has_var_kw_arg(fn): #判断是否有关键词参数
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

def has_request_arg(fn): #判断是否含有名为‘request’的参数且在最后
	sig = inspect.signature(fn)
	params = sig.parameters
	is_found = False
	for name, param in params.items():
		if 'request' == name:
			is_found = True
			continue
		if is_found and (
			param.kind != inspect.Parameter.KEYWORD_ONLY and
			param.kind != inspect.Parameter.VAR_KEYWORD and
			param.kind != inspect.Parameter.VAR_POSITIONAL):
		    raise ValueError('request parameter must be the last named parameter in function:%s%s' % (fn,__name__, str(sig)))
	return is_found

class RequestHandler(object):
	"""docstring for RequestHandler"""
	def __init__(self, app, fn ):
		self._app = app
		self._func = fn
		self._required_kw_args = get_required_kw_args(fn)
		self._named_kw_args = get_named_kw_args(fn)
		self._has_request_arg = has_request_arg(fn)
		self._has_named_kw_arg = has_named_kw_arg(fn)
		self._has_var_kw_arg = has_var_kw_arg(fn)
		

	async def __call__(self, request):
		kw = None
		if self._has_named_kw_arg or self._has_var_kw_arg or self._required_kw_args:
			if 'POST' == request.method:
				#根据request参数中的content_type使用不同解析方法
				if request.content_type is None:
					return web.HTTPBadRequest(text='Missing content_type')
				ct = request.content_type.lower()
				if ct.startswith('application/json'):
					params = await request.json()
					if not isinstance(params, dict):
						return web.HTTPBadRequest(text='JSON body must be object')
					kw = params
				elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
					params = await request.post()
					kw = dict(**params)
				else:
					return web.HTTPBadRequest(text='UNsupported Content-Type: %s' % request.content_type)
			if 'GET' == request.method:
				qs = request.query_string
				if qs:
					kw = dict()
					for k, v in parse.parse_qs(qs, True).items(): #返回查询变量和值的映射（dict）Tru表示不忽略空格
						kw[k] = v[0]
		if kw is None:
			#获取路由参数
			kw = dict(**request.match_info)
		else:
			if not self._has_var_kw_arg  and self._has_named_kw_arg :
				copy = dict()
				for name in self._named_kw_args:
					if name in kw:
						copy[name] = kw[name]
				kw = copy  #仅存储命名关键词参数
			for k, v  in request.match_info.items():
				#检查kw中的参数是否和match_info中重复
				if k in kw:
					logging.warn('Duplicate arg name in named arg and kw args:%s' % k)
				kw[k] = v
		if self._has_request_arg:
			kw['request'] = request
		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					return web.HTTPBadRequest('Missing argument: %s' % name)
		logging.info('call with args: %s' % str(kw))
		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error, data=e.data, message=e.message)


def add_route(app, fn):
	method = getattr(fn, '__method__', None)
	path =  getattr(fn, '__route__', None)
	if method is None or path is None:
		raise ValueError('@get or @post not defined in %s' % fn.__name__)
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
	#在app中注册经RequestHandler类封装的视图函数
	app.router.add_route(method, path, RequestHandler(app, fn))

#批量注册视图函数
def add_routes(app, module_name):
	n = module_name.rfind('.') #从右侧检索，无则返回-1
	if -1 == n:
		mod = __import__(module_name, globals(), locals)
	else:
		name = module_name[(n+1):]
		mod = getattr(__import__(module_name[:n],globals(), locals, [name]), name) #等价于from nodule_name import name
	for attr in dir(mod): #dir()迭代出mod模块中的所有的类，实例及函数等对象，str形式
		if attr.startswith('_'):
			continue
		fn  = getattr(mod, attr)
		if callable(fn):
			method = getattr(fn, '__method__', None)
			path  = getattr(fn, '__route__', None)
			if method and path:
				add_route(app, fn)

#注册静态文件
def add_static(app):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	app.router.add_static('/static', path)
	logging.info('add static %s=>%s' % ('/static/', path))





