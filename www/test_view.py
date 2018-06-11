#! /usr/bin/env python3
# -*- coding:utf-8 -*-

from coroweb import get, logger_factory, response_factory, init_jinja2, datetime_filter, add_routes, add_route, add_static
from aiohttp import web
import asyncio
import logging

@get('/')
async def index(request):
	return '<h1>INDEX</h1>'

@get('/hello')
async def hello(request):
	return '<h1>hello</h1>'


if __name__ == '__main__':

	async def init(loop):
		app = web.Application(loop=loop, middlewares=[logger_factory, response_factory])
		init_jinja2(app, filters=dict(datetime = datetime_filter))
		# add_route(app, index)
		add_routes(app, 'test_view')
		add_static(app)
		srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
		print('server started at http://127.0.0.1:9000')
		return srv
	loop = asyncio.get_event_loop()
	loop.run_until_complete(init(loop))
	loop.run_forever()