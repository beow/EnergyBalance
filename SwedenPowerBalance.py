# -*- coding: utf-8 -*-
"""
Created on Sun Jun 19 19:48:34 2022

Modelling Sweden in terms of electric energy balance during 2020 - 2021. From
this extrapolations in terms of adding more wind or nuclear energy can be
explored. The model assumes the following

Balance:
    Consumption + Export = Production + Import
If some constraints are mot fulfilled, balance may not be achieved and we'll
get either a shortage or excess of power.

Hourly data:
The simulation is based on hourly data during 2020-2021. A dataframe is
constructed with columns for Consumtion+Export, Constant (nuclear + heat,
based), Water inflow/outflow, Import/Export, Hydrogen need plus some other
parameters. All per hour. Power/Energy in GW (for one hour => GWh).

Power dispatch:
The balance equations are made such that
1. Consumtion (+ Export), Constant power and Wind power are given (that is,
"dispatched" first)
2. Water (hydro) power is used to balance production against consumption
3. If water capacity is not large or small enough for balancing, import or
export is used
4. If import or export limits are hit we get a shortage or an excess of power.

Wind power:
Hourly wind power production data is taken from ENTSO-E transparency platform.
To emulate more wind power in the future, the hourly values are simply scaled
with a scale factor. That is a scale factor of 2 would simply double the wind
power production, with the same statistical dispersion.

Consumtion (as well as Const power production) follows a sinusoidal curve that
emulates the usage over the year (that is higher consumption in winter, lower
in summer). Const power production have a similar pattern ( that is less power
from heat, NPP maintenance during summer).

Since the power dispatch is done in a strict order according to above, and not
based on instantaneous prices, especially the Import and Export simulations 
suffer. While in general the dispatch order is believed to be somewhat 
correct, import and export levels are manually adjusted as follows:

Export: About 35 TWh (actual export number for 20/21) is treated like 
consumtion and hence "dispatched" together with consumtion. In effect it 
raises the consumtion curve with 4 GW (4GW ~ 35 TWh yearly). Apart from this
"must carry" part Export is dispatched as described above. This mean that the
actual export limit of 10 GW (physical) is replaced by a 6 GW limit (since 4GW
is moved to consumtion).

Import: In order to not empty the water storage (in spring months, before the
spring floods begins), water power is "manually" exchanged with import power,
using a random process that amounts to about 10 TWh per year of import (which
is also the import level of 20/21). Here the random process is using an
exponential averager that smears out a uniform random flow. The goal has
been to get something that looks similar to the actual import statistics.

When increasing produced power, the consumption curve is raised to match the
extra power.

For higher levels of wind power we will get shortage and excess compared to the
target consumption (+export) curve. These deviations are hold in the 'Residual'
column. 

From this residual a store of hydrogen can be calculated as follows:
    An hour with residual excess => Increase H2 store with 0.02 kton/GW
    An hour with residual shortage => Decrease H2 store with 0.05 kton/GW
This corresponds to Power-Gas-Power cycle with 40% efficiency that is used
for adding H2 to the store when we have excess power and burning H2 in a gas
turbine to produce power when there is a shortage of power, in order to keep
the total power output on the target level. 
    

@author: Bengt J. Olsson
"""

import pandas as pd
import sys
import math
import random


def rename_cols(oprint):
#   If oprint is True then just print col names and quit
    if oprint:
        print(df.columns)
        sys.exit()
    df.rename(columns = {'Avräknad (kWh)':'Wind','Period':'Date'}, inplace = True)

def normalize():
    del df['Publiceringstidpunkt']
    df['Wind'] /= 1000000
    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d %H:%M')
    df.dropna(subset=['Wind'], inplace = True)
    
def info():
    print(df.info())
    
def balance():
    df.loc[0,'Store'] = 20000                                                  # Initiate columns 
    df.loc[0,'Pout'] = df.loc[0,'Tout']
    df.loc[0,'Waout'] = 0    #df.loc[0,'Wabase']
    df.loc[0,'Import'] = 0
    df.loc[0,'Export'] = 0
    df.loc[0,'Pnet'] = df.loc[0,'Tout'] - constexp

