from odoo import http
from odoo.http import request, Response
from . import api_responses as ar

COMMON_API_ENDPOINT = '/v1/api'
CONTENT_TYPE_JSON = 'application/json;charset=utf-8'


def wrap_response(response, status_code):
    return Response(response, content_type=CONTENT_TYPE_JSON, status=status_code)


class ApiRoutes(http.Controller):

    @http.route([f'{COMMON_API_ENDPOINT}/<string:model_ref>/<int:source_res_id>/<string:hash_value>'], type="http",
                auth="api_key", website=True, methods=['HEAD'], csrf=False)
    def check_if_resource_updated(self, model_ref, res_id):
        try:
            return wrap_response(ar.success({'ID': request.env[model_ref].browse(res_id).id}), 200)
        except Exception as error:
            return wrap_response(ar.error(f'Error! {error}'), 500)
