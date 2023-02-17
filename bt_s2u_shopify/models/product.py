# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    
    instance_id = fields.Many2one('s2u.shopify.instance', string='Instance', ondelete='restrict')
    
   
    
class ProductProduct(models.Model):
    _inherit = "product.product"
    
#     @api.model
#     def create(self, vals):
#         context  = self._context
#         rec = super(ProductProduct, self).create(vals)
# #         print('###########',context)
#         if 'shopify_data' in context:
#             print   ('#'*3, rec.name,'#'*3, rec.shopify_product_id,'#'*3, context['shopify_data']['id'],'#'*3, rec.default_code,'#'*3)
#         return rec
    
    
    # def _compute_product_price_extra(self):
    #     for product in self:
    #         product.price_extra = product.shopify_product_price
            
            
    shopify_product_id = fields.Char(string='Shopify Variant ID', index=True)
    shopify_product_price = fields.Float(
        string="Shopify Variant Price",
        default=0.0,
        digits='Product Price',
        )


class ShopifyMappingTemplate(models.Model):
    _inherit = 's2u.shopify.mapping.template'
    
#     active = fields.Boolean('Active')
    
    
    
    def shopify_process_product(self, product, default_mapping=None):

        vals = {
            'shopify_id': str(product['id']),
            'state': 'link'
        }
        if self.use_odoo_inventory:
            url = self.instance_id.get_url('locations')
            response = requests.get(url)
            try:
                res = json.loads(response.content.decode('utf-8'))
            except:
                res = False
            if not res or len(res['locations']) < 1:
                raise UserError(_('No locations found in shopify'))
            vals['shopify_location_id'] = res['locations'][0]['id']

        if default_mapping:
            vals.update(default_mapping)

        if len(product['variants']) == 1:
            variant = product['variants'][0]
#             if variant['title'] == 'Default Title':
            product_obj = self.env['product.product'].search([('shopify_product_id', '=', variant['id'])], limit=1)
            if product_obj:
                vals_mapping_product = {
                    'mapping_template_id': self.id,
                    'product_id': product_obj.id,
                    'shopify_id': str(variant['id']),
                    'inventory_item_id': str(variant['inventory_item_id']) if variant.get('inventory_item_id') else False
                }
                self.env['s2u.shopify.mapping.product'].create(vals_mapping_product)
                self.write(vals)
                return True
        else:
            variants_match = 0
            for variant in product['variants']:
#                 if not variant['sku']:
#                     continue
#                 if not variant['sku'].startswith('ODOO'):
#                     continue
#                 odoo_sku = variant['sku'].split('_')
#                 if len(odoo_sku) != 3:
#                     continue

                product_obj = self.env['product.product'].search([('shopify_product_id', '=', variant['id'])], limit=1)
                if not product_obj:
                    continue
#                 if product.product_tmpl_id != self.product_tmpl_id:
#                     continue

                vals_mapping_product = {
                    'mapping_template_id': self.id,
                    'product_id': product_obj.id,
                    'shopify_id': str(variant['id']),
                    'inventory_item_id': str(variant['inventory_item_id']) if variant.get('inventory_item_id') else False
                }
                self.env['s2u.shopify.mapping.product'].create(vals_mapping_product)
                variants_match += 1
            if variants_match:
                self.write(vals)
                return True

        return False
