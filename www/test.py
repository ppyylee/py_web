#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import orm
from model import User
import asyncio

async def test():
    #创建连接池,里面的host,port,user,password需要替换为自己数据库的信息
    # await orm.create_pool(loop=loop, user='root', password='root',db='py_web')
    #没有设置默认值的一个都不能少
    u = User(name='dflhuang', email='648sssss573@qq.com', password='0123', avatar_url='about:blank')
    res = await u.save()
    print(res)

# 获取EventLoop:
loop = asyncio.get_event_loop()
loop.run_until_complete(orm.create_pool(user='root', password='root', db='py_web', loop=loop))
loop.run_until_complete(test())


