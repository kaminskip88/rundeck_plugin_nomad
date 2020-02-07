jobspec = {
    'Job': {
        'ID': '',
        'Name': '',
        'Datacenters': ['dc1'],
        'Region': 'global',
        'Constraints': [],
        'Priority': 50,
        'Type': 'batch',
        'TaskGroups': [],
    }
}


groupspec = {
    'Count': 1,
    'EphemeralDisk': {
     'SizeMB': 100
    },
    'Name': 'exec',
    'ReschedulePolicy': {
     'Attempts': 0
    },
    'RestartPolicy': {
     'Attempts': 0
    },
    'Tasks': []
}

taskspec = {
    'Artifacts': None,
    'Config': {},
    'Constraints': None,
    'Driver': 'docker',
    'Env': {},
    'LogConfig': {
        'MaxFileSizeMB': 50,
        'MaxFiles': 1
    },
    'Name': 'docker',
    'Resources': {
        'CPU': 200,
        'MemoryMB': 256,
        'Networks': [
         {
            'MBits': 100
         }
        ]
    },
    'Templates': []
}

templatespec = {
    'ChangeMode': 'noop',
    'DestPath': '',
    'EmbeddedTmpl': '',
    'Perms': '0644',
    'SourcePath': ''
}
