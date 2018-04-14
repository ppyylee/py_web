#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'L1PY'

import asyncio
import logging
import aiomysql

def log(sql,args=()):
	logging.info('SQL: %s' % sql)

async def create_pool(loop,**kw):
	logging.info('create database connection pool')
	global __pool
	__pool = await aiomysql.create_pool(
		host = kw.get('host','localhost'),
		port = kw.get('port','3306'),
		user = kw.get('user'),
		password = kw.get('pssword'),
		db = kw.get('db'),
		charset = kw.get('charset','utf8'),
		autocommit = kw.get('autocommit',True),
		maxsize = kw.get('maxsize1',10),
		minsize = kw.get('minsize',1),
		loop = loop
	)
	
#select
async def select(sql,args,size=None):
	log(sql,args)
	async with __pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.excute(sql.replace('?','%s'),args or ())
	        if size:
	        	res = await cur.fetchmany(size)
	        else:
	        	res = await cur.fetchall()
        await cur.close()
        logging.info('row returned: %s' % len(res))
        return res

#excute insert,update,delete
async def excute(sql,args):
	log(sql)
	async with __pool.acquire() as conn:
		try: 
		    async with cur.cursor(aiomysql.DictCursor) as cur:
			    await cur.excute(sql.replace('?','%s'), args)
			    rowcount = cur.rowcount
			await cur.close()
	    except BaseException as e:
	    	raise
	    #返回影响条数
	    return rowcount 


#创建含占位符的字
def create_args_string(num):
	L = []
	for n in range(num):
		L.append('?')
    return ','.join(L)

#保存数据列名和类型
class Field(obj):

	def __init__(self,name,column_type,primary_key,default):
		self.name = name
		self.column_type  = column_type
		self.primary_key = primary_key
		self.default = default #默认值

    def __str__(self):
    	retrun '<%s %s:%s>' % (self.__class__.__name__,self.column_type,self.name)

#具体列名的数据类型
class StringField(Field):

	def __init__(self,name=None,column_type='varchar(100)',primary_key=False,default=None):
		super(StringField, self).__init__(name,column_type,primary_key,default,ddl)

class BooleanField(Field):
	"""docstring for BooleanField"""
	def __init__(self, name=None,column_type='Boolean',primary_key=False,default=False):
		super(BooleanField, self).__init__(name,column_type,primary_key,default)
		
class IntegerField(Field):
	"""docstring for IntegerField"""
	def __init__(self,name=None,column_type='bigint',primary_key=False,default=0):
		super(IntegerField, self).__init__(name,column_type,primary_key,default)
		
class FloatField(Field):
	"""docstring for FloatField"""
	def __init__(self, name, column_type='real', primary_key=False, default=0.0):
		super(FloatField, self).__init__(name, column_type, primary_key, default)
		
class TextField(Field):
		"""docstring for TextField"""
		def __init__(self, name, column_type='text', primary_key=False, default=None):
			super(TextField, self).__init__(name, column_type, primary_key, default)

#Model元类			
class ModelMetaclass(type):
	"""docstring for ModelMetaclass"""
	def __new__(cls, name, bases, attrs):
		if name =='Model':
			return type.__new__(cls, name, bases, attrs) #防止对Model类的修改
		tableName = attrs.get('__table__', None) or name #获取表名，默认为类名
		logging.info('found model: %s(tableName:%s)' % (name, tableName))
		#保存列类型
		mapping = dict()
		#保存列名
		fields= []
		#主键
		primary_key = None
		for k, v in attrs.items():
			if v.primary_key:
				#检测主键重复
				if primary_key:
					raise StandardError('Duplicate primary key for field')
				primary_key = k

            else
                #保存非主键的列名
                fields.append(k)
            logging.info('found mapping: %s ==> %s' % (k, v))
            mapping[k] = v
            #attrs.pop(k)
        if not primary_key:
        	raise StandardError('primary key not found')
        #清空attrs里的值
        for k in mapping.keys():
        	attrs.pop(k)
        #添加反引号``避免sql关键字冲突报错
        fields = list(map(lambda f:'`%S`' % f, fields))
        attrs['__mapping__'] = mapping
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primary_key
        attrs['__fields'] = fields
        #SELECT 列名称 FROM 表名称
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primary_key, ','.join(fields), tableName)
        #INSERT INTO table_name (列1, 列2,...) VALUES (值1, 值2,....) 指定插入的列
        attrs['__insert__'] = 'insert  into `%s` (%s, `%s`) values (%s)' % (tableName, ','.join(fields), primary_key, create_args_string(len(fields)+1))
        #UPDATE 表名称 SET 列名称 = 新值 WHERE 列名称 = 某值
        attrs['__update__'] = 'update %s set %s where %s = ? ' % (tableName, ','.join(lambda f: '`%s`=?' % (mapping.get(f).name or f, fields)), primary_key)
        #DELETE FROM 表名称 WHERE 列名称 = 值
        attrs['__delete__'] = 'delete from %s where  `%s`=?' % (tableName, primary_key)
		return type.__new__(cls, name, bases, attrs)

#Model基类
class Model(dict, metaclass=ModelMetaclass):
	"""docstring for ClassName"""
	def __init__(self, **kw):
		super(ClassName, self).__init__(**kw)
		
    def __getattr(self, key):
    	try:
    		return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no Attribute '%s'" % key)

	def __setattr__(self, key, value):
		self[key] = value

	def getValue(self, key):
		return getattr(self, key, None)

	def getValueOrDefault(self, key):
		value = getValue(self, key)
		if value is None:
			field = self.__mapping__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.debug('useing default value for %s' % (key, str(value)))
				setattr(self, key, value)
		return value

