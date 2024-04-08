from odoo import http
from odoo.http import request, Response
from . import api_responses as ar
from werkzeug.exceptions import NotFound
import werkzeug.exceptions
import json, ast

COMMON_API_ENDPOINT = '/api/v1/sync'
CONTENT_TYPE_JSON = 'application/json;charset=utf-8'


def wrap_response(response, status_code):
    return Response(response, content_type=CONTENT_TYPE_JSON, status=status_code)


def get_sync_config(model_ref):
    return request.env['synchronization.data.mapping'].get_by_model_name(model_ref)


def resource_data(model_ref, data):
    field_map = get_sync_config(model_ref).internal_fields_mapping(data)


def get_resource_data(model_ref, external_id):
    """Prepares request to grab resource, and map their values to their respective external fields."""
    sync_id = get_sync_config(model_ref)
    resource_id = request.env[sync_id.model_id.model].sudo().search([(sync_id.source_field_id.name, '=', external_id)], limit=1)
    if not resource_id:
        raise NotFound("No records found")
    latest_id = request.env['synchronization.queue.logs'].get_latest_log_per_record(resource_id.id, model_ref)
    if not latest_id:
        raise NotFound("No records found")
    return {'data': sync_id.external_fields_mapping(ast.literal_eval(latest_id.data))}


def post_resource_data(model_ref, external_id, data):
    """Prepares data to be inserted, and map their values to their respective internal fields."""
    sync_id = get_sync_config(model_ref)
    latest_id = sync_id.create_queue('create', None, sync_id.internal_fields_mapping(data), 'incoming', external_id)
    return {'data_saved': True}


def put_resource_data(model_ref, external_id, data):
    """Prepares data to be updated, and map their values to their respective internal fields."""
    sync_id = get_sync_config(model_ref)
    resource_id = request.env[sync_id.model_id.model].sudo().search([(sync_id.source_field_id.name, '=', external_id)], limit=1)
    latest_id = sync_id.create_queue('update', resource_id.id, sync_id.internal_fields_mapping(data), 'incoming', external_id)
    return {'data_updated': True}


def delete_resource_data(model_ref, external_id):
    """Prepares record to be deleted."""
    sync_id = get_sync_config(model_ref)
    resource_id = request.env[sync_id.model_id.model].sudo().search([(sync_id.source_field_id.name, '=', external_id)], limit=1)
    latest_id = sync_id.create_queue('delete', resource_id.id, None, 'incoming', external_id)
    return {'data_deleted': True}


class ApiRoutes(http.Controller):

    @http.route([f'{COMMON_API_ENDPOINT}/<string:model_ref>/'], type="http", auth="api_key", website=True, methods=['HEAD'], csrf=False)
    def check_queue(self, model_ref):
        """Check if there are queued items for model_ref."""
        try:
            if request.env['synchronization.queue.logs'].get_pending_failed_records(model_ref):
                return wrap_response(None, 200)  # 200 -> Yes
            return wrap_response(None, 204)  # 204 -> No Content
        except Exception as error:
            return wrap_response(ar.error(f'Error! {error}'), 500)

    @http.route([f'{COMMON_API_ENDPOINT}/<string:model_ref>/<string:res_id>'], type="http", auth="api_key", website=True, methods=['GET'], csrf=False)
    def get_resource(self, model_ref, res_id):
        """Check if there are queued items for model_ref."""
        try:
            try:
                res_id = int(res_id)
            except ValueError:
                pass
            return wrap_response(ar.success(get_resource_data(model_ref, res_id)), 200)  # 200 -> No Content
        except werkzeug.exceptions.NotFound as e:
            return wrap_response(ar.fail({'error': str(e)}), 404)
        except Exception as error:
            return wrap_response(ar.error(f'Error! {error}'), 500)

    @http.route([f'{COMMON_API_ENDPOINT}/<string:model_ref>/<string:res_id>'], type="http", auth="api_key", website=True, methods=['POST'], csrf=False)
    def post_resource(self, model_ref, res_id):
        """Create resource with external id = res_id in model_ref."""
        try:
            requestBody = json.loads(request.httprequest.data.decode(request.httprequest.charset))
            return wrap_response(ar.success(post_resource_data(model_ref, res_id, requestBody.get('data'))), 200)
        except Exception as error:
            return wrap_response(ar.error(f'Error! {error}'), 500)

    @http.route([f'{COMMON_API_ENDPOINT}/<string:model_ref>/<string:res_id>'], type="http", auth="api_key", website=True, methods=['PUT'], csrf=False)
    def update_resource(self, model_ref, res_id):
        """Update resource with external id = res_id in model_ref."""
        try:
            requestBody = json.loads(request.httprequest.data.decode(request.httprequest.charset))
            return wrap_response(ar.success(put_resource_data(model_ref, res_id, requestBody.get('data'))), 200)
        except Exception as error:
            return wrap_response(ar.error(f'Error! {error}'), 500)

    @http.route([f'{COMMON_API_ENDPOINT}/<string:model_ref>/<string:res_id>'], type="http", auth="api_key", website=True, methods=['DELETE'], csrf=False)
    def delete_resource(self, model_ref, res_id):
        """Delete resource with external id = res_id in model_ref."""
        try:
            return wrap_response(ar.success(delete_resource_data(model_ref, res_id)), 200)
        except Exception as error:
            return wrap_response(ar.error(f'Error! {error}'), 500)
