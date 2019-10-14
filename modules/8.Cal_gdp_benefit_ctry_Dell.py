# -*- coding: utf-8 -*-

'''
This code calculates impacts of temperature changes induced by aerosols on GDP

apply the Dell et al. damage function

distribution of Dell et al. parameter was sampled (1000 times) based on the provided median and standard error

by Yixuan Zheng (yxzheng@carnegiescience.edu)
'''   

from netCDF4 import Dataset
import pandas as pd
import numpy as np
import _env
import datetime
import xarray as xr



nens  = _env.nens
datasets = _env.datasets

year = _env.year
syr = str(year)
gdp_year = year
sgdp_year = str(gdp_year)

par = 'TREFHT' 

ds = 'ERA-Interim'
p_scen = 'No-Aerosol'

if_temp = _env.odir_root + '/sim_temperature/Simulated_Global_and_Country_' + par + '_20yravg.nc'
if_ctry_list = _env.idir_root + '/regioncode/Country_List.xls'
if_ctry_pr = _env.idir_root + '/historical_stat/Ctry_Poor_Rich_from_Burke.csv' #adopt country list from Burke et al. 2018

if_ctry_gdpcap = _env.idir_root + '/historical_stat/' + '/API_NY.GDP.PCAP.KD_DS2_en_csv_v2.csv'
if_ctry_pop = _env.idir_root + '/historical_stat/' + '/API_SP.POP.TOTL_DS2_en_csv_v2.csv'

odir_gdp = _env.odir_root + '/gdp_' + ds + '/'
_env.mkdirs(odir_gdp)

#climatological temperature from three datasets
if_clim_temp = _env.odir_root + 'sim_temperature/Climatological_Temp_Ctry_3ds.csv'
itbl_clim_temp = pd.read_csv(if_clim_temp,index_col = 0)[['iso',ds]]

#country list 
itbl_ctry_info = pd.read_csv(_env.odir_root + '/basic_stats/' + 'Country_Basic_Stats.csv')

#read global and country-level temperature
T_glob = Dataset(if_temp)['TREFHT_Global'][:,[0,1]]
T_ctry_full = Dataset(if_temp)['TREFHT_Country'][:,:,[0,1]]

#extract temperature for analyzed countries
T_ctry = T_ctry_full[((itbl_ctry_info['ind_in_full_list'].astype(int)).tolist()),:,:]


T_diff = T_ctry[:,:,1]-T_ctry[:,:,0]
T_ctry[:,:,0] = np.repeat(np.array(itbl_clim_temp[ds].values)[:,np.newaxis],8,axis=1)
T_ctry[:,:,1] = T_ctry[:,:,0] + T_diff

####country-level changes in GDP/cap growth rate####

########

# the net effect of a 1◦ C rise in temperature is to decrease growth rates in poor countries by −1.394 percentage points. (Dell,Jones, and Olken, 2012) Table 2
#median = -1.394
#standard error=0.408

if_gen_pars = 0
n_boot_sample = 1000
def cal_theta(theta,se_theta):
    return np.random.normal(loc=theta,scale=se_theta,size=n_boot_sample)

if if_gen_pars:
    #generate 1000 sets of parameters for the selected damage function
    djo_pars = cal_theta(-1.394,0.408)/100
    _env.mkdirs(_env.idir_root + '/Dell_parameters/')
    xr.Dataset({'djo_pars' : xr.DataArray(djo_pars,dims = ['boots'])}).to_netcdf(_env.idir_root + '/Dell_parameters/' + '/DJO_parameters.nc')
    
else:
    djo_pars = xr.open_dataset(_env.idir_root + '/Dell_parameters/' + '/DJO_parameters.nc')['djo_pars'].values

n_ctry = len(itbl_ctry_info.index)

ifs_rich = 1-itbl_ctry_info['poor']
poor_ind = np.where(ifs_rich == 0)[0]
diff_gr = np.zeros([n_boot_sample, np.shape(T_ctry)[0],np.shape(T_ctry)[1]])

