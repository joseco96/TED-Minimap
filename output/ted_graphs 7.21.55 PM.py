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




for name_folder in os.listdir(directory):
    if '.' in name_folder: 
        continue
    i=1

    directory_2 = '/Users/josecordova/Documents/cmu/TED/output/' + name_folder

    flag=1
    for name in os.listdir(directory_2):

        if not name.endswith(".csv") : 
            continue


        df = pd.read_csv(directory_2+'/'+name)
        if flag==1:
            df_effort=pd.DataFrame(0, index=np.arange(len(df)), columns=['Med','Eng'])
            df_triage=pd.DataFrame(0, index=np.arange(len(df)), columns=['Med','Eng'])
            df_speedup=pd.DataFrame(0, index=np.arange(len(df)), columns=['Med','Eng'])
            df_rubble=pd.DataFrame(0, index=np.arange(len(df)), columns=['Med','Eng'])
            df_exploration=pd.DataFrame(0, index=np.arange(len(df)), columns=['Med','Eng'])
            df_workload=pd.DataFrame(0, index=np.arange(len(df)), columns=['Med','Eng'])
            df_skill=pd.DataFrame(0, index=np.arange(len(df)), columns=['Med','Eng'])
            flag=0


        curr_player = 'player ' + str(i)

        if name[0]=='e':
            curr= 'Eng'
        else:
            curr='Med'
        df_exploration[curr]+=df['exploration']
        df_workload[curr]+=df['workload']
        df_skill[curr]+=df['skill_s']
        df_effort[curr]+=df['effort']

        df_triage[curr]+=df['action_triage_s']
        df_speedup[curr]+=df['action_speedup_s'] 
        df_rubble[curr]+=df['action_dig_rubble_s']


        i+=1
    df_effort['time'] = range(0,10*len(df),10)
    df_effort[df_effort<0]=0
    df_effort.plot(x='time')
    plt.xlabel('Time(s)')
    plt.ylabel('Effort')
    plt.title('Effort')
    plt.savefig(directory_2+'/effort_roles.png')

    df_triage['time'] = range(0,10*len(df),10)
    plt.xlabel('Time(s)')
    plt.ylabel('Triage (s)')
    plt.title('Triage')
    df_triage[df_triage<0]=0
    df_triage.plot(x='time')


    plt.savefig(directory_2+'/triage_roles.png')

    df_speedup['time'] = range(0,10*len(df),10)

    df_speedup[df_speedup<0]=0
    df_speedup.plot(x='time')
    plt.xlabel('Time(s)')
    plt.ylabel('Speedup (s)')
    plt.title('Speedup')

    plt.savefig(directory_2+'/speedup_roles.png')

    df_rubble['time'] = range(0,10*len(df),10)

    df_rubble[df_rubble<0]=0
    df_rubble.plot(x='time')
    plt.xlabel('Time(s)')
    plt.ylabel('Rubble (s)')
    plt.title('Rubble')

    plt.savefig(directory_2+'/rubble_roles.png')

    df_exploration['time'] = range(0,10*len(df),10)

    df_exploration.plot(x='time')
    plt.xlabel('Time(s)')
    plt.ylabel('Exploration (dist)')
    plt.title('Exploration')

    plt.savefig(directory_2+'/exploration_roles.png')

    df_workload['time'] = range(0,10*len(df),10)

    df_workload.plot(x='time')
    plt.xlabel('Time(s)')
    plt.ylabel('Workload')
    plt.title('Workload')

    plt.savefig(directory_2+'/workload_roles.png')
    df_skill['time'] = range(0,10*len(df),10)

    df_skill.plot(x='time')
    plt.xlabel('Time(s)')
    plt.ylabel('Skill (s)')
    plt.title('Skill')

    plt.savefig(directory_2+'/skill_roles.png')
