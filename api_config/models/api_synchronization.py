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
        for internal_key, external_key in dict_val.items():
            if internal_key in field_map:
                new_external_field_dict[field_map[internal_key]] = external_key
        return new_external_field_dict

    def internal_fields_mapping(self, dict_val):
        """This is the reverse of what external fields_mapping does. Formatting data from external application to internal one."""
        field_map = self.field_mapping_to_dict()
        new_external_field_dict = {}
        for internal_key, external_key in field_map.items():
            if external_key in dict_val:
                new_external_field_dict[internal_key] = dict_val[external_key]
        return new_external_field_dict

    def create_queue(self, type, res_id, data, sync_type, external_id=None, last_updated=None):
        if last_updated is None:
            last_updated = fields.datetime.now()
        """Creates a new synchronization log in the queue. A CRON job will attempt to send this data to the external application."""
        return self.env['synchronization.queue.logs'].create(
            {
                'synchronization_config': self.id,
                'res_id': res_id,
                'state': 'pending',
                'sync_type': sync_type,
                'type': type,
                'data': data,
                'internal_last_updated': last_updated,
                'external_id': external_id,
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
    external_id = fields.Char(string='External ID', readonly=True)
    data = fields.Char(string='Data')
    internal_last_updated = fields.Datetime(string='Internal last updated')
    latest_error_message = fields.Text(string='Error', readonly=True)

    _sql_constraints = [('model_id_uniq', 'unique(model_id)', 'Each model can have only one configuration.')]

    def external_fields_mapping(self, dict_val):
        return self.synchronization_config.external_fields_mapping(dict_val)

    def get_config_by_model_name(self, model_name):
        return self.synchronization_config.get_by_model_name(model_name)

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
    def get_pending_failed_records(self, sync_type='outgoing', model_ref=None):
        domain = [('state', 'in', ['pending', 'failed'])]
        if model_ref:
            synchronization_config = self.get_config_by_model_name(model_ref)
            domain.append(('synchronization_config', '=', synchronization_config))
        if sync_type:
            domain.append(('sync_type', '=', sync_type))
        return self.search(domain)

    @api.model
    def get_latest_log_per_record(self, res_id, model_ref=None):
        domain = []
        if model_ref:
            synchronization_config = self.get_config_by_model_name(model_ref)
            domain.append(('synchronization_config', '=', synchronization_config.id))
        if res_id:
            domain.append(('res_id', '=', res_id))
        return self.search(domain, order='create_date desc', limit=1)

    @api.model
    def _cron_sync(self):
        """This CRON Job will check for all pending and failed queues, and will attempt to send them one by one.
        It is separated in two-parts, first outgoing requests and then the incoming requests."""
        pending_failed_outgoing_records = self.get_pending_failed_records()
        outgoing_api_id = self.env['outgoing.api.key'].search([('valid', '=', True), ('name', '=', 'ext_project_app')], limit=1)
        for record in pending_failed_outgoing_records:
            try:
                mapped_external_field = record.external_fields_mapping(ast.literal_eval(record.data))
                outgoing_api_id.send_data_to_api(json.dumps(mapped_external_field))
            except Exception as e:
                record.latest_error_message = str(e)
                record.state = 'failed'
                continue
            record.state = 'success'

        pending_failed_incoming_records = self.get_pending_failed_records(sync_type='incoming')
        for record in pending_failed_incoming_records:
            try:
                data = ast.literal_eval(record.data)
                if record.type == 'create':
                    if data:
                        data['external_project_id'] = record.external_id
                        data['last_sync_date'] = record.internal_last_updated
                        data['synced_boolean'] = True
                    res = self.env[record.synchronization_config.model_id.model].with_context({"apisync-incoming": True}).create(data)
                    record.res_id = res.id
                if record.type == 'update':
                    if data:
                        data['last_sync_date'] = record.internal_last_updated
                        data['synced_boolean'] = True
                    self.env[record.synchronization_config.model_id.model].browse(record.res_id).with_context({"apisync-incoming": True}).write(data)
                if record.type == 'delete':
                    self.env[record.synchronization_config.model_id.model].browse(record.res_id).with_context({"apisync-incoming": True}).unlink()  # Maybe soft-delete?
            except Exception as e:
                record.latest_error_message = str(e)
                record.state = 'failed'
                continue
            record.state = 'success'
