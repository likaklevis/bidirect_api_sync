from odoo import fields, models, api, _
import json
from odoo.exceptions import UserError
import ast


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

    @api.model
    def get_by_model_name(self, model_name):
        """Returns the configuration data for the given model name."""
        return self.search([('model_id.model', '=', model_name)], limit=1)

    def get_model_field_names(self):
        """Returns the names of the model fields."""
        return [s['name'] for s in self.sudo().env['ir.model.fields'].browse(self.model_id.field_id.ids).read(['name'])]

    def field_mapping_to_dict(self):
        """Returns the string to a dictionary. Raises error if the field mapping format is invalid, not according to JSON Format."""
        if self.field_mapping:
            return json.loads(self.field_mapping)

    def external_fields_mapping(self, dict_val):
        """Maps the data of the internal fields, to the external one. Preparing data to send to external application."""
        field_map = self.field_mapping_to_dict()
        new_external_field_dict = {}
        for key, value in dict_val.items():
            if key in field_map:
                new_external_field_dict[field_map[key]] = value

        return new_external_field_dict

    def create_queue(self, type, res_id, data, last_updated):
        """Creates a new synchronization log in the queue. A CRON job will attempt to send this data to the external application."""
        self.env['synchronization.queue.logs'].create(
            {
                'synchronization_config': self.id,
                'res_id': res_id,
                'state': 'pending',
                'sync_type': 'outgoing',
                'type': type,
                'data': data,
                'internal_last_updated': last_updated
            }
        )

    @api.onchange('field_mapping')
    def onchange_field_mapping(self):
        """This will attempt to check if the format is correct, and clean the whitespaces/lines if necessary."""
        if self.field_mapping:
            model_fields = self.get_model_field_names()
            field_map_dict = self.field_mapping_to_dict()
            for field in field_map_dict:
                if field not in model_fields:
                    raise UserError(_('Field mapping is incorrect. Check the field '.format(field)))
            self.field_mapping = json.dumps(field_map_dict)


class SynchronizationQueueLogs(models.Model):
    _name = 'synchronization.queue.logs'
    _description = 'Logs for each synchronization attempt'

    synchronization_config = fields.Many2one(comodel_name='synchronization.data.mapping', string='Sync Data Map')
    res_id = fields.Integer(string='Resource ID')
    state = fields.Selection([('success', 'Success'),
                              ('pending', 'Pending'),
                              ('outdated', 'Outdated'),  # it means no longer needed, new data has been added on recent queues
                              ('failed', 'Failed')], string='State')
    sync_type = fields.Selection([('incoming', 'Incoming'), ('outgoing', 'Outgoing'), ], string='Synchronization type', help="Incoming if it is being updated from external application, outgoing if it is being updated from our application")
    type = fields.Selection([('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ], string='Type', help="Type of action of the record")
    hash_value = fields.Char(string='Hash Value', readonly=True)
    data = fields.Char(string='Data')
    internal_last_updated = fields.Datetime(string='Internal last updated')
    external_last_updated = fields.Datetime(string='External last updated')

    _sql_constraints = [('model_id_uniq', 'unique(model_id)', 'Each model can have only one configuration.')]

    def external_fields_mapping(self, dict_val):
        return self.synchronization_config.external_fields_mapping(dict_val)

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            # for the res_id of the model, we change all other pending or failed queues to outdated
            self.search([('synchronization_config', '=', val['synchronization_config']),
                         ('res_id', '=', val['res_id']),
                         ('state', 'in', ['pending', 'failed'])]).write({'state': 'outdated'})
        res = super(SynchronizationQueueLogs, self).create(vals_list)
        return res

    # def check_if_records_missing(self):
    #     for model in self.env['synchronization.data.mapping'].search([('id', '!=', False)]).mapped('model_id'):
    #         model_config = self.env['synchronization.data.mapping'].get_by_model_name(model.model)
    #         ids_per_model = self.search([('synchronization_config', '=', model_config.id)]).mapped('res_id')
    #         res_missing = self.env[model.model].search([('id', 'not in', ids_per_model)])
    #         for res in res_missing:
    #             self.env['synchronization.queue.logs'].create(
    #                 {
    #                     'synchronization_config': model_config.id,
    #                     'res_id': res.id,
    #                     'state': 'pending',
    #                     'sync_type': 'outgoing',
    #                     'type': 'create',
    #                     'data': res.create_date,
    #                     'internal_last_updated': res.create_date
    #                 }
    #             )

    @api.model
    def _cron_sync(self):
        """This CRON Job will check for all pending and failed queues, and will attempt to send them one by one."""
        pending_failed_records = self.search([('state', 'in', ['pending', 'failed'])])
        outgoing_api_id = self.env['outgoing.api.key'].search([('valid', '=', True), ('name', '=', 'ext_project_app')], limit=1)
        for record in pending_failed_records:
            try:
                mapped_external_field = record.external_fields_mapping(ast.literal_eval(record.data))
                outgoing_api_id.send_data_to_api(json.dumps(mapped_external_field))
            except:
                print('Error sending data to API')
                record.state = 'failed'
                continue
            record.state = 'success'
