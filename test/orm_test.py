from orm import create_pool, destroy_pool
import asyncio
from model import User
import logging

async def test1(loop):
    await create_pool(loop=loop, host='localhost', port=3306, user='www-data', password='www-data', db='awesome')
    # u = User(name='Test19', email='test19@example.com', passwd='123456',
    #         image='about:blank')
    # await u.save()

    # 测试count rows语句
    rows = await User.countRows()
    logging.info('rows is %s' % rows)

    # 测试insert into语句
    if rows < 3:
        for idx in range(5):
            u = User(
                name='test%s' % idx,
                email='mytest%s@org.com' % idx,
                passwd='orm123%s' % idx,
                image='about:blank'
            )
            row = await User.countRows(where='email = ?', args=[u.email])
            if row == 0:
                await u.save()
            else:
                print('the email is already registered...')

    # 测试select语句
    users = await User.findAll(orderBy='created_at')
    for user in users:
        logging.info('name: %s, password: %s, created_at: %s' % (user.name, user.passwd, user.created_at))

    # 测试update语句
    user = users[1]
    user.email = 'guest@orm.com'
    user.name = 'guest'
    await user.update()

    # 测试查找指定用户
    test_user = await User.find(user.id)
    logging.info('name: %s, email: %s' % (test_user.name, test_user.email))

    # # 测试delete语句
    # users = await User.findAll(orderBy='created_at', limit=(0, 3))
    # for user in users:
    #     logging.info('delete user: %s' % user.name)
    #     await user.remove()

    await destroy_pool()  # 这里先销毁连接池
    print('test ok')

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test1(loop))
    loop.close()
