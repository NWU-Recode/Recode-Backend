import importlib, traceback
mods = [
    'app.features.submissions.service',
    'app.features.judge0.service',
    'app.features.submissions.endpoints',
    'app.features.judge0.endpoints',
    'app.features.challenges.service',
]
ok=[]
errs=[]
print('Starting imports for modules:', mods)
for m in mods:
    try:
        importlib.import_module(m)
        ok.append(m)
    except Exception as e:
        errs.append((m, traceback.format_exc()))
print('\nOK:', ok)
print('\nERR COUNT:', len(errs))
for m, tb in errs:
    print('\n--- MODULE ERROR:', m)
    print(tb)
