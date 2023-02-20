# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
import logging


from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SynchProductShopify(models.TransientModel):
    _name = "bt_s2u_shopify.synch.product.shopify"
    _description = "Synch Product Price To Shopify"


    def export_product_price(self):
        active_model = self.env.context.get("active_model")
        
        product_obj = self.env[active_model].browse(self._context.get('active_ids', []))
        mapping_template_env = self.env['s2u.shopify.mapping.template']
        mapping_product_env = self.env['s2u.shopify.mapping.product']
        for product in product_obj:
            template_obj = False
            if active_model == 'product.product':
                if product.shopify_product_id:
                    template_product_obj = mapping_product_env.search([('shopify_id', '=', product.shopify_product_id)])
                    if template_product_obj:
                        template_obj = template_product_obj.mapping_template_id
                elif product.shopify_id:
                    template_obj = mapping_template_env.search([('shopify_id', '=', product.shopify_id)])
                        
            if active_model == 'product.template':
                if product.shopify_id:
                    template_obj = mapping_template_env.search([('shopify_id', '=', product.shopify_id)])
                    
            if template_obj:
                template_obj.do_update_product_price()

        return {'type': 'ir.actions.act_window_close'}



class ExportProductTemplate(models.TransientModel):
    _name = 'bt_s2u_shopify.export.product.product'
    _description = 'Export Product Template'
    

    def _get_default_instance_id(self):
        instance_obj = self.env['s2u.shopify.instance'].search([], limit=1)
        if instance_obj:
            return instance_obj.id 
        return False
    
    
    instance_id = fields.Many2one('s2u.shopify.instance', 'Instance', default=_get_default_instance_id)
    
    
    
    def export_product_template(self):
        product_pool = self.env['product.product']
        template_pool = self.env['product.template']
        attribute_line_pool = self.env['product.template.attribute.line']
        product_template_attribute_value_obj = self.env['product.template.attribute.value']
        mapping_template_pool = self.env['s2u.shopify.mapping.template']
        mapping_product_pool = self.env['s2u.shopify.mapping.product']
        
        
        i = 0
        for data in self:
            active_ids = self._context.get('active_ids', [])
            product_tmp_objs = template_pool.browse(active_ids)
            for product_tmp_obj in product_tmp_objs:
                i += 1
                
                mapping_template_obj = mapping_template_pool.search([('instance_id', '=', data.instance_id.id), ('product_tmpl_id', '=', product_tmp_obj.id)])
                
                if not mapping_template_obj:
                    mapping_template_obj = mapping_template_pool.create({
                        'instance_id' : data.instance_id.id,
                        'product_tmpl_id': product_tmp_obj.id,
                        'shopify_manual': False,
                        })
                    varinat_obj = product_pool.search([('product_tmpl_id', '=', product_tmp_obj.id)], limit=1)
                    mapping_product_pool.create({
                        'mapping_template_id': mapping_template_obj.id,
                        'product_id': varinat_obj.id,
                        
                        })
                    mapping_template_obj.do_action_create()
                else:
                    if mapping_template_obj:
                        mapping_template_obj.do_action_create(True)
            
        _logger.info('Processed items (%s)'% (str(i)))
        return True
    
    
    
    