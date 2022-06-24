from cProfile import label
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
import seaborn as sns

directory = '/Users/josecordova/Documents/cmu/TED/output'

i=1

scores=[]
skills=[]
efforts=[]
workloads=[]
labels = []
CIs = []
for name in os.listdir(directory):

    if not name.endswith(".csv") : 
        continue
    labels.append(name[11]+'_'+name[21])

    df= pd.read_csv(name)
    df['time'] = range(0,10*len(df),10)
    df['process_skill_use_s']=df['process_skill_use_s']
    df['process_effort_s']= df['process_effort_s']
    plt.figure()
    df.plot(y='process_workload_burnt',x='time')
    workloads.append(df['process_workload_burnt'].sum())
    plt.xlabel('Time(s)')
    plt.ylabel('Workload')
    plt.title('Workload')
    plt.savefig(name+'workload.png')
    plt.close()

    plt.figure()
    df.plot(y='process_skill_use_s',x='time')
    skills.append(df['process_skill_use_s'].sum())
    plt.xlabel('Time(s)')
    plt.ylabel('Skill(s)')
    plt.title('Skills')
    plt.savefig(name+'skill.png')
    plt.close()

    plt.figure()
    df.plot(y='process_effort_s',x='time')
    efforts.append(df['process_effort_s'].sum())
    plt.xlabel('Time(s)')
    plt.ylabel('Effort(dist)')
    plt.title('Effort')
    plt.savefig(name+'effort.png')

    plt.close()


    df['CI']=df['process_workload_burnt']+df['process_skill_use_s']+df['process_effort_s']
    print('skill: ', df['process_skill_use_s'].min(), df['process_skill_use_s'].max())
    print('effort: ', df['process_effort_s'].min(), df['process_effort_s'].max())
    print('workload: ', df['process_workload_burnt'].min(), df['process_workload_burnt'].max())
    
    plt.figure()
    df.plot(y='CI',x='time')
    CIs.append(df['CI'].sum())

    plt.savefig(name+'CI.png')
    plt.xlabel('Time(s)')
    plt.ylabel('CI')
    plt.title('CI')
    plt.savefig(name+'CI.png')

    plt.close()


    df['score']=50*df['triage_count_red']+df['triage_count_yellow']*30+df['triage_count_green']*10

    scores.append(df['score'].sum())

colors = [ 'b' , 'c', 'g', 'y', 'm', 'k', 'r', 'peru', 'silver' ]
sns.scatterplot(x=skills, y=scores, hue=labels)
plt.xlabel('Skill')
plt.ylabel('Score')
plt.title('Skill Correlation (team_episode)')

plt.savefig('skills.png')

plt.close()
sns.scatterplot(x=efforts, y=scores, hue=labels)
plt.xlabel('Effort')
plt.ylabel('Score')
plt.title('Effort Correlation (team_episode)')
plt.savefig('efforts.png')
plt.close()

sns.scatterplot(x=workloads, y=scores, hue=labels)
plt.xlabel('Workload')
plt.ylabel('Score')
plt.title('Skill Correlation (team_episode)')
plt.savefig('workloads.png')
plt.close()

sns.scatterplot(x=CIs, y=scores, hue=labels)
plt.xlabel('CI')
plt.ylabel('Score')
plt.title('CI Correlation (team_episode)')
plt.savefig('CIs.png')
plt.close()