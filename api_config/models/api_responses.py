import json


def Jsonify(dictionary):
    return json.dumps(dictionary)


def success(data=None):
    """
    {
        'status' : 'success',
        'data' : {
            data
        }
    }

    :param data: Data to be send with the response, type 'dict'
    """
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError('data must be the dict type')
    return Jsonify({'status': 'success', 'data': data})


def fail(data=None):
    """
    {
        'status' : 'fail',
        'data' : {
            data
        }
    }

    :param data: Data to be sent with the response and why it failed, type 'dict'
    """
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError('data param must be type \'dict\'')
    return Jsonify({'status': 'fail', 'data': data})


def error(message='', code=None, data=None):
    """
    {
        'status' : 'error',
        'message' : {
            message
        }
    }

    :param message: Contains the message for the error, type str
    :param code: Contains the status code of the response, type int
    :param data: Data that could be sent with the response, type 'dict'
    """
    ret = {}
    if not isinstance(message, str):
        raise ValueError('message param must be type \'str\'')
    if code:
        if not isinstance(code, int):
            raise ValueError('code param must be type \'int\'')
        ret['code'] = code
    if data:
        if not isinstance(data, dict):
            raise ValueError('data param must be type \'dict\'')
        ret['data'] = data

    ret['status'] = 'error'
    ret['message'] = message
    return Jsonify(ret)
