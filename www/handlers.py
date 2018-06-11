#! /usr/bin/env pyhton3
# -*- conding： utf-8 -*-

import re, time, json, logging, hashlib, base64, asyncio

import markdown2
from coroweb import get, post
from coroweb import web
from apis import Page, APIValueError, APIResourceNotFoundError, APIPermissionError, APIError

from model import User, Comment, Blog, next_id
from config import configs

from shehuiren import main as show

COOKIE_NAME = configs.session.name
_COOKIE_KEY = configs.session.secret

def check_admin(request):
	if request.__user__ is None or not request.__user__.is_admin:
		raise APIPermissionError()

def user2cookie(user, max_age):
	'''
	generate cookie str
	'''
	expires = str(int(time.time() + max_age))
	s = '%s-%s-%s-%s' % (user.id,user.passwd,expires, _COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)

def text2html(text):
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
	return ''.join(lines)

def get_page_index(page_str):
	p = 1 
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p

async def cookie2user(cookie_str):
	if not cookie_str:
		return None
	try:
		l = cookie_str.split('-')
		if len(l) != 3:
			return None
		uid , expires, sha1 = l
		if int(expires) < time.time():
			return None
		user = await User.find(uid)
		if user is None:
			return None
		s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			return None
		user.passwd = '******'
		return user
	except Exception as e:
		logging.exception(e)
		return None

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/users')
async def api_register_user(*, email, name, passwd):
	if not name or not name.strip():
		raise APIValueError('name',)
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=?',[email])
	if len(users) > 0:
		raise APIError('register:faild', 'email', 'Email is already in use')
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid, passwd)
	user = User(id=uid, email=email, name=name.strip(), passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), avatar_url='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
	await user.save()
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii = False).encode('utf-8')
	return r

@post('/api/authenticate')
async def authenticate(*, email, passwd):
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email', 'Invalid email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd', 'Invalid passwd')
	user = await User.findAll('email=?',[email])
	if len(user) == 0:
		raise APIValueError('eamil', 'eamil not exist')
	user = user[0]
	sha1_passwd = '%s:%s' % (user.id, passwd)
	sha1_str = hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest()
	# sha1 = hashlib.sha1()
	# sha1.update(user.id.encode('utf-8'))
	# sha1.update(b':')
	# sha1.update(user.passwd.encode('utf'))
	logging.info('user passwd is: %s' % sha1_str)
	if user.passwd != sha1_str:
		raise APIValueError('password', 'Invalid password')
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r
	
@get('/register')
def register():
	return {
		'__tpl__': 'register.html'
	}

@get('/signin')
def signin():
	return {
		'__tpl__': 'signin.html'
	}

@get('/signout')
def signout(request):
	referer = request.headers.get('referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
	return r	

@get('/')
async def index(*, page= '1'):
	paeg_index  = get_page_index(page)
	num =  await Blog.findNumber('count(id)')
	page = Page(num)
	if 0 == num:
		blogs = []
	else:
		blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
	return {
		'__tpl__': 'blogs.html',
		'page' : page,
		'blogs' : blogs
	}

@get('/blog/{id}')
async def get_blog(id):
	blog = await Blog.find(id)
	comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)
	return {
		'__tpl__': 'blog.html',
		'blog': blog,
		'comments': comments
	}

@get('/manage/')
def manage():
	return 'redirect: /manage/comments' 

@get('/manage/comments')
def manage_comments(*, page=1):
	return {
		'__tpl__' : 'manage_comments.html',
		'page_index' : get_page_index(page)
	}

@get('/api/comments')
async def get_commonts(*, page=1):
	page_index = get_page_index(page)
	num =await Comment.findNumber('count(id)')
	p = Page(num, page_index)
	if 0 == num :
		return dict(page= p, comments = ())
	comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return  dict(page=p, comments=comments)
	
@get('/manage/blogs')
def manage_blogs(*, page=1):
	return {
		'__tpl__': 'manage_blogs.html',
		'page_index': get_page_index(page)
	}

@get('/api/blogs')
async def get_blogs_list(*, page=1):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	p = Page(num, page_index)
	if 0 == num :
		return dict(page=p, blogs=())
	blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, blogs=blogs)

@post('/api/blogs/{id}/delete')
async def delete_blog(request, *, id):
	check_admin(request)
	blog = await Blog.find(id)
	await blog.remove()
	return dict(id=id)	

@get('/manage/blogs/edit')
def edit_blog(request, *,id):
	check_admin(request)
	return {
		'__tpl__': 'manage_blog_edit.html',
		'id':id,
		'action': '/api/blogs/%s' % id
	}

@get('/api/blogs/{id}')
async def api_edit_blogs(request, * , id):
	check_admin(request)
	blog = await Blog.find(id)
	return blog
	

@get('/manage/blogs/create')
def create_blog():
	return {
		'__tpl__': 'manage_blog_edit.html',
		'id': '',
		'action': '/api/blogs'
	}

#提交保存新blog
@post('/api/blogs')
async def api_create_blog(request, *, title, summary, content):
	check_admin(request)
	if not title or not title.strip():
		raise APIValueError('title', 'title cannot be empty')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty')
	blog =  Blog(user_id=request.__user__.id, user_name=request.__user__.name, avatar_url=request.__user__.avatar_url, title=title.strip(), summary=summary.strip(), content=content.strip())
	await blog.save()
	return blog

#保存修改的blog
@post('/api/blogs/{id}')
async def api_update_blogs(id, request,  *, title, summary, content):
	check_admin(request)
	if not title or not title.strip():
		raise APIValueError('title', 'title cannot be empty')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty')
	blog = await Blog.find(id)
	blog.title = title.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	await blog.update()
	return blog

@get('/manage/users')
def manage_users(*, page=1):
	return {
		'__tpl__': 'manage_users.html',
		'page_index': get_page_index(page)
	}

@get('/api/users')
async def get_users_list(*, page=1):
	page_index = get_page_index(page)
	num = await User.findNumber('count(id)')
	p = Page(num, page_index)
	if 0 == num:
		return dict(page=p, users=())
	users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, users=users)

#发表评论
@post('/api/blogs/{id}/comments')
async def create_comments(id, request, *, content ):
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty')
	user = request.__user__
	if user is None:
		raise APIPermissionError('Please signin first')
	blog = await Blog.find(id)
	if blog is None:
		raise APIResourceNotFoundError('Blog')
	comments = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, avatar_url=user.avatar_url, content=content.strip())
	await comments.save()
	return comments

#删除评论
@post('/api/comments/{id}/delete')
async def delete_comments(id, request):
	check_admin(request)
	comment = await Comment.find(id)
	if comment is None:
		raise APIResourceNotFoundError('comment')
	await comment.remove()
	return dict(id=id)


#玩客
@get('/play')
def play():
	show()