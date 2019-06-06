#!/usr/bin/env python3

import pandas
from os import path
import datetime as dt
import subprocess as sp


def split_chunked_text(text):
    return [chunk.split('\n') for chunk in text.rstrip('\n').split('\n\n')]


src_path = path.join(path.dirname(__file__), '190529 - Vanc data for Elliot.xlsx')
base, ext = path.splitext(src_path)
dest_path = base + ' - validation' + ext

# Expected columns:
# ID date time dose conc age weight sex baseline_Cr
xls = pandas.read_excel(src_path, converters={'date': str, 'time': str})

ptid = None

new_columns = {k:[] for k in ['2.5pct', 'median', '97.5pct', 'n_levels']}
correct = incorrect = 0
for tpl in xls.itertuples():
    for l in new_columns.values():
        l.append('')

    if 'none found' == tpl.weight: continue

    t = tpl.date.split()[0] + 'T' + tpl.time.split()[-1]
    t = dt.datetime.fromisoformat(t)
    if '00:00:00' in tpl.time:
        t += dt.timedelta(days=1)

    if tpl.ID != ptid:
        ptid = tpl.ID
        pt0 = t

        try:
            weight = float(tpl.weight)
        except:
            weight = 65.5

        # let's get some covariates...
        cockcroft_gault = ((140 - tpl.age) * weight) / (0.815 * tpl._9)
        if tpl.sex == 'f':
            cockcroft_gault *= 0.85
        elif tpl.sex == 'm':
            pass
        else:
            raise ValueError('bad sex field for ID %d: %r' % (tpl.ID, tpl.sex))

        pthx = [
            'PARAM total body weight %f kg' % weight,
            'PARAM creatinine clearance %f mL/min' % cockcroft_gault,
            'MAX 201',
            'TRY 1000000',
        ]

        print(ptid, 'C-G', cockcroft_gault)

    rel_hours = (t - pt0).total_seconds() / 60 / 60

    # Calculate everything we know up to this point...
    num_levels = sum('LEVEL' in line for line in pthx)

    my_pthx = list(pthx)
    my_pthx.append('%d h GET' % rel_hours)

    # Drive the simulator, a Unix filter
    stdin = '\n'.join(my_pthx + [''])
    result = sp.run(['/Users/elliotnunn/baypk/bin/vanc_int'],
        encoding='ascii', input=stdin, stdout=sp.PIPE, check=True)

    predict = []
    for chunk in split_chunked_text(result.stdout)[1:]:
        for line in chunk:
            if line.startswith('#'):
                predict.append(float(line.split()[3]))
    predict.sort()

    if len(predict) == 201:
        new_columns['2.5pct'][-1] = '%.1f' % predict[5]
        new_columns['median'][-1] = '%.1f' % predict[100]
        new_columns['97.5pct'][-1] = '%.1f' % predict[195]
        new_columns['n_levels'][-1] = num_levels

        if tpl.conc not in ('.', 'BLQ'):
            if predict[5] < tpl.conc < predict[195]:
                correct += 1
            else:
                incorrect += 1


    # for future simulations, incorporate this information...
    if tpl.dose != '.':
        rate = 600
        period = tpl.dose / rate
        pthx.append('%f h EV %f mg/h' % (rel_hours, rate))
        pthx.append('%f h EV %f mg/h' % (rel_hours + period, 0))

    if tpl.conc != '.':
        conc = tpl.conc
        if conc == 'BLQ': conc = 0

        # Comment this line to disable Bayesian estimation
        pthx.append('%f h LEVEL %f mg/L' % (rel_hours, conc))

    # print(new_column[-1])

for k, v in new_columns.items():
    xls[k] = v # Can't just use update() unfortunately

xls.to_excel(dest_path, index=False)

print('%d/%d (%.1f%%)' % (correct, correct+incorrect, correct*100/(correct+incorrect)))
