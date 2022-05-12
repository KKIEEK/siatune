post_custom_hooks = [
    dict(type='RayTuneLoggerHook', filtering_key='val', priority='VERY_LOW'),
    dict(type='RayCheckpointHook', by_epoch=True, interval=1)
]

rewriters = [
    dict(type='BatchConfigPathcer'),
    dict(type='SequeunceConfigPathcer'),
    dict(type='Decouple', keys=['searched_cfg', 'base_cfg']),
    dict(type='ConfigMerger'),
    dict(type='CustomHookRegister', post_custom_hooks=post_custom_hooks),
    dict(type='Dump'),
    dict(type='SetEnv')
]