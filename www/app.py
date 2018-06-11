 #!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'L1PY'

import logging
logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from config import configs
from aiohttp import web
from coroweb import add_route, add_routes, add_static
from handlers import cookie2user, COOKIE_NAME
import orm

def init_jinja2(app, **kw):
	logging.info('init jinja2...')
	options = dict(
		autoescape = kw.get('autoescape', True),
		block_start_string = kw.get('block_start_string', '{%'),
		block_end_string = kw.get('block_end_string', '%}'),
		variable_start_string = kw.get('variable_start_string', '{{'),
		variable_end_string = kw.get('variable_end_string', '}}'),
		auto_reload = kw.get('auto_reload', True)
		)
	path = kw.get('path', None)
	if not path:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'tpl')

	env = Environment(loader = FileSystemLoader(path), **options)
	filters = kw.get('filters', None)
	if filters:
		for name,f in filters.items():
			env.filters[name] = f
	app['__tpl__'] = env

#用于输出日志的middleware
async def logger_factory(app, handler):
	async def logger(request):
		logging.info('Request: %s %s' % (request.method, request.path))
		return (await handler(request))
	return logger

#用于处理request data的middlsware
async def data_factory(app, handler):
	async def parse_data(request):
		if 'POST' == request.method:
			if request.content_type.startswith('application/json'):
				request.__data__ = await request.json()
				logging.info('request json: %s' % str(request.__data__))
			if request.content_type.startswith('application/x-www-form-urlencoded'):
				request.__data__ =  await request.post()
				logging.info('request form: %s' % str(request.__data__))
		return await handler(request)
	return parse_data 

#用于检测登录状态的middleware
async def auth_factory(app, handler):
	async def auth(request):
		logging.info('check user: %s %s' % (request.method, request.path))
		request.__user__ = None
		cookie_str = request.cookies.get(COOKIE_NAME)
		if cookie_str:
			user = await cookie2user(cookie_str)
			if user:
				logging.info('set current user: %s' % user.email)	
				request.__user__ = user
		if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.is_admin):
			return web.HTTPFound('/signin')
		return (await handler(request))
	return auth


#用于构造Response对象的middleware
async def response_factory(app, handler):
	async def response(request):
		logging.info('response handler..')
		r = await handler(request)
		logging.info('response result = %s' % str(r))
		if isinstance(r, web.StreamResponse): #StreamResponse是所有Response的夫类
			return r #直接返回
		if isinstance(r, bytes):
			res = web.Response(body=r)
			res.content_type = 'application/octet-stream'
			return res
		if isinstance(r, str):
			if r.startswith('redirect:'): #重定向字符串
				return web.HTTPFound(r[9:]) #重定向至目标URL
			res = web.Response(body=r.encode('utf-8'))
			res.content_type = 'text/html;charset=utf-8'
			return res
		if isinstance(r, dict):
			tpl = r.get('__tpl__', None)
			if tpl is None:
				res = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda obj : obj.__dict__).encode('utf-8'))
				res.content_type = 'application/json;charset=utf-8'
				return res
			else:
				r['__user__'] = request.__user__
				res = web.Response(body=app['__tpl__'].get_template(tpl).render(**r))
				res.content_type = 'text/html;charset=utf-8'
				return res
		if isinstance(r, int) and r>= 100 and r<600:
			res = web.Response(status=r)
			return res
		if isinstance(r, tuple) and len(r) == 2:
			status_code, msg = r
			if isinstance(status_code, int) and status_code>=100 and status_code<600 :
				res = web.Response(status=status_code, text=str(msg))
				return res
		res  = web.Response(body=str(r).encode(utf-8))
		res.content_type = 'text/plain;charset=utf-8'
		return res
	return response

#过滤器
def datetime_filter(t):
	delta = int(time.time() - t)
	if delta < 60:
		return u'1分钟前'
	if delta < 3600:
		return u'%s分钟前' % (delta//60)
	if delta < 86400:
		return u'%s小时前' % (delta//3600)
	if delta < 604800:
		return u'%s天前' % (delta//86400)
	dt = datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
	#创建连接池
	await orm.create_pool(loop=loop, **configs.db)
	app = web.Application(loop=loop, middlewares=[
		logger_factory,auth_factory,  response_factory
	])
	init_jinja2(app, filters=dict(datetime=datetime_filter))
	add_routes(app, 'handlers')
	add_static(app)
	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	logging.info('server started at http://127.0.0.1:9000')
	logging.info('*'*12)
	return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()