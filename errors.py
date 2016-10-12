import logging
import json


class Page(object):
    '''
    Page object for display pages.
    '''
    def __init__(self, item_count, page_index=1, page_size=10):
        '''
                Init Pagination by item_count, page_index and page_size.
                >>> p1 = Page(100, 1)
                >>> p1.page_count
                10
                >>> p1.offset
                0
                >>> p1.limit
                10
                >>> p2 = Page(90, 9, 10)
                >>> p2.page_count
                9
                >>> p2.offset
                80
                >>> p2.limit
                10
                >>> p3 = Page(91, 10, 10)
                >>> p3.page_count
                10
                >>> p3.offset
                90
                >>> p3.limit
                10
                '''
        self.item_count = item_count
        self.page_size = page_size
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            self.page_index = page_index
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1

    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__



class APIError(Exception):

    # 基本的API错误，包括必须的errors,可选的data和message
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message


class APIValueError(APIError):

    # 指示输入值有错误或无效。该数据指明输入表单的错误字段
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)


class APIResourceNotFoundError(APIError):

    # 指出输入源不存在，数据指明源名称
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)


class APIPermissionError(APIError):

    # 指出API没有权限
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)


if __name__ == '__main__':
    import doctest
    doctest.testmod()