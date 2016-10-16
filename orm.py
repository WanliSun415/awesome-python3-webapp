import logging
import aiomysql
logging.basicConfig(level=logging.INFO)


# 定义log函数用于提示log信息,第一部分为数据库中用到的log语句,第二部分为'?'对应的参数
def log(sql, args=None):
    logging.info('SQl: [%s] args: %s' % (sql, args or []))

async def destroy_pool(): #销毁连接池
    global __pool
    if __pool is not None:
        __pool.close()
        await  __pool.wait_closed()

async def create_pool(loop, user, password, db, **kw):
    logging.info('create database connection pool ...')
    global __pool
    # __xx表示不是一定不能访问，只是python解释器对外把__xx改成_class__name,所以仍可以通过其访问__xx
    __pool = await aiomysql.create_pool(
        # dict.get(key, default=None)
        loop=loop,                              # 传递消息循环对象loop用于异步执行
        user=user,  # 通过关键字参数传递user
        password=password,  # 通过关键字参数传递password
        db=db,  # 通过关键字参数传递数据库名称
        host=kw.get('host', 'localhost'),       # 默认定义host名字为localhost
        port=kw.get('port', 3306),              # 默认定义mysql的默认端口为3306
        charset=kw.get('charset', 'utf8'),     # 默认数据库字符集为utf-8
        autocommit=kw.get('autocommit', True),  # 默认自动提交事务
        maxsize=kw.get('maxsize', 10),          # 连接池最多同时处理10个请求
        minsize=kw.get('minsize', 1),           # 连接池最少处理1个请求
    )

# 作用于SQL的SELECT语句，对应select语句，传入sql语句和参数
async def select(sql, args, size=None):
    log(sql, args)
    # 异步等待连接池对象返回可以连接的线程，with语句则封装了关闭conn和处理异常的工作
    async with __pool.get() as conn:
        # 等待连接对象返回DictCursor,可以通过dict的方式获取数据库对象，需要通过游标对象执行SQL
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 将sql中的'?'替换为'%s'，因为mysql语句中的占位符为%s
            await cur.execute(sql.replace('?', '%s'), args)
            if size:   # 如果传入的为size,取出指定行数的结果
                resultset = await cur.fetchmany(size)
            else:
                resultset = await cur.fetchall()  # 否则取出所有结果
        logging.info('row returned: %s' % len(resultset))
        return resultset


# 用于SQL的INSERT、INTO、UPDATE、DELETE语句，execute方法只返回结果数，不返回结果集
async def execute(sql, args, autocommit=True):
    log(sql, args)
    # with函数调用进程池，调用with函数后自动调用关闭进程池函数
    async with __pool.get() as conn:
        if not autocommit:  # 若数据库的事务为非自动提交的，则调用协程启动连接
            await conn.begin()
        try:
            # 打开一个DictCursor,他与普通游标不同之处在于，以dict形式返回结果
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount  # 返回受影响的行数
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:  # 出错，回滚事务到增删改之前
                await conn.rollback()
            raise e
        return affected


# 这是一个元类,它定义了如何来构造一个类,任何定义了__metaclass__属性或指定了metaclass的都会通过元类定义的构造方法构造类
# 任何继承自Model的类,都会自动通过ModelMetaclass扫描映射关系,并存储到自身的类属性
class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        # cls: 当前准备创建的类对象,相当于self
        # name: 类名,比如User继承自Model,当使用该元类创建User类时,name=User
        # bases: 父类的元组
        # attrs: 属性(方法)的字典,比如User有__table__,id,等,就作为attrs的keys
        # 排除Model类本身,因为Model类主要就是用来被继承的,其不存在与数据库表的映射
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 找到表名，若没有定义__table__属性,将类名作为表名
        tablename = attrs.get('__table__', name)
        logging.info('found model: %s (table: %s)' % (name, tablename))
        # 建立映射关系表和找到主键
        mappings = {}   # 保存映射关系
        escaped_fields = []         # 保存所有字段名
        primary_key = None  # 保存主键

        # 遍历类的属性,找出定义的域(如StringField,字符串域)内的值,建立映射关系
        # key是属性名,val其实是定义域!请看name=StringField(ddl="varchar50")
        for key, val in attrs.copy().items():
            # 判断val是否属于Field属性类
            if isinstance(val, Field):
                # 把Field属性类保存在映射映射关系表，并从原属性列表中删除
                logging.info('   found mapping: %s ==> %s' % (key, val))
                mappings[key] = attrs.pop(key)
                # 查找并检验主键是否唯一，主键初始值为None，找到一个主键后会被设置为key，若if val.primary_key: 再次为真，则会报错
                if val.primary_key:
                    if primary_key:
                        raise KeyError('Duplicate primary key for field: %s')
                    primary_key = key
                else:
                    escaped_fields.append(key)  # 将非主键的属性名都保存到escaped_fields
        if not primary_key:  # 没有主键也将报错
            raise KeyError('Primary key not found. ')

        attrs['__mappings__'] = mappings                        # 保存表名
        attrs['__table__'] = tablename                          # 映射关系表
        attrs['__primary_key__'] = primary_key                 # 主键属性名
        attrs['__fields__'] = escaped_fields + [primary_key]    # 将所有属性名都添加进__fields__属性中

        # --------------------默认SQL语句------------------------------------
        # 默认select选出主键
        attrs['__select__'] = 'SELECT * FROM `%s`' % (tablename)
        attrs['__insert__'] = 'INSERT INTO `%s` (%s) VALUES (%s)' % (tablename, ', '.join('`%s`' % f for f in mappings), ', '.join('?' * len(mappings)))
        attrs['__update__'] = 'UPDATE `%s` SET %s WHERE `%s` = ?' % (tablename,
                                                                 ', '.join('`%s` = ?' % f for f in escaped_fields), primary_key)
        attrs['__delete__'] = 'DELETE FROM `%s` WHERE `%s`= ?' % (tablename,
                                                              primary_key)
        return type.__new__(cls, name, bases, attrs)