diff_gr[:,poor_ind,:] = np.einsum('i,jk->ijk',djo_pars, np.squeeze(T_ctry[poor_ind,:,1]-T_ctry[poor_ind,:,0])) #*(0.2609434-1.655145)/100 #no-aerosol minus with-aerosol

diff_gdp = np.einsum('ijk,j->ijk',diff_gr,itbl_ctry_info[str(gdp_year) + '_gdp'])

_env.rmfile(odir_gdp + 'GDP_Changes_' + 'Dell_' + str(gdp_year) +  '_' + ds + '_' + p_scen + '.nc')
onc = Dataset(odir_gdp + 'GDP_Changes_' + 'Dell_' + str(gdp_year) +  '_' + ds + '_' + p_scen + '.nc', 'w', format='NETCDF4')
    
    
d_ctry = onc.createDimension('boots',n_boot_sample)
d_ctry = onc.createDimension('countries',n_ctry)
d_ens = onc.createDimension('ensembles',nens)

v_ratio = onc.createVariable('GDP_Ratio','f4',('boots','countries','ensembles'))
v_ratio.desc = 'Impacts of aerosol-induced cooling on annual GDP growth rate'
v_ratio[:] = diff_gr

v_gdp = onc.createVariable('GDP','f4',('boots','countries','ensembles'))
v_gdp.desc = 'Impacts of aerosol-induced cooling on country-level annual GDP'
v_gdp[:] = diff_gdp    

#write global attribute
onc.by = 'Yixuan Zheng (yxzheng@carnegiescience.edu)'
onc.desc = 'Impacts of aerosol-induced cooling on annual GDP and GDP growth rate (based on damage functions by Pretis et al. 2018)'
onc.creattime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
onc.close()


####summarize global and regional GDP changes####
itbl_gdp_baseline = itbl_ctry_info.copy() 
odir_summary = _env.odir_root + 'summary_' + ds
_env.mkdirs(odir_summary)
writer = pd.ExcelWriter(odir_summary + '/country_specific_statistics_GDP_'+ds+'_'+p_scen+'_Dell.xls')
otbls_ctry_GDP_stat = {}

gdp_tot = itbl_gdp_baseline[sgdp_year + '_gdp'].sum()

spe = 'Dell'
otbl_median = pd.DataFrame(index=[spe],columns = ['median','median_ratio','5','5_ratio','95','95_ratio','10','10_ratio','90','90_ratio','prob_benefit'])

    
imtrx_gdp = diff_gdp.copy()
##global total
imtrx_gdp_glob = (imtrx_gdp).sum(axis=1)

otbl_median.loc[spe] = np.median(imtrx_gdp_glob)/1e9,np.median(imtrx_gdp_glob)/gdp_tot*100,np.percentile(imtrx_gdp_glob,95)/1e9,np.percentile(imtrx_gdp_glob,95)/gdp_tot*100,np.percentile(imtrx_gdp_glob,5)/1e9,np.percentile(imtrx_gdp_glob,5)/gdp_tot*100,    np.percentile(imtrx_gdp_glob,90)/1e9,np.percentile(imtrx_gdp_glob,90)/gdp_tot*100,np.percentile(imtrx_gdp_glob,10)/1e9,np.percentile(imtrx_gdp_glob,10)/gdp_tot*100,len(np.where(imtrx_gdp_glob<0)[0])/np.size(imtrx_gdp_glob)

