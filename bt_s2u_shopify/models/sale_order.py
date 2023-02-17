# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    carrier_tracking_ref = fields.Char(string='Tracking Reference')


