from odoo import fields, models
import requests
from base64 import b64encode


class OutgoingApiKey(models.Model):
    _name = 'outgoing.api.key'
    _description = 'Outgoing Services API Key'

    name = fields.Char(string='Application name', required=True)
    api_key = fields.Char(string='Key', required=True)
    api_endpoint = fields.Char(string='Full URL endpoint', required=True,
                               help="Entire URL where API endpoint is located, e.g. https://127.0.0.1:8000/v1/api")
    api_auth_type = fields.Selection([('auth_basic', 'Basic Authentication'),
                                      ('bearer', 'Bearer Authentication'),
                                      ('header_api_key', 'Custom Header API Key')],
                                     string='How to authenticate', required=True)
    api_custom_header = fields.Char(string='Custom Header')
    valid = fields.Boolean(string='Valid', default=False, readonly=True)

    _sql_constraints = [('name_uniq', 'unique(name)', 'Application name must be unique.')]

    def test_connection(self):
        data = {
            'method': 'GET',
            'headers': self.prepare_headers(),
            'url': self.api_endpoint,
        }
        response = self.do_connection_session(data)
        if response == 200:
            self.valid = True

    def do_connection_session(self, data):
        req = requests.request(**data)
        req.raise_for_status()
        status = req.status_code
        return status

    def prepare_headers(self):
        headers = {}
        if self.api_auth_type == 'header_api_key':
            headers = {self.api_custom_header: f'{self.api_key}'}
        if self.api_auth_type == 'auth_basic':
            headers = {'Authorization': f'Basic {self.basic_auth(self.api_key)}'}
        if self.api_auth_type == 'bearer':
            headers = {'Authorization': f'Bearer {self.api_key}'}
        return headers

    @staticmethod
    def basic_auth(usr_pwd):
        username, password = usr_pwd.split(':')
        token = b64encode(f"{username}:{password}".encode('utf-8')).decode("ascii")
        return f'{token}'

    def invalidate_api(self):
        self.valid = False
        self.api_key = False