otbl_ctry_GDP_stat = itbl_gdp_baseline.copy()
otbl_ctry_GDP_stat['GDP_mean_benefit'] = np.zeros(len(otbl_ctry_GDP_stat.index))
otbl_ctry_GDP_stat['GDP_median_benefit'] = np.zeros(len(otbl_ctry_GDP_stat.index))
otbl_ctry_GDP_stat['GDP_mean_benefit_ratio'] = np.zeros(len(otbl_ctry_GDP_stat.index))
otbl_ctry_GDP_stat['GDP_median_benefit_ratio'] = np.zeros(len(otbl_ctry_GDP_stat.index))
otbl_ctry_GDP_stat['GDP_90_benefit'] = np.zeros(len(otbl_ctry_GDP_stat.index))
otbl_ctry_GDP_stat['GDP_10_benefit'] = np.zeros(len(otbl_ctry_GDP_stat.index))
otbl_ctry_GDP_stat['GDP_95_benefit'] = np.zeros(len(otbl_ctry_GDP_stat.index))
otbl_ctry_GDP_stat['GDP_5_benefit'] = np.zeros(len(otbl_ctry_GDP_stat.index))    
otbl_ctry_GDP_stat['probability_damage'] = np.zeros(len(otbl_ctry_GDP_stat.index)) #add  by yz 20190719

for ictry,ctry in enumerate(itbl_ctry_info.index):
    imtrx_country = (imtrx_gdp)[:,ictry,:]
    
    otbl_ctry_GDP_stat.loc[ctry,'GDP_mean_benefit'] = -np.mean(imtrx_country)
    otbl_ctry_GDP_stat.loc[ctry,'GDP_median_benefit'] = -np.median(imtrx_country)
    otbl_ctry_GDP_stat.loc[ctry,'GDP_90_benefit'] = -np.percentile(imtrx_country,90)
    otbl_ctry_GDP_stat.loc[ctry,'GDP_10_benefit'] = -np.percentile(imtrx_country,10)
    
    otbl_ctry_GDP_stat.loc[ctry,'GDP_95_benefit'] = -np.percentile(imtrx_country,95)
    otbl_ctry_GDP_stat.loc[ctry,'GDP_5_benefit'] = -np.percentile(imtrx_country,5)
    
    otbl_ctry_GDP_stat.loc[ctry,'probability_damage'] = len(imtrx_country[imtrx_country>0])/np.size(imtrx_country)
    
otbl_ctry_GDP_stat['GDP_mean_benefit_ratio'] = otbl_ctry_GDP_stat['GDP_mean_benefit']/otbl_ctry_GDP_stat[sgdp_year+'_gdp']*100
otbl_ctry_GDP_stat['GDP_median_benefit_ratio'] = otbl_ctry_GDP_stat['GDP_median_benefit']/otbl_ctry_GDP_stat[sgdp_year+'_gdp']*100
otbl_ctry_GDP_stat.to_excel(writer,spe)
otbls_ctry_GDP_stat[spe] = otbl_ctry_GDP_stat.copy()

otbl_median = -otbl_median

otbl_median.to_excel(writer,'median_summary')
    
writer.save()


#==================changes in 90:10 and 80:20 ratio (inequality)===========================

itbl_gdp_baseline.sort_values([sgdp_year + '_gdpcap'],inplace=True)
tot_pop = itbl_gdp_baseline[sgdp_year + '_pop'].sum()

itbl_gdp_baseline[sgdp_year + '_gdpsum'] = 0
itbl_gdp_baseline[sgdp_year + '_popsum'] = 0

for irow, row in enumerate(itbl_gdp_baseline.index):
    if irow == 0:
        itbl_gdp_baseline.loc[row,sgdp_year + '_gdpsum'] = itbl_gdp_baseline.loc[row,sgdp_year + '_gdp']
        itbl_gdp_baseline.loc[row, sgdp_year + '_popsum'] = itbl_gdp_baseline.loc[row,sgdp_year + '_pop']
        
    else:
        itbl_gdp_baseline.loc[row,sgdp_year + '_gdpsum'] = itbl_gdp_baseline[sgdp_year + '_gdpsum'].iloc[irow-1] + itbl_gdp_baseline.loc[row,sgdp_year + '_gdp']
        itbl_gdp_baseline.loc[row, sgdp_year + '_popsum'] = itbl_gdp_baseline[sgdp_year + '_popsum'].iloc[irow-1] + itbl_gdp_baseline.loc[row,sgdp_year + '_pop'] 
        
