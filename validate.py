#!/usr/bin/env python3

import pandas
from os import path


class Individual:
    def __init__(self, num, age, weight, sex, creatinine):
        self.num = num
        self.age = age
        self.weight = weight
        self.sex = sex
        self.creatinine = creatinine

        self.list = []



# Expected columns:
# ID date time dose conc age weight sex baseline_Cr
xls = pandas.read_excel(path.join(path.dirname(__file__), '190529 - Vanc data for Elliot.xlsx'))


individuals = []


for num in sorted(set(xls['ID'])):
    rows = xls[xls['ID'] == num]

    for field in ['age', 'weight', 'sex', 'baseline Cr']:
        print(num)
        print()
        print(repr(rows[field]))
        # assert all(rows[field] == rows[field][0])

    person = Individual(num=num,
        age=rows['age'][0], weight=rows['weight'][0], sex=rows['sex'][0], creatinine=rows['baseline Cr'][0])

    individuals.append(person)


print(individuals)



# The above code doesn't work! Suggestion... be more conservative and just add a column to the right of the table
# (after all, I am a Unix hacker...)
