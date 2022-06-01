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

directory = '/Users/josecordova/Documents/cmu/TED/output/graphs'

i=1

df_effort=pd.DataFrame()
df_triage=pd.DataFrame()
df_speedup=pd.DataFrame()
for name in os.listdir(directory):

    if not name.endswith(".csv") : 
        continue


    df = pd.read_csv(name)

    df['effort']=10-df['inaction_stand_s']

    curr_player = 'player ' + str(i)


    df_effort[name[28:-4]]=df['effort']

    df_triage[name[28:-4]]=df['action_triage_s']
    df_speedup[name[28:-4]]=df['action_speedup_s']

    i+=1
df_effort['time'] = range(0,10*len(df),10)
df_effort[df_effort<0]=0
df_effort.plot(x='time')
plt.savefig('effort.png')

df_triage['time'] = range(0,10*len(df),10)

df_triage[df_triage<0]=0
df_triage.plot(x='time')
plt.savefig('triage.png')

df_speedup['time'] = range(0,10*len(df),10)

df_speedup[df_speedup<0]=0
df_speedup.plot(x='time')
plt.savefig('speedup.png')


