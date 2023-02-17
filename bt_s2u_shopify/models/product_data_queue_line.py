import requests
import json
import logging
import datetime
import re
import time
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ShopifyProductDataqueueLineEpt(models.Model):
    _name = "bt_s2u_shopify.product.data.queue"
    _description = 'Shopify Product Data Queue'

    shopify_instance_id = fields.Many2one('s2u.shopify.instance', string='Instance')
    last_process_date = fields.Datetime('Last Process Date', readonly=True)
    synced_product_data = fields.Text(string='Synced Product Data')
    product_data_id = fields.Char(string='Product Data Id')
    state = fields.Selection([('draft', 'Draft'), ('failed', 'Failed'), ('done', 'Done'),
                              ("cancel", "Cancelled")],
                             default='draft')
    name = fields.Char(string="Product", help="It contain the name of product")

    
    def shopify_import_update_product(self):
        self.shopify_instance_id.process_shopify_product_data_queue([self])
        return  True