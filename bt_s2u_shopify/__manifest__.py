{
    'name': 'BT Odoo Shopify',
    'version': '13.0.1.2',
    'author' : 'Your odoo partner',
    'website' : 'http://yourodoopartner.com/',
    'license': 'OPL-1',
    'category':  'eCommerce',
    'summary': 'Shopify connector to handle orders',
    'description':
        """This module integrates Shopify with Odoo.
        """,
    'depends': ['s2u_shopify'],
    'data': [
        'security/ir.model.access.csv',
        'data/crons.xml',
        'views/shopify_view.xml',
        'views/product_data_queue_line_view.xml',
        'wizard/export_shopify_views.xml',
    ],
    'qweb': [
    ],
    'installable': True,
    'auto_install': False,
}
