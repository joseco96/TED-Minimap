import sys
import json
import math
import os
import ast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import json

from sympy import false
import matplotlib.pyplot as plt

import os

directory = '/Users/josecordova/Documents/cmu/TED/output'

i=1

scores=[]
skills=[]
efforts=[]
workloads=[]
for name in os.listdir(directory):

    if not name.endswith(".csv") : 
        continue
    df= pd.read_csv(name)
    df['time'] = range(0,10*len(df),10)
    plt.figure()
    df.plot(y='process_workload_burnt',x='time')
    workloads.append(df['process_workload_burnt'].sum())
    plt.savefig(name+'workload.png')
    plt.close()

    plt.figure()
    df.plot(y='process_skill_use_s',x='time')
    skills.append(df['process_skill_use_s'].sum())

    plt.savefig(name+'skill.png')
    plt.close()

    plt.figure()
    df.plot(y='process_effort_s',x='time')
    efforts.append(df['process_effort_s'].sum())

    plt.savefig(name+'effort.png')

    plt.close()

    df['score']=df['triage_count_red']*0.45+df['triage_count_yellow']*0.35+df['triage_count_green']*0.2

    scores.append(df['score'].sum())
plt.scatter(x=skills, y=scores)
plt.savefig('skills.png')
plt.close()
plt.scatter(x=efforts, y=scores)
plt.savefig('efforts.png')
plt.close()

plt.scatter(x=workloads, y=scores)
plt.savefig('workloads.png')
plt.close()
