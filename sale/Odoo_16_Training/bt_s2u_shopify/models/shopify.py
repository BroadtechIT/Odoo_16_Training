# -*- coding: utf-8 -*-

import requests
import json
import logging
import datetime
import re
import time
import base64
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
# from __builtin__ import False

_logger = logging.getLogger(__name__)


class ShopifyInstance(models.Model):
    _inherit = 's2u.shopify.instance'
    
    
    pricelist_id = fields.Many2one('product.pricelist', 'Pricelist')
    fiscal_position_id = fields.Many2one('account.fiscal.position', 'Fiscal Position')
    journal_id = fields.Many2one('account.journal', 'Shopify Payment Journal')
    paypal_journal_id = fields.Many2one('account.journal', 'Paypal Payment Journal')
    sales_team_id = fields.Many2one('crm.team', 'Sales Team')
    location_ids = fields.Many2many('stock.location', string='Stock Locations')
    usa_customer_warehouse_id = fields.Many2one('stock.warehouse', 'USA Customer Warehouse')
    ca_customer_warehouse_id = fields.Many2one('stock.warehouse', 'CANDA Customer Warehouse')
    
    
    

    def cleanhtml(self, raw_html):
        cleanr = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext
    
    
    def do_get_shopify_customer(self):
        partner_env = self.env['res.partner']
        event_env = self.env['s2u.shopify.event']
        
        for instance in self:
            url = instance.get_url('customers') + '?limit=250'
            
            replace_url = "%s:%s@%s.myshopify.com" % (instance.shopify_api_key,
                        instance.shopify_password,
                        instance.shopify_shop)
            
            
            continueprocess = True
            default_code = []
            rr = 0
            while continueprocess is True:
                response = requests.get(url)
                rr += 200
                res = json.loads(response.content.decode('utf-8'))
                response_header = response.headers
                if res.get('customers', False):
                    for customer in res['customers']:
                        partner_obj = partner_env.search([('shopify_id', '=', customer['id'])], limit=1)
                        if not partner_obj:
                            if 'default_address' in customer:
                                if customer['default_address']['first_name']:
                                    email = customer['email']
                                    partner = event_env.match_partner(email, customer['default_address'])
                                    for address in customer['addresses']:
                                        if address['first_name']:
                                            event_env.match_partner(email, address, partner=partner)
                            else:
                                name = customer['first_name']
                                if name:
                                    if customer['last_name']:
                                        name +=  ' ' + customer['last_name']
                                    partner_vals = {
                                        'name': name,
                                        'email': customer['email'] if customer['email'] else False,
                                        'shopify_id': customer['id'],
                                        'phone': customer['phone'] if customer['phone'] else False,
                                        }
                                    partner_env.create(partner_vals)
                            
                if 'Link' in response_header and 'next' in response_header['Link']:
                    next_url = response_header['Link'].split(', ')
                    
                    if len(next_url) > 1:
                        next_url = next_url[1]
                    else:
                        next_url = next_url[0]
                        
                    next_url = next_url.replace(instance.shopify_shop + 'myshopify.com', replace_url)
                    next_url = next_url.replace('<', '').replace('>', '')
                    next_url = next_url.split('customers.json')
                    next_url = next_url[1].replace(', https://anzie.myshopify.com/admin/api/2022-01/', '')
                    next_url1 = url.split('customers.json')
                    url = next_url1[0] + 'customers.json' + next_url
                else:
                    continueprocess = False
        return True
    
    def do_get_shopify_product(self):
        product_attribute_value_obj = self.env['product.attribute.value']
        category_pool = self.env['product.category']
        prod_template_pool = self.env['product.template']
        product_pool = self.env['product.product']
        mapping_template_pool = self.env['s2u.shopify.mapping.template']
        mapping_product_pool = self.env['s2u.shopify.mapping.product']
        product_data_queue_pool = self.env['bt_s2u_shopify.product.data.queue']
        product_id = []
        decative_product = []
        for instance in self:
            url = instance.get_url('products') + '?limit=250'
            
            replace_url = "%s:%s@%s.myshopify.com" % (instance.shopify_api_key,
                        instance.shopify_password,
                        instance.shopify_shop)
            
            
            continueprocess = True
            default_code = []
            rr = 0
            while continueprocess is True:
                response = requests.get(url)
                rr += 200
                res = json.loads(response.content.decode('utf-8'))
                response_header = response.headers
                if res.get('products', False):
                    for product in res['products']:
                        # if product['id'] == 7859098681591:
                            data_queue_ids = product_data_queue_pool.search([('product_data_id', '=', product['id'])])
                            data = json.dumps(product)
                            product_data_queue = {
                                'name': product['title'],
                                'product_data_id': product['id'],
                                'synced_product_data': data,
                                'state': 'draft',
                                'shopify_instance_id': instance.id,
                                'last_process_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                                }
                            if not data_queue_ids:
                                data_queue = product_data_queue_pool.create(product_data_queue)
                                
                            else:
                                data_queue_ids.update(product_data_queue)
                            
                if 'Link' in response_header and 'next' in response_header['Link']:
                    next_url = response_header['Link'].split(', ')
                    
                    if len(next_url) > 1:
                        next_url = next_url[1]
                    else:
                        next_url = next_url[0]
                        
                    next_url = next_url.replace(instance.shopify_shop + 'myshopify.com', replace_url)
                    next_url = next_url.replace('<', '').replace('>', '')
                    next_url = next_url.split('products.json')
                    next_url = next_url[1].replace(', https://anzie.myshopify.com/admin/api/2022-01/', '')
                    next_url1 = url.split('products.json')
                    url = next_url1[0] + 'products.json' + next_url
                else:
                    continueprocess = False
        return True
    
    
    def process_shopify_product_data_queue(self, product_data_queue_obj=False):
        product_attribute_value_obj = self.env['product.attribute.value']
        category_pool = self.env['product.category']
        prod_template_pool = self.env['product.template']
        product_pool = self.env['product.product']
        mapping_template_pool = self.env['s2u.shopify.mapping.template']
        mapping_product_pool = self.env['s2u.shopify.mapping.product']
        product_data_queue_pool = self.env['bt_s2u_shopify.product.data.queue']
        product_id = []
        decative_product = []
        product_data_queue_objs = False
        if product_data_queue_obj:
            product_data_queue_objs = product_data_queue_obj
        else:
            product_data_queue_objs = product_data_queue_pool.search([('state', '=', 'draft')], limit=100)
        prod_category = {categ.name:categ.id for categ in category_pool.search([])}
        
        shopify_location_id = ''
        if product_data_queue_objs:
            location_url = product_data_queue_objs[0].shopify_instance_id.get_url('locations')
            response = requests.get(location_url)
            try:
                location_res = json.loads(response.content.decode('utf-8'))
            except:
                location_res = False
            if not location_res or len(location_res['locations']) < 1:
                raise UserError(_('No locations found in shopify'))
            shopify_location_id = location_res['locations'][0]['id']
        
        
        for product_data in product_data_queue_objs:
            
            product = json.loads(product_data.synced_product_data)
            if product.get('status', False) != 'archived':
                prod_template_objs =  False
                mapping_template_obj = False
                template_vals = {
                    'shopify_id': product['id'],
                    'name': product['title'],
                    'description': self.cleanhtml(product['body_html']),
                    'company_id': product_data.shopify_instance_id.company_id.id,
                    'type': 'product',
                    'description_sale': product.get('description', ''),
                    'active': True,
                    }
                 
                options = []
                if product.get('options'):
                    options = product.get('options') 
                 
                     
                if product.get('product_type', False):
                    if product['product_type'] in prod_category:
                        template_vals['categ_id'] = prod_category[product['product_type']]
                    else:
                        categ_vals = {'name': product['product_type']}
                        cate_obj = category_pool.create(categ_vals)
                        prod_category[cate_obj.name] = cate_obj.id
                        template_vals['categ_id'] = cate_obj.id
                else:
                    categ_obj = category_pool.search([], limit=1)
                    if categ_obj:
                        template_vals['categ_id'] = categ_obj.id
                
                
                        
                created_variants = {}        
                        
                for variation in product.get('variants', []):
                    sku = variation.get('sku')
                    if sku:
                        list_price = variation['price']
                        product_obj = product_pool.search(['|', ('default_code', '=', sku),('shopify_product_id', '=', variation["id"])], limit=1)
                        if not product_obj:
                            
                            if not sku.islower() and not sku.isupper():
                                sku = sku.upper()
                                product_obj = product_pool.search(['|', ('default_code', '=', sku),('shopify_product_id', '=', variation["id"])], limit=1)
                                if not product_obj:
                                    sku = sku.lower()
                                    product_obj = product_pool.search(['|', ('default_code', '=', sku),('shopify_product_id', '=', variation["id"])], limit=1)
                            if not product_obj:
                                if sku.islower():
                                    sku = sku.upper()
                                else:
                                    sku = sku.lower()
                                
                                product_obj = product_pool.search(['|', ('default_code', '=', sku),('shopify_product_id', '=', variation["id"])], limit=1)
                        print('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',product_obj,sku)     
                        if not product_obj:
                            template_vals.update({
                                'default_code': variation.get('sku'),
                                'shopify_product_id': variation["id"],
                                'list_price': list_price,
                                'shopify_product_price':  variation['price'],
                                })
                            product_obj = product_pool.create(template_vals)
                            if template_vals.get('shopify_id', False):
                                del template_vals['shopify_id']
                        else:
                            product_obj.shopify_product_id = variation["id"]
                            if template_vals.get('shopify_id', False):
                                product_obj.product_tmpl_id.shopify_id = template_vals['shopify_id']
                                del template_vals['shopify_id']
                        
                        if product_obj.product_tmpl_id.shopify_id == product['id']:
                            prod_template_objs = product_obj.product_tmpl_id
                        else:
                            prod_template_objs = prod_template_pool.search([('shopify_id', '=', product['id'])], limit=1)
                            if not prod_template_objs:
                                product_obj.product_tmpl_id.shopify_id = product['id']
                                prod_template_objs = product_obj.product_tmpl_id
                        
                        mapping_template_vals = {}
                        if prod_template_objs:
                            
                            mapping_template_obj = mapping_template_pool.search([
                                ('instance_id', '=', product_data.shopify_instance_id.id),
                                ('product_tmpl_id', '=', prod_template_objs.id),
                                ])
                                
                            mapping_template_vals = {
                                    'shopify_id': product['id'],
                                    'instance_id': product_data.shopify_instance_id.id,
                                    'state': 'link',
                                    'shopify_manual': True,
                                    'product_tmpl_id': prod_template_objs.id,
                                    'use_odoo_inventory': True,
                                    'shopify_location_id': shopify_location_id,
                                    }
                           
                        if not mapping_template_obj and mapping_template_vals:
                            mapping_template_obj = mapping_template_pool.create(mapping_template_vals)
                        else:
                            mapping_template_obj.update(mapping_template_vals)
                        if  mapping_template_obj:
                            vals_mapping_product = {
                                'mapping_template_id': mapping_template_obj.id,
                                'product_id': product_obj.id,
                                'shopify_id': variation["id"],
                                'inventory_item_id': variation['inventory_item_id']
                            }
                            mapping_product_obj = mapping_product_pool.search([('shopify_id', '=', variation["id"])])
                            if not mapping_product_obj:
                                mapping_product_obj = mapping_product_pool.create(vals_mapping_product)
                            else:
                                mapping_product_obj.update(vals_mapping_product)
                        if variation["id"] not in created_variants:
                            created_variants[variation["id"]] = product_obj
                        
                        
                                    
                        
                    else:
                        print('XXXXXXXXXXXXXXXX Products Without SKU XXXXXXXXXXXXXXXXXXXXX',product['id'],sku)
                        
                self.import_product_images(product, created_variants)
                
            product_data.state = 'done'
        
        return True
    
    
    def import_product_images(self, product, created_variants):
        if product.get('images',[]): 
            image_assigned = False
            for image in product['images']:
                if 'src' in image and image['variant_ids']:
                    image_data = base64.b64encode(requests.get(image['src']).content).replace(b"\n", b"")
                    for variant in image['variant_ids']:
                        if variant in created_variants:
                            created_variants[variant].image_1920 = image_data
                            image_assigned = True
            if not image_assigned:
                image_data = base64.b64encode(requests.get(product['images'][0]['src']).content).replace(b"\n", b"")
                for prod in created_variants.values():
                    prod.image_1920 = image_data

class ShopifyEvent(models.Model):
    _inherit = 's2u.shopify.event'
    
    
    def do_action_process_event(self):

        self.ensure_one()

        if self.name == 'order_creation':
            self.bt_process_event_order_creation_update()
        if self.name == 'order_update':
            self.update_shopify_order()
        if self.name == 'order_cancelation':
            self.process_event_order_cancelation()
        if self.name == 'order_deletion':
            self.process_event_order_deletion()
        if self.name == 'order_payment':
            self.process_event_order_payment()
            
            
    def get_prepare_fiscal_position(self, partner):
        position_pool = self.env['account.fiscal.position']
        fiscal_position = False
        position_obj = False
        if partner.state_id:
            position_obj = position_pool.search([('state_ids', 'in', [partner.state_id.id]), ('company_id', '=', self.instance_id.company_id.id)])
        if not position_obj:
            position_obj = position_pool.search([('country_id', '=', partner.country_id.id), ('company_id', '=', self.instance_id.company_id.id)])
        if position_obj:
            fiscal_position = position_obj[0].id
        else:
            fiscal_position = self.instance_id.fiscal_position_id.id
        
        return fiscal_position
    
    def bt_process_event_order_creation_update(self, update_order=False):
    
        self.ensure_one()

        if not self.instance_id:
            self.write({
                'state': 'error',
                'process_message': _('No instance present')
            })
            return False

        url = self.instance_id.get_url('orders', res_id=self.res_id)
        response = requests.get(url)
        try:
            res = json.loads(response.content.decode('utf-8'))
        except:
            res = False

        if not res:
            # do nothing, try fetch order in next cron
            return False
        if res.get('errors') or res.get('error'):
            fldname = 'errors' if res.get('errors') else 'error'
            if isinstance(res[fldname], str):
                self.write({
                    'state': 'error',
                    'process_message': res[fldname]
                })
                return False
            else:
                self.write({
                    'state': 'error',
                    'process_message': json.dumps(res[fldname])
                })
                return False

        delivery_product = self.env['product.product'].search([('default_code', '=', 'delivery')])
        if not delivery_product:
            self.write({
                'state': 'error',
                'process_message': _('No product \'delivery\' defined!')
            })
            return False

        if len(delivery_product) > 1:
            self.write({
                'state': 'error',
                'process_message': _('Multiple products \'delivery\' present!')
            })
            return False

        order = res['order']
        customer = order['customer']['default_address']
        partner = self.match_partner(order['customer']['email'], customer)

        customer = order['billing_address']
        partner_invoice = self.match_partner(False, customer, partner=partner, type='invoice')
        
        partner_shipping = partner_invoice
        country_warehouse_id = False
        if 'shipping_address' in order:
            customer = order['shipping_address']
            partner_shipping = self.match_partner(False, customer, partner=partner, type='delivery')
            
        
            
            if 'country_code' in customer:
                partner_code = False
                if customer['country_code'] == 'US':
                    country_warehouse_id = self.instance_id.usa_customer_warehouse_id.id
                elif customer['country_code'] == 'CA':
                    country_warehouse_id = self.instance_id.ca_customer_warehouse_id.id
    
        fiscal_position = self.prepare_fiscal_position(partner_shipping)
        

        if update_order:
            odoo_order = self.env['sale.order'].search([('shopify_id', '=', str(order['id']))], limit=1)
            if not odoo_order:
                raise UserError(_('Order with shopify_id [%s] not found.') % order['id'])
            if odoo_order.state != 'draft':
                odoo_order.action_cancel()
                odoo_order.action_draft()
            odoo_order.order_line.unlink()
        company_id = False
        if self.instance_id.company_id:
            company_id = self.instance_id.company_id.id
        team_id = self.env['crm.team'].search([('company_id', '=', company_id)], limit=1) 
        sale_team_id = False
        if team_id:
            sale_team_id = team_id.id
            
        
        vals = {
            'shopify_id': order['id'],
            'partner_id': partner.id,
            'partner_invoice_id': partner_invoice.id,
            'partner_shipping_id': partner_shipping.id,
            'note': order['note'] if order['note'] else False,
            'origin': 'Shopify',
            'reference': order['name'],
            'fiscal_position_id': fiscal_position.id if fiscal_position else False,
            'warehouse_id': country_warehouse_id,
#             'company_id': company_id,
#             'team_id': sale_team_id,
#             'sale_order_template_id': False,
#             'lead_source': 'referral',
        }

        currency_obj = self.env['res.currency'].search([('name', '=', order['currency'])], limit=1)
        if currency_obj:
            vals['currency_id'] = currency_obj.id
            
        salesperson = self.instance_id.company_id and self.instance_id.company_id.shopify_user_id or False
        if salesperson:
            vals['user_id'] = salesperson.id
        else:
            salesperson_config = self.env['ir.config_parameter'].sudo().search([('key', '=', 's2u_shopify.salesperson')], limit=1)
            vals['user_id'] = int(salesperson_config.value)

        order_lines = []
        for line in order['line_items']:
            
            sale_line_vals = {
                'name': line['name'],
                'price_unit': float(line['price']),
                'discount': float(line['total_discount']),
                'product_uom_qty': line['quantity'],
                }
            
            product_id = False
            if line['variant_id']:
                mapping_product = self.env['s2u.shopify.mapping.product'].search([('shopify_id', '=', str(line['variant_id']))], limit=1)
                if not mapping_product:
    #                 if company_id != 2:
    #                     raise UserError(_('Mapping product [%s / %s] not found.') % (line['variant_id'], line['title']))
    #                 else:
                    continue
                product_id = mapping_product.product_id.id
                
            else:
                no_product_obj = self.env['product.product'].search([('default_code', '=', 'No_Product')], limit=1)
                if no_product_obj:
                    product_id = no_product_obj.id
                    
            sale_line_vals.update({'product_id': product_id})
            order_lines.append((0, 0, sale_line_vals))
        try:
            tot_discounts = float(order['total_discounts'])
        except:
            tot_discounts = 0.0
        if tot_discounts:
            discount_product = self.env['ir.config_parameter'].sudo().search([('key', '=', 's2u_shopify.discount_product')], limit=1)
            if not discount_product:
                self.write({
                    'state': 'error',
                    'process_message': _('No discount product defined!')
                })
                return False
            discount_product = self.env['product.product'].browse(int(discount_product.value))
            order_lines.append((0, 0, {
                'name': discount_product.name,
                'price_unit': -1.0 * tot_discounts,
                'product_id': discount_product.id,
                'product_uom_qty': 1
            }))

        for line in order['shipping_lines']:
            order_lines.append((0, 0, {
                'name': line['title'],
                'price_unit': float(line['price']),
                'product_id': delivery_product.id,
                'product_uom_qty': 1
            }))
        if order_lines:
            vals['order_line'] = order_lines
        else:
            self.write({
                    'state': 'error',
                    'process_message': _('No relevant order line exist!')
                })
            return False

        if update_order:
            odoo_order.write(vals)
        else:
            odoo_order = self.env['sale.order'].create(vals)
#         if round(odoo_order.amount_total, 2) != round(float(order['total_price']), 2):
#             if company_id != 2:
#                 raise UserError(_('Total amount mismatch! Checks VAT\'s.'))

        odoo_order.action_confirm()
        if order.get('fulfillment_status') == 'fulfilled':
            tracking_number = []
            if 'fulfillments' in order:
                for track_data in order['fulfillments']:
                    if track_data['tracking_number']:
                        tracking_number.append(track_data['tracking_number'])
                tracking_number=', '.join(tracking_number)
        
            pickings = self.fulfilled_shopify_order(odoo_order)
            if pickings:
                pickings.carrier_tracking_ref = tracking_number
                odoo_order.carrier_tracking_ref = tracking_number
                moves = odoo_order._create_invoices()
                moves.action_post()
        
        self.write({
            'state': 'processed',
            'process_message': odoo_order.name
        })
        return order
        
        
        
        
    def update_shopify_order(self):
        self.ensure_one()
    
        if not self.instance_id:
            self.write({
                'state': 'error',
                'process_message': _('No instance present')
            })
            return False
        
        url = self.instance_id.get_url('orders', res_id=self.res_id)
        response = requests.get(url)
        try:
            res = json.loads(response.content.decode('utf-8'))
        except:
            res = False

        if not res:
            # do nothing, try fetch order in next cron
            return False
        if res.get('errors') or res.get('error'):
            fldname = 'errors' if res.get('errors') else 'error'
            if isinstance(res[fldname], str):
                self.write({
                    'state': 'error',
                    'process_message': res[fldname]
                })
                return False
            else:
                self.write({
                    'state': 'error',
                    'process_message': json.dumps(res[fldname])
                })
                return False
            
        
        if res['order'].get('fulfillment_status') == 'fulfilled':
            tracking_number = []
            if 'fulfillments' in res['order']:
                for track_data in res['order']['fulfillments']:
                    tracking_number.append(track_data['tracking_number'])
                tracking_number=', '.join(tracking_number)
            sale_obj = self.env['sale.order'].search([('shopify_id', '=', self.res_id)], limit=1)
            if sale_obj:
                pickings = self.fulfilled_shopify_order(sale_obj)
                not_done = pickings.filtered(lambda x:x.state not in ['cancel', 'done'])
                if not_done:
                    self.write({
                    'state': 'retry',
                    'process_message': 'Picking not processed'
                })
                else:
                    pickings.carrier_tracking_ref = tracking_number
                    sale_obj.carrier_tracking_ref = tracking_number
                    moves = sale_obj._create_invoices()
                    moves.action_post()
                    self.write({
                        'state': 'processed',
                        'process_message': 'Picking processed'
                        })
        else:
            self.write({
                    'state': 'retry',
                    'process_message': 'fulfillment_status not found'
                })
        return True
    

    def fulfilled_shopify_order(self, sale_obj):
        if sale_obj.state not in ["sale", "done", "cancel"]:
            date_order = sale_obj.date_order
            sale_obj.action_confirm()
            sale_obj.write({'date_order': date_order})
            
            # self.fulfilled_picking_for_shopify(sale_obj.picking_ids.filtered(lambda x:x.location_dest_id.usage != "customer"))
            
        return self.fulfilled_picking_for_shopify(sale_obj.picking_ids.filtered(lambda x:x.location_dest_id.usage == "customer"))

    def fulfilled_picking_for_shopify(self, pickings):
        for picking in pickings.filtered(lambda x:x.state not in ['cancel', 'done']):
            picking.action_confirm()
            picking.action_assign()
            for line in picking.move_ids_without_package:
                line.quantity_done = line.product_uom_qty
            picking.button_validate()
            # wiz = picking.button_validate()
            # wiz = self.env['stock.backorder.confirmation'].create({'pick_ids': [(4, p.id) for p in picking]})
            # wiz.process() 
            # wiz = Form(self.env['stock.immediate.transfer'].with_context(wiz['context'])).save().process()
            
            
            # res_dict = picking.button_validate()
            #
            # wizard = Form(picking._action_generate_immediate_wizard()).save()
            # res_dict = wizard.process()
            # wizard = Form(picking._action_generate_backorder_wizard()).save()
            # wizard.process()
            
            
        return pickings
    
    
    
    
    def process_event_order_payment(self):

        self.ensure_one()

        if not self.instance_id:
            self.write({
                'state': 'error',
                'process_message': _('No instance present')
            })
            return False

        url = self.instance_id.get_url('orders', res_id=self.res_id)
        response = requests.get(url)
        try:
            res = json.loads(response.content.decode('utf-8'))
        except:
            res = False

        if not res:
            # do nothing, try fetch order in next cron
            return False

        if res.get('errors') or res.get('error'):
            fldname = 'errors' if res.get('errors') else 'error'
            if isinstance(res[fldname], str):
                self.write({
                    'state': 'retry',
                    'process_message': res[fldname]
                })
                return False
            else:
                self.write({
                    'state': 'retry',
                    'process_message': json.dumps(res[fldname])
                })
                return False

        order = res['order']
        odoo_order = self.env['sale.order'].search([('shopify_id', '=', str(order['id']))], limit=1)
        if not odoo_order:
#             raise UserError(_('Order with shopify_id [%s] not found.') % order['id'])
            self.write({
                    'state': 'retry',
                    'process_message': 'Order with shopify_id ' + str(order['id']) + ' not found'
                })
            return False

        for invoice in odoo_order.invoice_ids:
            if invoice.amount_residual <= 0.0:
                continue
            payment_vals = {}
            if invoice.is_inbound():
                domain = [('payment_type', '=', 'inbound')]
            else:
                domain = [('payment_type', '=', 'outbound')]
            payment_method_id = self.env['account.payment.method'].search(domain, limit=1).id
            journal_id = self.instance_id.journal_id.id
            if 'payment_gateway_names' in order:
                if 'paypal' in order['payment_gateway_names']:
                    journal_id  = self.instance_id.paypal_journal_id.id
            payment_vals.update({
                'journal_id': journal_id,
                'amount': invoice.amount_residual,
                'date': fields.Date.today(),
                'partner_id': invoice.partner_id.id,
                'currency_id': invoice.currency_id.id,
                'payment_method_id': payment_method_id,
                })
            
            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()
            
            payment_lines = payment.line_ids
            domain = [('account_internal_type', 'in', ('receivable', 'payable')), ('reconciled', '=', False)]
            reconcile_lines = (payment.line_ids + invoice.line_ids).filtered_domain(domain)
            for account in payment_lines.account_id:
                reconcile_lines.filtered_domain([('account_id', '=', account.id), ('reconciled', '=', False)]).reconcile()

        self.write({
            'state': 'processed',
            'process_message': odoo_order.name
        })

        return odoo_order
    
    def match_partner(self, email_address, customer, partner=False, type=False):

        if partner and self.check_same_address(partner, customer):
            return partner

        country = self.env['res.country'].search([('code', '=', customer['country_code'])], limit=1)
        country_id = False
        # if not country:
        #     raise UserError(_('Country with code [%s] not found.') % customer['country_code'])
        if country:
            country_id = country.id
        country_state = False
        if customer['province_code']:
            country_state = self.env['res.country.state'].search([('country_id', '=', country.id),
                                                                  ('code', '=', customer['province_code'])], limit=1)
            if not country_state:
                country_state = self.env['res.country.state'].create({
                    'country_id': country.id,
                    'code': customer['province_code'],
                    'name': customer['province']
                })

        customer_id = customer.get('customer_id')

        vals = {
            'shopify_id': str(customer['customer_id']) if customer_id else False,
            'type': type if type else 'contact',
            'name': customer['name'],
            'email': email_address if email_address else False,
            'phone': customer['phone'] if customer['phone'] else False,
            'street': customer['address1'] if customer['address1'] else False,
            'street2': customer['address2'] if customer['address2'] else False,
            'zip': customer['zip'] if customer['zip'] else False,
            'city': customer['city'] if customer['city'] else False,
            'country_id': country_id,
            'state_id': country_state.id if country_state else False
        }

        if customer_id:
            match = self.env['res.partner'].search([('shopify_id', '=', str(customer['customer_id']))], limit=1)
        else:
            match = False

        if match:
            if customer['company']:
                if match.parent_id:
                    match.parent_id.write({
                        'name': customer['company']
                    })
                else:
                    parent = self.env['res.partner'].create({
                        'is_company': True,
                        'name': customer['company'],
                    })
                    vals['parent_id'] = parent.id
            match.write(vals)
            return match
        else:
            if customer['company']:
                parent = self.env['res.partner'].create({
                    'is_company': True,
                    'name': customer['company'],
                })
                vals['parent_id'] = parent.id
            return self.env['res.partner'].create(vals)
   
    @api.model
    def cron_process_events(self):
        """WARNING: meant for cron usage only - will commit() after each validation!"""

        _logger.info('Start process Shopify events ...')

        self._cr.commit()

        todos = self.env['s2u.shopify.event'].search([('state', 'in', ['new', 'retry'])], order='id')
        for t in todos:
            try:
                if t.shopify_test:
                    t.write({
                        'state': 'processed',
                        'process_message': 'TEST EVENT'
                    })
                else:
                    if t.name == 'order_creation':
                        t.bt_process_event_order_creation_update()
                    if t.name == 'order_update':
                        t.update_shopify_order()
                    if t.name == 'order_cancelation':
                        t.process_event_order_cancelation()
                    if t.name == 'order_deletion':
                        t.process_event_order_deletion()
                    if t.name == 'order_payment':
                        t.process_event_order_payment()
                self._cr.commit()
            except Exception as e:
                self._cr.rollback()
                _logger.error('Shopify process event failed: [%s] with id: [%s]' % (t.name, t.res_id))
                t.write({
                    'state': 'error',
                    'process_message': e
                })
                self._cr.commit()

    

class ShopifyMappingTemplate(models.Model):
    _inherit = 's2u.shopify.mapping.template'
    
    
    last_sync_done = fields.Datetime(string='Last Price Export On')
    
    
    def export_shopify_product_price(self):
        mapping_template_pool = self.env['s2u.shopify.mapping.template']
        for template_obj in mapping_template_pool.search([]):
            template_obj.do_update_product_price()
        return True
    
    def do_update_product_price(self):

        self.ensure_one()

        url = self.instance_id.get_url('products', res_id=self.shopify_id)
        product_data = {
            'product': {
                'id': int(self.shopify_id),
                'variants': []
                }
            }
        for mapping_product in self.mapping_product_ids:
            price = mapping_product.product_id.list_price
            if self.instance_id.pricelist_id:
                price = self.instance_id.pricelist_id.price_get(mapping_product.product_id.id, 1)[self.instance_id.pricelist_id.id]
            product_data['product']['variants'].append({
                'id': int(mapping_product.shopify_id),
                'price': str(price),
                })
        
        response = requests.put(url, data=json.dumps(product_data),
            headers = {
                 "Content-Type": "application/json",
                 "X-Shopify-Access-Token": self.instance_id.shopify_password
                 })
        try:
            res = json.loads(response.content.decode('utf-8'))
        except:
            res = False

        if not res:
            raise UserError(_('No response from Shopify API.'))

        if res.get('errors') or res.get('error'):
            fldname = 'errors' if res.get('errors') else 'error'
            if isinstance(res[fldname], str):
                raise UserError(res[fldname])
            else:
                raise UserError(json.dumps(res[fldname]))

        self.write({
            'last_sync_done': fields.Datetime.now()
        })
    
    
    def do_action_inventory(self):

        self.ensure_one()

        if not self.use_odoo_inventory:
            raise UserError(_('Product is not using Odoo inventory!'))
        if not self.shopify_location_id:
            raise UserError(_('Please define Shopify location for this product!'))
        if self.product_tmpl_id.type != 'product':
            raise UserError(_('Product is not storable!'))

        url = self.instance_id.get_url('inventory_levels/set')
        for mapping_product in self.mapping_product_ids:
            qty_available = 0.0
            if self.instance_id.location_ids:
                qty_available = sum(quant.quantity for quant in self.env['stock.quant'].search([('product_id', '=', mapping_product.product_id.id), ('location_id', 'in', self.instance_id.location_ids.ids)]))
                    
            try:
                data = {
                    'location_id': int(self.shopify_location_id),
                    'inventory_item_id': int(mapping_product.inventory_item_id),
                    'available': int(qty_available)
                }
            except Exception as e:
                raise UserError(_('Please check your values!\n[%s]') % e)
            response = requests.post(url,
                                     data=json.dumps(data),
                                     headers={
                                         "Content-Type": "application/json"
                                     })
            try:
                res = json.loads(response.content.decode('utf-8'))
            except:
                res = False

            if not res:
                raise UserError(_('No response from Shopify API.'))

            if res.get('errors') or res.get('error'):
                fldname = 'errors' if res.get('errors') else 'error'
                if isinstance(res[fldname], str):
                    raise UserError(res[fldname])
                else:
                    raise UserError(json.dumps(res[fldname]))

            mapping_product.write({
                'shopify_qty': qty_available,
                'last_sync_done': fields.Datetime.now()
            })
        

    def do_action_back(self):

        self.ensure_one()

        self.mapping_product_ids.unlink()

        self.write({
            'state': 'draft'
        })
    
    
    
    
    
    def shopify_process_product_mapping(self, product, default_mapping=None, product_tmpl_id=False):
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

       
        
        mapping_productobj = self.mapping_product_ids[0]
        for variant in product['variants']:
            mapping_productobj.update({
                'shopify_id': variant['id'],
                'inventory_item_id': str(variant['inventory_item_id']) if variant.get('inventory_item_id') else False
                })
            mapping_productobj.product_id.update({
                'shopify_id': product['id'],
                'shopify_product_id': variant['id'],
                })
        self.write(vals)
        return True

        return False

    def shopify_process_product_result(self, res, default_mapping=None, product_tmpl_id=False):

        if not res:
            return False

        if res.get('errors') or res.get('error'):
            fldname = 'errors' if res.get('errors') else 'error'
            if isinstance(res[fldname], str):
                raise UserError(res[fldname])
            else:
                raise UserError(json.dumps(res[fldname]))

        product = res.get('product')
        return self.shopify_process_product_mapping(product, default_mapping=default_mapping, product_tmpl_id=product_tmpl_id)
    
    
    def do_action_create(self, update=False):

        self.ensure_one()

        url = self.instance_id.get_url('products')
        
        body_html = self.product_tmpl_id.name
        if self.product_tmpl_id.description_sale:
            body_html = self.product_tmpl_id.description_sale
        data = {
            'product': {
                'title': self.product_tmpl_id.name,
                'body_html': body_html,
                'barcode': self.product_tmpl_id.barcode,
                'sku': self.product_tmpl_id.default_code,
                'published': False,
                'variants': [],
                }
            }
        if update:
            data['product'].update({
                'id': self.shopify_id,
                })
        for mapping in self.mapping_product_ids:
            product = mapping.product_id
            variant = {
                'price': str(product.lst_price),
                'inventory_management': 'shopify',
                'sku': product.default_code,
                'title': product.name,
                'weight': str(product.weight),
                'weight_unit': 'kg',
                'barcode': product.barcode
            }
            if update:
                variant.update({
                    'id': mapping.shopify_id,
                    'product_id': self.shopify_id
                    })
            
            data['product']['variants'].append(variant)
        if not update:
            response = requests.post(url, data=json.dumps(data), headers={"Content-Type": "application/json"})
        else:
            url = self.instance_id.get_url('products', res_id=self.shopify_id)
            response = requests.put(url, data=json.dumps(data), headers={"Content-Type": "application/json"})
        try:
            res = json.loads(response.content.decode('utf-8'))
        except:
            res = False
        if not res:
            raise UserError(_('No response from Shopify API.'))

        return self.shopify_process_product_result(res, default_mapping={'shopify_manual': False}, product_tmpl_id=self.product_tmpl_id)
    
    
    
    
    
    
    
    
    
    
    
    
    @api.model
    def cron_synchronize_inventory(self):
        """WARNING: meant for cron usage only - will commit() after each validation!"""

        _logger.info('Start synchronize inventory with Shopify ...')

        self._cr.commit()

        todos = self.env['s2u.shopify.mapping.product'].search([('use_odoo_inventory', '=', True)])
        for t in todos:
            # skip not storable
            if t.product_id.type != 'product':
                continue
            if not t.inventory_item_id:
                continue
            if not t.mapping_template_id.shopify_location_id:
                continue
            if not t.last_sync_done or (t.shopify_qty != t.product_id.qty_available):
                try:
                    qty_available = 0.0
                    if t.mapping_template_id.instance_id.location_ids:
                        qty_available = sum(quant.quantity for quant in self.env['stock.quant'].search([('product_id', '=', t.product_id.id), ('location_id', 'in', t.mapping_template_id.instance_id.location_ids.ids)]))
                    data = {
                        'location_id': int(t.mapping_template_id.shopify_location_id),
                        'inventory_item_id': int(t.inventory_item_id),
                        'available': int(qty_available)
                    }
                except:
                    data = False
                if not data:
                    continue

                url = t.mapping_template_id.instance_id.get_url('inventory_levels/set')

                try:
                    response = requests.post(url,
                                             data=json.dumps(data),
                                             headers={
                                                 "Content-Type": "application/json"
                                             })
                    res = json.loads(response.content.decode('utf-8'))

                    if not res:
                        _logger.error('Shopify synchronization inventory failed for product: [%s] with id: [%d] -> No response from API' % (t.product_id.name, t.product_id.id))
                    elif res.get('errors') or res.get('error'):
                        fldname = 'errors' if res.get('errors') else 'error'
                        if isinstance(res[fldname], str):
                            _logger.error('Shopify synchronization inventory failed for product: [%s] with id: [%d] -> %s' % (t.product_id.name, t.product_id.id, res[fldname]))
                        else:
                            _logger.error('Shopify synchronization inventory failed for product: [%s] with id: [%d] -> %s' % (t.product_id.name, t.product_id.id, json.dumps(res[fldname])))
                    else:
                        t.write({
                            'shopify_qty': qty_available,
                            'last_sync_done': fields.Datetime.now()
                        })
                    self._cr.commit()
                except Exception as e:
                    self._cr.rollback()
                    _logger.error('Shopify synchronization inventory failed for product: [%s] with id: [%d]' % (t.product_id.name, t.product_id.id))

