from odoo import fields, api, models, tools, _
from odoo.exceptions import ValidationError, AccessDenied
from odoo.http import request
import logging
from . import api_secure as apisecure

_logger = logging.getLogger(__name__)


class ServicesApiKey(models.Model):
    """This is where API keys are stored in the database.
    For each service we create an API key and select the user to access the service."""

    _name = 'services.api.key'
    _description = 'Services API Key'

    name = fields.Char(string='Application name', required=True)
    identifier = fields.Char(string='Identifier', readonly=True)
    api_key = fields.Char(string='Hashed and Hidden Api Key', readonly=True)
    valid = fields.Boolean(string='Valid', default=False, readonly=True)
    user_id = fields.Many2one('res.users', string='User associated', required=True)

    _sql_constraints = [('name_uniq', 'unique(name)', 'Application name must be unique.')]

    @api.model
    @tools.ormcache('api_key')  # cache so for the same validated key we do not run this function again
    def _retrieve_api_obj(self, api_key):
        """From the API key provided, get the identifier inside this key
        and compare the hash of this key with the one in the database"""

        try:
            app = api_key.split('_')[0]
            assert app == apisecure.APP

            identifier = api_key.split('_')[1]
            key = api_key.split('_')[2]
        except Exception:
            raise ValidationError(_('API not correct'))

        api_obj = self.env['services.api.key'].sudo().search([('identifier', '=', identifier), ('valid', '=', True), ])
        if not api_obj or not apisecure.validate_key(key, api_obj.api_key):
            raise ValidationError(_('API not correct'))

        return api_obj.user_id.id or None

    @api.model
    def clear_cache(self):
        """Clear the API key cache, whenever changes happen in any of the keys.
        This affects all the functions with tools.ormcache decorator"""
        self.sudo().env.registry.clear_cache()

    def invalidate_api_key(self):
        """Invalidates the API key from the database"""
        self.valid = False
        self.clear_cache()

    def open_generate_api_key_wizard(self):
        """Open the API key wizard for generating a new API key"""
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'generate.api.key.wizard',
            'target': 'new',
        }


class GenerateApiKeyWizard(models.TransientModel):
    _name = 'generate.api.key.wizard'

    @staticmethod
    def _generate_key(self):
        """Generate the API key"""
        identifier = apisecure.generate_key(5)
        api_key = apisecure.generate_key(32)
        return f'{apisecure.APP}_{identifier}_{api_key}'

    api_key = fields.Char(string='API Key', default=_generate_key)

    def apply_key(self):
        """Apply the API key to the appropriate API configuration."""
        vals_update = {
            'identifier': self.api_key.split('_')[1],
            'api_key': apisecure.hash_key(self.api_key.split('_')[2]),
            'valid': True,
        }
        self.env['services.api.key'].browse(self.env.context.get('active_id')).write(vals_update)
        self.api_key = False
        self.env['services.api.key'].clear_cache()


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _auth_method_api_key(cls):
        """Method to authenticate new controllers with auth="API_KEY" based
        on the API configurations in services.api.key"""

        headers = request.httprequest.environ
        api_key = headers.get('HTTP_API_KEY')
        if api_key:
            request.update_env(user=1)  # acting like .sudo() to do the lookup on the next line
            uid = request.env['services.api.key']._retrieve_api_obj(api_key)
            if uid:
                request._env = None  # reset _env when changing user
                request.update_env(user=uid)  # change to user associated with the key
                return True
        _logger.error('Wrong API_KEY, access denied')
        raise AccessDenied()
