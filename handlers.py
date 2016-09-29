from coroweb import get, post
from model import User, Comment, Blog, next_id
import re, time, json, logging, hashlib, base64, asyncio


@get('/')
async def index(request):
    users = await User.findAll()
    return {
        '__template__': 'test.html',
        'users': users
    }