#    maxstore = 33600
    random.seed(5)                                                             # Parameters for the random sequence
    imp_level = 1.1                                                            # of water -> import exchange
    ema_old = imp_level
    alfa = 0.03
    for i in range(1, len(df)):                                                # Start of the hourly power balancing
        imp = 0
        exp = 0
        water = 0
        vlim = wlim
        wind = df.loc[i,'Wind']                                                     
        load =  df.loc[i,'Tout']
        con =  df.loc[i,'Nuclear']
        inflow = df.loc[i,'Inflow']
        ostore = df.loc[i-1,'Store']                                           # ostore = old store (value of hour before)

        if load - (wind + con) <= 0:                                           # Water balance equations
            water = 2                                                          # Minimum water power production
        elif load - (wind + con) >= wlim:
            water = min(vlim,ostore)
        else:
            water = min(max(load - (wind + con),2), ostore)

        if load - (wind + con + water) >= 0:                                   # Imp/exp balance equations
            imp = min(load - (wind + con + water), impl)
        else:
            exp = min((wind + con + water) - load, expl)                       # --- End balancing


        new_rand = random.random()*imp_level*2                                 # Start of water -> import exchange
        ema = alfa * new_rand + (1-alfa)*ema_old
        rand_imp = max((ema-imp_level)*9 + imp_level ,0)
        rand_imp = min(rand_imp,water,impl-imp)
        water -= rand_imp
        imp += rand_imp
        ema_old = ema                                                          #--- End water -> import exchange
        
        df.loc[i,'Store'] = ostore - water + inflow                            # Populate dataframe with new hourly data
        df.loc[i,'Waout'] = water
        df.loc[i,'Import'] = imp 
        df.loc[i,'Export'] = exp
        df.loc[i,'Pout'] = wind + water + con + imp - exp
        df.loc[i,'Pnet'] = wind + water + con + imp
        
def sinus(column,mean, amp, phase):
    df[column] = df['Date'].apply(lambda x: math.sin(x.value/5e15 + phase))    # Sinus curve over two years
    df[column] *= amp
    df[column] += mean
    
def inflow():
    df['HoY'] = df['Date'].apply(lambda x: (x.timestamp()/3600 - 438288) )     # calculates hour of year
    df['HoY'] = df['HoY'].apply(lambda x: (x + 5880) % 8784 )                  # translate timescale to start May 1
    df['Inflow'] = df['HoY'].apply(lambda x: 0.00012*x**2*math.exp(-pow(x*0.002,0.9))+2.8)  # Inflow formula (empirical)
#    df.loc[df['Date'].dt.year == 2020 ].plot(x ='Date', y='Inflow',figsize=(15,10))
#    sys.exit()
    
def scalewind():
    df['Wind'] *= scale

def estore():
    df.loc[0,'Estore'] = 0
    for i in range(1,len(df)):
        df.loc[i,'Estore'] = df.loc[i-1,'Estore'] + df.loc[i,'Wind'] - mean_power
    df.plot(x ='Date', y='Estore',figsize=(30,20))
#    df.plot(x ='Date', y='Wind',figsize=(30,20))
    sys.exit()
    
### Start main ###

# Windpower scaling
scale = 6
# Mean nuclear + heat power
conp = 7.2 # +  3.14 * (6 - scale)                                             # Constant power sources [GW]
# Water power limit
wlim = 13
# import/export limits
constexp = 4                                                                   # Constant export (added to consumtion for tout)
impl = 6
expl = 10 - constexp
# Load curve (usage)
load = 8.4 + conp + (scale-1)*3.14 + constexp                                  # Mean load (note: includes part of export "constexp")

df = pd.read_csv('WindSE20-21.csv')
rename_cols(False)
normalize()
sinus('Tout', load, 4, 0*3.14)                                                 # Construct sinus shaped target load
sinus('Nuclear', conp, 2, 0*3.14)                                              # Construct sinus shaped constant power (nuclear + heat)
inflow()                                                                       # Models inflow to hydro store
scalewind()                                                                    # Scale windstrengths
total_power = df['Wind'].sum()
mean_power = total_power / len(df)
#estore()                                                                            
balance()                                                                      # Calculate balance equations

df['Residual'] = df['Pout'] - df['Tout']                                       # Hydrogen etc. calculations
curtail = 0
shortage = 0
df.loc[0,'Hydrogen'] = 0                                                       # Hydrogen store in kton H2
df.loc[0,'eStore'] = 0                                                         # Energy store in GWh
for i in range(1,len(df)):
    df.loc[i,'eStore'] = df.loc[i-1,'eStore'] + df.loc[i,'Residual']
    if df.loc[i,'Residual'] >= 0:
        curtail += df.loc[i,'Residual']
        df.loc[i,'Hydrogen'] = df.loc[i-1,'Hydrogen'] + 0.02 * df.loc[i,'Residual']
    else:
        shortage -= df.loc[i,'Residual']
        df.loc[i,'Hydrogen'] = df.loc[i-1,'Hydrogen'] + 0.05 * df.loc[i,'Residual']
            
