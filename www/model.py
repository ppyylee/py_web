#!/usr/bin/env python3
# -*- coding:utf-8 -*-

__author__ = 'L1PY'

import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField

def next_id():
	 return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User(Model):
	#定义表明
	__table__ = 'users'

	id = StringField(primary_key=True, default=next_id, column_type='varchar(50)')
	email = StringField(column_type='varchar(50)')
	passwd = StringField(column_type='varchar(50)')
	is_admin = BooleanField()
	name = StringField(column_type='varchar(50)')
	avatar_url = StringField(column_type='varchar(100)')
	created_at = FloatField(default=time.time)

class Blog(Model):
	__table__ = 'blogs'

	id = StringField(primary_key=True, default=next_id, column_type='varchar(50)')
	user_id = StringField(column_type='varchar(50)')
	user_name = StringField(column_type='varchar(50)')
	avatar_url = StringField(column_type='varchar(100)')
	title = StringField(column_type='varchar(50)')
	summary = StringField(column_type='varchar(200)')
	content = TextField()
	created_at = FloatField(default=time.time)

class Comment(Model):
	__table__ = 'comments'

	id = StringField(primary_key=True, default=next_id,column_type='varchar(50)')
	blog_id = StringField(column_type='varchar(50)')
	user_id = StringField(column_type='varchar(50)')
	user_name = StringField(column_type='varchar(50)')
	avatar_url = StringField(column_type='varchar(100)')
	content = TextField()
	created_at = FloatField(default=time.time)
		