itbl_gdp_baseline[sgdp_year + '_pop_ratio_sum'] = itbl_gdp_baseline[sgdp_year + '_popsum']/tot_pop

        
#deciles (<=10% and >=90%)

deciles = {}

ind10 = np.where(itbl_gdp_baseline[sgdp_year + '_pop_ratio_sum']<=0.1)[0]
deciles[10] =  itbl_gdp_baseline.iloc[ind10].copy()


ind90 = np.where(itbl_gdp_baseline[sgdp_year + '_pop_ratio_sum']>=0.9)[0]
deciles[90] = itbl_gdp_baseline.iloc[ind90].copy()


#quintiles  (<=20% and >=80%)

ind20 = np.where(itbl_gdp_baseline[sgdp_year + '_pop_ratio_sum']<=0.2)[0]
deciles[20] = itbl_gdp_baseline.iloc[ind20].copy()

ind80 = np.where(itbl_gdp_baseline[sgdp_year + '_pop_ratio_sum']>=0.8)[0]
deciles[80] = itbl_gdp_baseline.iloc[ind80].copy()

writer = pd.ExcelWriter(odir_summary + '/Deciles_and_Quintile_ratio_changes_'+ds+'_'+p_scen+'_Dell.xls')
otbls = {}
otbl_ineq = pd.DataFrame(index=[spe],columns = ['median_ratio','5_ratio','95_ratio','10_ratio','90_ratio','probability_reduced'])

otbls['deciles'] = otbl_ineq.copy()
otbls['quintiles'] = otbl_ineq.copy()

omtrx_gdp_spe = diff_gdp.copy()

dec_var = {}
dec_base = {}
for perc in [10,20,80,90]:
    dec = deciles[perc].copy()
    dec_pop_tot = dec[sgdp_year + '_pop'].sum()
    dec_gdp_tot = dec[sgdp_year + '_gdp'].sum()
    
    dec_base[perc] = dec_gdp_tot/dec_pop_tot
    
    ind_ctry = dec.index
    
    
    imtrx_dec = omtrx_gdp_spe[:,ind_ctry,:]
    imtrx_dec_sum = dec_gdp_tot-(imtrx_dec).sum(axis=1) #+ dec_gdp_tot
    
    dec_gdpcap = imtrx_dec_sum/dec_pop_tot
    
    dec_var[perc] = dec_gdpcap.copy()


dec_diff = (dec_var[90]/dec_var[10]-dec_base[90]/dec_base[10])/(dec_base[90]/dec_base[10])*100
quin_diff = (dec_var[80]/dec_var[20] - dec_base[80]/dec_base[20])/(dec_base[80]/dec_base[20])*100


otbls['deciles'].loc[spe,'median_ratio'] = np.median(dec_diff)
otbls['deciles'].loc[spe,'5_ratio'] = np.percentile(dec_diff,5)
otbls['deciles'].loc[spe,'95_ratio'] = np.percentile(dec_diff,95)

otbls['deciles'].loc[spe,'10_ratio'] = np.percentile(dec_diff,10)
otbls['deciles'].loc[spe,'90_ratio'] = np.percentile(dec_diff,90)
otbls['deciles'].loc[spe,'probability_reduced'] = len(dec_diff[dec_diff<0])/np.size(dec_diff)

otbls['quintiles'].loc[spe,'median_ratio'] = np.median(quin_diff)
otbls['quintiles'].loc[spe,'5_ratio'] = np.percentile(quin_diff,5)
otbls['quintiles'].loc[spe,'95_ratio'] = np.percentile(quin_diff,95)

otbls['quintiles'].loc[spe,'10_ratio'] = np.percentile(quin_diff,10)
otbls['quintiles'].loc[spe,'90_ratio'] = np.percentile(quin_diff,90)
otbls['quintiles'].loc[spe,'probability_reduced'] = len(quin_diff[quin_diff<0])/np.size(quin_diff)
    
otbls['deciles'].to_excel(writer,'deciles')
otbls['quintiles'].to_excel(writer,'quintiles')

writer.save()