print("/n")
print("Prod pow + imp per year:{:> 8.2f} TWh".format(df['Pnet'].sum() / 1000 / 2))
print("Load + export per year:{:> 9.2f} TWh".format(load * 365.5 * 24 / 1000+df['Export'].sum() / 1000 / 2))
print("Inflow per year:      {:> 10.2f} TWh".format(df['Inflow'].sum() / 1000 / 2))
print("Produced water per year:{:> 8.2f} TWh".format(df['Waout'].sum() / 1000 / 2))
print("Produced wind per year:{:> 9.2f} TWh".format(df['Wind'].sum() / 1000 / 2))
print("Produced const per year:{:> 8.2f} TWh".format(df['Nuclear'].sum() / 1000 / 2))
print("Max residual load:    {:> 10.2f} GW".format(df['Residual'].max()))
print("Max overshot          {:> 10.2f} GW".format(-df['Residual'].min()))
print("Water store balance   {:> 10.2f} TWh".format((df.loc[len(df)-1,'Store'] - df.loc[0,'Store'])/1000)) 
print("Import per year       {:> 10.2f} TWh".format(df['Import'].sum() / 2 / 1000))
print("Export per year       {:> 10.2f} TWh".format((df['Export'].sum() / 2 + constexp * 365.5 * 24) / 1000))
print("Curtailed per year    {:> 10.2f} TWh".format(curtail / 2 / 1000))
print("Shortage per year     {:> 10.2f} TWh".format(shortage / 2 / 1000))
# df.plot(x ='Date', y='Store',figsize=(30,20))
#df.plot(x ='Date', y=['Pout'],figsize=(15,10))
#df.plot(x ='Date', y='Wabase')
# df.plot(x ='Date', y='Import',figsize=(30,20))
df.plot(x ='Date', y='Store', ylabel='[GWh]',figsize=(15,10))
#df.plot(x ='Date', y='Residual', ylabel='[GWh]',figsize=(15,10))
df.plot(x ='Date', y='Hydrogen', ylabel='[kton H2]',figsize=(15,10))
df.plot(x ='Date', y='eStore', ylabel='[GWh]',figsize=(15,10))
# df.plot(x ='Date', y='Pout',figsize=(15,10))
# df.plot(x ='Date', y=['Import'],figsize=(15,10))
# df.plot(x ='Date', y=['Export'],figsize=(15,10))
#df.plot(x ='Date', y=['Waout'],figsize=(15,10))

#print(df.tail(100))
year = 2021
df.loc[df['Date'].dt.year == year ].plot(x ='Date', y='Waout', ylabel='[GW]', figsize=(15,10))
#df.loc[df['Date'].dt.year == year ].plot(x ='Date', y='Store',figsize=(15,10))
#df.loc[df['Date'].dt.year == year ].plot(x ='Date', y=['Import','Export'], ylabel='[GW]', figsize=(15,10))
#df.loc[df['Date'].dt.year == year ].plot(x ='Date', y='Pnet',figsize=(15,10))
df.loc[df['Date'].dt.year == year ].plot(x ='Date', y=['Pout','Wind','Nuclear','Waout','Import','Export'], ylabel='[GW]', ylim = [0,70], figsize=(15,10))
#df.loc[df['Date'].dt.year == year ].plot(x ='Date', y='Inflow',figsize=(15,10))
# print("\nImport {}      {:> 10.2f} TWh".format(year, df.loc[df['Date'].dt.year == year, 'Import'].sum() / 1000))
# print("Export {}        {:> 10.2f} TWh".format(year, df.loc[df['Date'].dt.year == year, 'Export'].sum() / 1000))


# Vindkraftstatistik hela landet
# https://pxexternal.energimyndigheten.se/pxweb/sv/Vindkraftsstatistik/Vindkraftsstatistik/EN0105_1.px/table/tableViewLayout2/
# Helårsstatistik
# https://www.energimyndigheten.se/nyhetsarkiv/2022/fortsatt-hog-elproduktion-och-elexport-under-2021/