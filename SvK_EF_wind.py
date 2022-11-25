# -*- coding: utf-8 -*-
"""
--- License notice ---
Copyright (c) 2022 Bengt J. Olsson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
---

Created on Sun Jun 19 19:48:34 2022

Modelling Sweden in terms of electric energy balance using wind data from 
2020 - 2021. From this extrapolations in terms of adding more wind or Heat
energy can be explored. The model assumes the following

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

A balance energy store functionality is included to simulate the size of a
store needed to cover the deficit that may appear when having a large share
of wind power.

See https://adelsfors.se/2022/11/18/a-simple-balance-model-for-swedens-electricity-power-system/
for a description of the model.
                                                           
Version: 2.1.0, 2022-11-25

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
    global H2high, H2low                                                       #
    df.loc[0,'eStore'] = 0                                                     # H2 production store
    df.loc[0,'dStore'] = 0                                                     # Deficit store
    df.loc[0,'dPower'] = 0
    df.loc[0,'Pout'] = df.loc[0,'Consumption']                              
    df.loc[0,'Import'] = 0
    df.loc[0,'Export'] = 0
    df.loc[0,'Residual'] = 0
    df.loc[0,'Pnet'] = df.loc[0,'Consumption']
    for i in range(1, len(df)):                                                # Start of the hourly power balancing
        imp = 0
        exp = 0
        water = 0
        eload = 0
        flex = 0
        power_diff = 0
        def_store = 0
        must_run = df.loc[i,'Wind'] + df.loc[i,'Heat']                         # must run sources with defined power production                                                     
        load =  df.loc[i,'Consumption']

        if must_run - load  >= 0:                                              # Water balance equations
            water = wlim_low                                                          
        elif must_run - load  <= -wlim_high:
            water = wlim_high
        else:
            water = max(load - must_run,wlim_low)
            
        power_diff = must_run + water - load                                   # Power balance after water balancing

        if power_diff >= 0:                                                    # If excess power after water balancing
            def_store = min(power_diff,dStore_InCap)                           # First add to deficit store
            power_diff -= def_store                                            # New power balance
            eload = min(power_diff,elyscap)                                    # Produce H2 up to electrolyser cap limit
            power_diff -= eload                                                # New power balance
            exp = min(power_diff, expl)                                        # Export whatever is left, up to export limit            

        else:                                                                  # If power deficit after water balancing
            flex = min(-power_diff , flexmax)                                  # Decrease H2 production
            power_diff += flex                                                 # New power balance
            imp = min(-power_diff, impl)                                       # Import to cover deficit 
            power_diff += imp                                                 # New power balance
            def_store = -min(-power_diff,dStore_OutCap)                        # Extract from deficit store
            # power_diff += -def_store                                         # New power balance
        
        df.loc[i,'Water'] = water
        df.loc[i,'Import'] = imp 
        df.loc[i,'Export'] = exp
        df.loc[i,'Pout'] = must_run + water + imp - exp - def_store
        df.loc[i,'Pnet'] = must_run + water + imp
        df.loc[i,'Consumption'] += eload - flex
        df.loc[i,'eStore'] = df.loc[i-1,'eStore'] + eload + (flexmax - flex) - H2drain
        if def_store < 0:
            def_store /= rtp_eff
        df.loc[i,'dStore'] = df.loc[i-1,'dStore'] + def_store
        df.loc[i,'dPower'] = def_store

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
scale = 8.05                                                                   # Scaling factor relative wind 2020-2021
# Constant power sources
conp = 1.7                                                                     # Heat, nuclear [GW]
# Water power limit
wlim_high = 13                                                                 # Water power upper limit
wlim_low = 2                                                                   # Water power lower limit
# Import/Export limits
impl = 2.6                                                                     # 0.70 * 3.7 Import capacity from Norway
expl = 6                                                                       # Assumed export capacity
# Constant load
load = 32.25                                                                   # Constant load 
# Deficit store parameters
dStore_InCap = 0.73                                                            # Capacity in to deficit store (for example pump power in pumped hydro store)
dStore_OutCap = 6                                                              # Capacity out from deficit store (for example generator power in pumped hydro store)
rtp_eff = 0.4                                                                  # Round trip efficiency energy store
                                                                               # Params for different efficiencies:
                                                                               # dStore_inCap, dStore_OutCap, rtp,eff
                                                                                 # Hydrogen: 0,73, 6, 0.4
                                                                                 # Pumped hydro: 0.36, 6, 0.8
# H2 parameters
elyscap = 9.35                                                                 # Electrolyser capacity for peak production (flexible)
flexmax = 9.35                                                                 # Electrolyser capacity for continuos production(flexible)
total_elyscap = elyscap + flexmax                                                                 
H2high = 0                                                                     # H2 produced from peak energy
H2low = 0                                                                      # H2 produced within Conumption profile 
H2drain = 85/8.76                                                              # eStore drain rate (85 TWh / 8760 h)
# Start simulation
df = pd.read_csv('WindSE20-21.csv')                                            # Create dataframe with wind data
rename_cols(False)
normalize()
sinus('Consumption', load, 4, 0*3.14)                                          # Construct sinus shaped target load
sinus('Heat', conp, 1.5, 0*3.14)                                               # Construct sinus shaped constant power (nuclear + heat)
scalewind()                                                                    # Scale windstrengths
balance()                                                                      # Calculate balance equations

df['Residual'] = df['Pout'] - df['Consumption']                                # Diff between total available power for consumption and the actual consumption
curtail = df.loc[df['Residual'] > 0, "Residual"].sum()                         # Not used power 
shortage = - df.loc[df['Residual'] < 0, "Residual"].sum()                      # Power deficit
total_H2 = H2high + H2low

print("\n")
print("Prod power per year:        {:> 8.2f} TWh".format(df['Pnet'].sum() / 1000 / 2))
#print("Load + export per year:{:> 9.2f} TWh".format(load * 365.5 * 24 / 1000+df['Export'].sum() / 1000 / 2))
print("Load per year:             {:> 9.2f} TWh".format(df['Consumption'].sum() / 1000 / 2))
print("Produced water per year:    {:> 8.2f} TWh".format(df['Water'].sum() / 1000 / 2))
print("Produced wind per year:    {:> 9.2f} TWh".format(df['Wind'].sum() / 1000 / 2))
print("Produced nuc/heat per year: {:> 8.2f} TWh".format(df['Heat'].sum() / 1000 / 2))
print("H2 production per year:     {:> 8.2f} TWh".format((total_H2 / 1000 / 2)))
print("- From excess power:        {:> 8.2f} TWh".format((H2high / 1000 / 2)))
print("- Within consump. profile:  {:> 8.2f} TWh".format((H2low / 1000 / 2)))
print("Cap. util. electrolyzers:   {:> 8.2f} %".format((total_H2 / 1000 / 2)/(total_elyscap*8.76/100)))
print("Curtailed per year        {:> 10.2f} TWh".format(curtail / 2 / 1000))
print("Deficit per year            {:> 8.2f} TWh".format(shortage / 2 / 1000))
print("Max shortage:             {:> 10.2f} GW".format(-df['Residual'].min()))
print("Max overshot              {:> 10.2f} GW".format(df['Residual'].max()))
print("Import per year           {:> 10.2f} TWh".format(df['Import'].sum() / 2 / 1000))
print("Export per year           {:> 10.2f} TWh".format(df['Export'].sum() / 2 / 1000))

start = "2020-01-01"
stop = "2021-12-31"
df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Pout','Wind','Heat','Water','Import','Export','Consumption'], ylabel='[GW]', figsize=(15,10)) # ylim = [0,70], 
#df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Import','Export'], ylabel='[GW]', figsize=(15,10)) # ylim = [0,70], 
#df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Water'], ylabel='[GWh]',figsize=(15,10))
# df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['eStore'], ylabel='[GWh]',figsize=(15,10))
df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['dStore'], ylabel='[GWh]',figsize=(15,10))
#df.loc[(df['Date'] >= start) & (df['Date'] <= stop)].plot(x ='Date', y=['Residual'], ylabel='[GWh]',figsize=(15,10))


# Vindkraftstatistik hela landet
# https://pxexternal.energimyndigheten.se/pxweb/sv/Vindkraftsstatistik/Vindkraftsstatistik/EN0105_1.px/table/tableViewLayout2/
# Helårsstatistik
# https://www.energimyndigheten.se/nyhetsarkiv/2022/fortsatt-hog-elproduktion-och-elexport-under-2021/