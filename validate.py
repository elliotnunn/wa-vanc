#!/usr/bin/env python3

import pandas
from os import path
import datetime as dt
import subprocess as sp


# baypk prints chunks of text, delimited by blank lines
# The first chunk repeats the input parameters
# Each subsequent chunk corresponds with one ETA in the output population
# This format can be fed back into baypk to get the same results
def split_chunked_text(text):
    return [chunk.split('\n') for chunk in text.rstrip('\n').split('\n\n')]


# Slurp the data (which must not go on GitHub!!)
# Expected columns:
# ID date time dose conc age weight sex baseline_Cr
src_path = path.join(path.dirname(__file__), '190529 - Vanc data for Elliot.xlsx')
base, ext = path.splitext(src_path)
dest_path = base + ' - validation' + ext
xls = pandas.read_excel(src_path, converters={'date': str, 'time': str})


# We will add these columns to the output
new_columns = {k:[] for k in ['2.5pct', 'median', '97.5pct', 'n_levels']}


# Iterate (slowly) over every row of the chart,
# and run baypk for every valid line
ptid = None
correct = incorrect = 0
for tpl in xls.itertuples():
    # By default, the new columns contain blank cells at this row
    for l in new_columns.values():
        l.append('')

    # Some rows lack a weight, so ignore them
    if 'none found' == tpl.weight: continue

    # Parse these date/time fields into ISO 8601
    t = tpl.date.split()[0] + 'T' + tpl.time.split()[-1]
    t = dt.datetime.fromisoformat(t)

    # Surprising: a midnight time fields refers to 'tonight', not 'last night'
    if '00:00:00' in tpl.time:
        t += dt.timedelta(days=1)

    # Is this a new individual? Then calculate 'total body weight' and 'creatinine clearance'
    # from the baseline covariates in this row
    if tpl.ID != ptid:
        ptid = tpl.ID
        pt0 = t # The 'zero' timestamp for this patient

        try:
            weight = float(tpl.weight)
        except:
            weight = 65.5

        # Calculate creatinine clearance
        cockcroft_gault = ((140 - tpl.age) * weight) / (0.815 * tpl._9)
        if tpl.sex == 'f':
            cockcroft_gault *= 0.85
        elif tpl.sex == 'm':
            pass
        else:
            raise ValueError('bad sex field for ID %d: %r' % (tpl.ID, tpl.sex))

        # This list variable contains the text lines to go into baypk
        pthx = [
            'PARAM total body weight %f kg' % weight,
            'PARAM creatinine clearance %f mL/min' % cockcroft_gault,
            'MAX 201',
            'TRY 1000000', # If it doesn't converge in this generous time, the numbers are way off
        ]

        # Print this pt to the console
        print('ID=%03d tbw=%03d crcl=%03d' % (ptid, weight, cockcroft_gault))

    # Time in hours relative to patient's first dose
    rel_hours = (t - pt0).total_seconds() / 60 / 60

    # Feed all our info, excluding the measured level at this time point, into baypk
    num_levels = sum('LEVEL' in line for line in pthx) # How many LEVELs go into this result?
    my_pthx = list(pthx)
    my_pthx.append('%d h GET' % rel_hours)

    # baypk can be called as a simple Unix 'filter' program
    stdin = '\n'.join(my_pthx + [''])
    result = sp.run(['/Users/elliotnunn/baypk/bin/vanc_int'],
        encoding='ascii', input=stdin, stdout=sp.PIPE, check=True)

    # Get a population of predicted concentrations for this time point
    predict = []
    for chunk in split_chunked_text(result.stdout)[1:]:
        for line in chunk:
            if line.startswith('#'):
                predict.append(float(line.split()[3]))
    predict.sort()

    # Did the Bayesian algorithm get a big enough population in the time we gave it?
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

    # If this row was the start of a dose, then add to the dose list
    if tpl.dose != '.':
        rate = 600
        period = tpl.dose / rate
        pthx.append('%f h EV %f mg/h' % (rel_hours, rate))
        pthx.append('%f h EV %f mg/h' % (rel_hours + period, 0))

    # If this row was a 'conc', then feed it into the Bayesion prediction of future rows
    if tpl.conc != '.':
        conc = tpl.conc
        if conc == 'BLQ': conc = 0

        # Comment this line to disable Bayesian estimation
        pthx.append('%f h LEVEL %f mg/L' % (rel_hours, conc))

# Add these columns to the Excel spreadsheet and write it to disk
for k, v in new_columns.items():
    xls[k] = v # Can't just use update() unfortunately
xls.to_excel(dest_path, index=False)

# Print how many concs were in the confidence interval
print('%d/%d (%.1f%%)' % (correct, correct+incorrect, correct*100/(correct+incorrect)))
