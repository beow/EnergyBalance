# -*- coding: utf-8 -*-
"""
Created on Sun Jun 19 19:48:34 2022


Modelling Sweden in terms of electric energy balance during 2020 - 2021. From
this extrapolations in terms of adding more wind or Heat energy can be
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
1. Consumtion, Constant power and Wind power are given (that is,
"dispatched" first)
2. Water (hydro) power is used to balance production against consumption
3. Hydrogen production is adjusted within limits when water balancing
   is not enough
3. If still not balanced, import or export is used
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

Hydrogen production is handled in terms of energy needed to produce it. "eStore"
is an ideal store of produced H2. Energy flows into it at production rates and
energy is drained at rate corresponding to the mean production. 

                                                           
Version: 2.0, 2022-11-13

Disclaimer: Script code could need a clean-up...


@author: Bengt J. Olsson
Twitter: @bengtxyz
"""

import pandas as pd
import sys
import math


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
    global H2high, H2low                                                                 # Initiate columns
    df.loc[0,'eStore'] = 0                                                  # Water store (GWh)
    df.loc[0,'Pout'] = df.loc[0,'Consumption']                                        # Total power out
    df.loc[0,'Water'] = 0                                                      # Water power out
    df.loc[0,'Import'] = 0
    df.loc[0,'Export'] = 0
    df.loc[0,'Residual'] = 0
    df.loc[0,'Pnet'] = df.loc[0,'Consumption'] - constexp
    for i in range(1, len(df)):                                                # Start of the hourly power balancing
        imp = 0
        exp = 0
        water = 0
        eload = 0
        flex = 0
        wind = df.loc[i,'Wind']                                                     
        load =  df.loc[i,'Consumption']
        con =  df.loc[i,'Heat']
        if (wind + con) - load  >= 0:                                          # Water balance equations
            water = 2                                                          # Minimum water power production
        elif (wind + con) - load  <= -wlim:
            water = wlim
        else:
            water = max(load - (wind + con),2)
            
        if (wind + con + water) - load <= 0:
            flex = min(load - (wind+con+water), flexmax)                                                                   # Imp/exp balance equations
            imp = min(load - (wind + con + water)- flex, impl)
        else:
            eload = min((wind + con + water) - load,elyscap)
            exp = min((wind + con + water) - load - eload, expl)                       # --- End balancing

        
        df.loc[i,'Water'] = water
        df.loc[i,'Import'] = imp 
        df.loc[i,'Export'] = exp
        df.loc[i,'Pout'] = wind + water + con + imp - exp
        df.loc[i,'Pnet'] = wind + water + con + imp
        df.loc[i,'Consumption'] += eload - flex
        df.loc[i,'eStore'] = df.loc[i-1,'eStore'] + eload + (flexmax - flex) - 9.7
        H2high += eload
        H2low += flexmax - flex
        
def sinus(column,mean, amp, phase):
    df[column] = df['Date'].apply(lambda x: math.sin(x.value/5e15 + phase))    # Sinus curve over two years
    df[column] *= amp
    df[column] += mean
    
    
def scalewind():
    df['Wind'] *= scale
    
### Start main ###

# Windpower scaling
scale = 1.5                                                       # 4.3: No nuclear power 2045
# Mean Heat + heat power                                                    # 1.7: No nuclear power 2045. 7.2: same as today
conp = 20.25 # +  3.14 * (6 - scale)                                       # Constant power sources [GW]
# Water power limit
wlim = 13
# import/export limits
constexp = 0                                                                   # Constant export (added to consumtion for tout)
impl = 2.6                                                                     # 0.70 * 3.7 importkap från norge
expl = 6 # 10 - constexp
# Load curve (usage)
load = 32.6 #22.915  #+ conp + (scale-1)*3.14 + constexp                               # Mean load (note: includes part of export "constexp")
#load = 35.3  
elyscap = 0
flexmax = 9.72  
H2high = 0
H2low = 0                                                                 # Load 22.9 for 201 TWh
df = pd.read_csv('WindSE20-21.csv')
rename_cols(False)
normalize()
sinus('Consumption', load, 4, 0*3.14)                                                 # Construct sinus shaped target load
sinus('Heat', conp, 1.5, 0*3.14)                                              # Construct sinus shaped constant power (nuclear + heat)
scalewind()                                                                    # Scale windstrengths
wind_max = df['Wind'].max()
total_power = df['Wind'].sum()
mean_power = total_power / len(df)
balance()                                                                      # Calculate balance equations

