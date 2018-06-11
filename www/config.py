#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import config_default

class Dict(dict):

	def __init__(self, names=(), values=(), **kw):
		super(Dict, self).__init__(**kw)
		for k, v in zip(names, values):
			self[k] = v

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

	def __setattr__(self, key, value):
		self[key] = value

def merge(default, override):
	r = {}
	for k, v in default.items():
		if k in override:
			r[k] = merge(v, override[k]) if isinstance(v, dict) else override[k]
		else:
			r[k] = v
	return r

def toDict(d):
	D = Dict()
	for k, v in d.items():
		D[k] = toDict(v) if isinstance(v, dict) else v
	return D

configs = config_default.config

try:
	import config_override
	configs = merge(configs, config_override.config)
except ImportError:
	pass

configs = toDict(configs)
