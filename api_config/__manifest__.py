{
    'name': 'API Secure Synchronization',
    'version': '1.0',
    'summary': 'Configure secure API, to synchronize data with external applications',
    'category': 'API',
    'depends': ['base', ],
    'data': [
        'views/api_conf_incoming.xml',
        'views/api_conf_outgoing.xml',
        'views/api_synchronization.xml',
        'data/ir_cron.xml',
        'views/groups.xml',
        'security/ir.model.access.csv',
        'views/api_menu.xml',
    ],
    'installable': True,
    'application': True,
}
