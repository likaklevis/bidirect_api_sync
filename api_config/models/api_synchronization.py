from odoo import fields, models, api


class SynchronizationDataMapping(models.Model):
    _name = 'synchronization.data.mapping'
    _description = 'Data to map appropriate information internally with external application'

    name = fields.Char(string='Name', required=True)
    description = fields.Char(string='Description')
    model_id = fields.Many2one(comodel_name='ir.model', string='Model', ondelete='cascade', domain=[('transient', '=', False)], required=True)
    source_field_id = fields.Many2one(comodel_name='ir.model.fields', ondelete='cascade', string='Field where external ID is stored', required=True)  # ext. app. meaning external application, the field in this application that contains the ID
    source_field_name = fields.Char(string='Source field name', help="The name of the ID field in the external application, e.x. we use 'id' field.")
    field_mapping = fields.Text(string='Field mapping')
    state = fields.Selection([('active', 'Active'),
                              ('disabled', 'Disabled')], string='State')

    _sql_constraints = [('model_id_uniq', 'unique(model_id)', 'Each model can have only one configuration.')]


class SynchronizationQueueLogs(models.Model):
    _name = 'synchronization.queue.logs'
    _description = 'Logs for each synchronization attempt'

    name = fields.Char(string='Name', required=True)
    synchronization_config = fields.Many2one(comodel_name='synchronization.data.mapping', string='Sync Data Map')
    res_id = fields.Integer(string='Resource ID')
    state = fields.Selection([('success', 'Success'),
                              ('pending', 'Pending'),
                              ('outdated', 'Outdated'),  # it means it failed, and when attempted to re-sync the data on external application was the latest (which is preferred)
                              ('failed', 'Failed')], string='State')
    type = fields.Selection([('incoming', 'Incoming'), ('outgoing', 'Outgoing'), ], string='Type', help="Incoming if it is being updated from external application, outgoing if it is being updated from our application")
    hash_value = fields.Char(string='Hash Value', readonly=True)
    internal_last_updated = fields.Datetime(string='Internal last updated')
    external_last_updated = fields.Datetime(string='External last updated')

    _sql_constraints = [('model_id_uniq', 'unique(model_id)', 'Each model can have only one configuration.')]