# ORM映射基类,继承自dict,通过ModelMetaclass元类来构造类
class Model(dict, metaclass=ModelMetaclass):

    # 初始化函数,调用其父类(dict)的方法
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    # 增加__getattr__方法，使获取属性更加简单,即可通过"a.b"的形式
    # 动态调用不存在的属性key时,将会调用__getattr__(self,'attr')来尝试获得属性
    # 例如b属性不存在，当调用a.b时python会试图调用__getattr__(self,'b')来获得属性，在这里返回的是dict a[b]对应的值
    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % attr)

    # 增加__setattr__方法,使设置属性更方便,可通过"a.b=c"的形式
    def __setattr__(self, attr, value):
        self[attr] = value

    # 通过键取值,若值不存在,则取默认值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                # 如果field.default可被调用，则返回field.default()，否则返回field.default
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, value))
                # 通过default取到值之后再将其作为当前值
                setattr(self, key, value)
        return value

    # classmethod装饰器将方法定义为类方法
    # 对于查询相关的操作,我们都定义为类方法,就可以方便查询,而不必先创建实例再查询
    # 查找所有合乎条件的信息
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause. '
        # 初始化SQL语句和参数列表
        sql = [cls.__select__]
        if args is None:
            args = []
        # WHERE查找条件的关键字
        if where:
            sql.append('WHERE ')
            sql.append(where)
        # ORDER BY是排序的关键字
        if kw.get('orderBy') is not None:
            sql.append('ORDER BY %s' % (kw['orderBy']))
        # LIMIT 是筛选结果集的关键字
        limit = kw.get('limit')
        if limit is not None:
            if isinstance(limit, int):
                sql.append('LIMIT ?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('LIMIT ?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % limit)
        resultset = await select(' '.join(sql), args)   # 调用前面定义的select函数，没有指定size,因此会fetchall
        return [cls(**r) for r in resultset]            # 返回结果，结果是list对象，里面的元素是dict类型的

    # 根据列名和条件查看数据库有多少条信息
    # @classmethod
    # async def countRows(cls, selectField='*', where=None, args=None):
    #     ' find number by select and where. '
    #     sql = ['SELECT COUNT(%s) _num_ FROM `%s`' % (selectField,
    #                                                  cls.__table__)]
    #     if where:
    #         sql.append('where %s' % where)
    #     resultset = await select(' '.join(sql), args, 1)   # size = 1
    #     if not resultset:
    #         return 0
    #     return resultset[0].get('_num_', 0)

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    # 根据主键查找一个实例的信息
    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '
        resultset = await select('%s WHERE `%s`= ?' % (cls.__select__,
                                                       cls.__primary_key__), [pk], 1)
        return cls(**resultset[0]) if resultset else None

    # 更改一个实例在数据库的信息
    async def update(self):
        args = list(map(self.get, self.__fields__))
        # args.append(self.getValue(self.__primary_key__))
        # 第104行已经将primary_key加入，无需再次加入
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning('failed to update record: affected rows: %s' % rows)

    # 把一个实例从数据库中删除
    async def remove(self):
        args = [self.get(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning('failed to remove by primary key: affected rows: %s' % rows)

    # 把一个实例保存到数据库
    async def save(self):
        args = list(map(self.getValueOrDefault, self.__mappings__))
        # args.append(self.getValueOrDeflault(self.__primary_key__))
        # 第104行已经将primary_key加入，无需再次加入
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warning('failed to insert record: affected rows: %s' % rows)


class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


# 以下几个类作用是为User,Blog,Comment中的字段提供初始化
class StringField(Field):

    # String一般不作为主键，所以默认False, DDL是数据定义语言，为了配合mysql，所以默认设定为100的长度
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        # http://www.cnblogs.com/dkblog/archive/2011/02/24/1980654.html
        # super用于子类调用父类的方法
        super().__init__(name, ddl, primary_key, default)


class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)
