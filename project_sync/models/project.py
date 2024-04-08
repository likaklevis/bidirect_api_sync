from odoo import fields, models, api


class ProjectInherit(models.Model):
    _inherit = 'project.project'

    external_project_id = fields.Char(string='External Project ID')
    last_sync_date = fields.Datetime(string='Last sync date')
    synced_boolean = fields.Boolean(string='Synced')

    _sql_constraints = [('external_project_id_uniq', 'unique(external_project_id)', 'External Project ID MUST be UNIQUE.')]

    def create_sync_queue(self, res):
        data_to_sync = {}
        sync_obj = self.sudo().env['synchronization.data.mapping']
        sync_config = sync_obj.get_by_model_name(self._name)
        mapped_fields = sync_config.field_mapping_to_dict()
        if mapped_fields:
            for field in mapped_fields:
                data_to_sync[field] = getattr(res, field)
        if data_to_sync:
            sync_config.create_queue('create', res.id, data_to_sync, 'outgoing', res.write_date)

    def write_sync_queue(self, res, vals):
        data_to_sync = {}
        sync_obj = self.sudo().env['synchronization.data.mapping']
        sync_config = sync_obj.get_by_model_name(self._name)
        mapped_fields = sync_config.field_mapping_to_dict()
        if mapped_fields:
            for field in mapped_fields:
                if field not in vals:
                    continue
                data_to_sync[field] = vals.get(field)
        if data_to_sync:
            sync_config.create_queue('update', res.id, data_to_sync, 'outgoing', res.write_date)

    def delete_sync_queue(self, res, ):
        sync_obj = self.sudo().env['synchronization.data.mapping']
        sync_config = sync_obj.get_by_model_name(self._name)
        sync_config.create_queue('delete', res.id, {}, 'outgoing', fields.Datetime.now())

    @api.model_create_multi
    def create(self, vals_list):
        res_list = super(ProjectInherit, self).create(vals_list)

        if not self.env.context.get('apisync-incoming'):
            for res in res_list:
                self.create_sync_queue(res)
        return res_list

    def write(self, vals):
        res = super(ProjectInherit, self).write(vals)
        if not self.env.context.get('apisync-incoming'):
            self.write_sync_queue(self, vals)
        return res

    def unlink(self):
        if not self.env.context.get('apisync-incoming'):
            self.delete_sync_queue(self)
        res = super(ProjectInherit, self).unlink()
        return res