df['Residual'] = df['Pout'] - df['Consumption']
curtail = df.loc[df['Residual'] > 0, "Residual"].sum()                                      # Hydrogen etc. calculations
shortage = - df.loc[df['Residual'] < 0, "Residual"].sum()                                      # Hydrogen etc. calculations

print("\n")
print("Prod power per year:        {:> 8.2f} TWh".format(df['Pnet'].sum() / 1000 / 2))
#print("Load + export per year:{:> 9.2f} TWh".format(load * 365.5 * 24 / 1000+df['Export'].sum() / 1000 / 2))
print("Load per year:             {:> 9.2f} TWh".format(df['Consumption'].sum() / 1000 / 2))
#print("Inflow per year:      {:> 10.2f} TWh".format(df['Inflow'].sum() / 1000 / 2))
print("Produced water per year:    {:> 8.2f} TWh".format(df['Water'].sum() / 1000 / 2))
print("Produced wind per year:    {:> 9.2f} TWh".format(df['Wind'].sum() / 1000 / 2))
print("Produced nuc/heat per year: {:> 8.2f} TWh".format(df['Heat'].sum() / 1000 / 2))
print("H2 production per year:     {:> 8.2f} TWh".format((H2high+H2low) / 1000 / 2))
print("Cap. util. electrolyzers:   {:> 8.2f} %".format(((H2high+H2low) / 1000 / 2)/((elyscap+flexmax)*8.76/100)))
print("Curtailed per year        {:> 10.2f} TWh".format(curtail / 2 / 1000))
# #print("Curtailed per year (H2){:> 9.2f} TWh".format(curtail / 2 / 1000))
print("Shortage per year            {:> 7.3f} TWh".format(shortage / 2 / 1000))
print("Max shortage:             {:> 10.2f} GW".format(-df['Residual'].min()))
print("Max overshot              {:> 10.2f} GW".format(df['Residual'].max()))
#print("Water store balance   {:> 10.2f} TWh".format((df.loc[len(df)-1,'Store'] - df.loc[0,'Store'])/1000)) 
print("Import per year           {:> 10.2f} TWh".format(df['Import'].sum() / 2 / 1000))
print("Export per year           {:> 10.2f} TWh".format((df['Export'].sum() / 2 + constexp * 365.5 * 24) / 1000))

start = "2020-01-01"
stop = "2021-12-31"
df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Pout','Wind','Heat','Water','Import','Export','Consumption'], ylabel='[GW]', figsize=(15,10)) # ylim = [0,70], 
#df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Import','Export'], ylabel='[GW]', figsize=(15,10)) # ylim = [0,70], 
# df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Water'], ylabel='[GWh]',figsize=(15,10))
# df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Store'], ylabel='[GWh]',figsize=(15,10))
df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['eStore'], ylabel='[GWh]',figsize=(15,10))
df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Residual'], ylabel='[GWh]',figsize=(15,10))


# Vindkraftstatistik hela landet
# https://pxexternal.energimyndigheten.se/pxweb/sv/Vindkraftsstatistik/Vindkraftsstatistik/EN0105_1.px/table/tableViewLayout2/
# Helårsstatistik
# https://www.energimyndigheten.se/nyhetsarkiv/2022/fortsatt-hog-elproduktion-och-elexport-under-2021/