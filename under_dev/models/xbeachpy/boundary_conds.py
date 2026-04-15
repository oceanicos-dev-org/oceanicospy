#     def jonswap_from_swan(self,input_filename):
#         """
#         Get the wave parameters from SWAN.
#         Returns:
#             None
#         """
#         # Create the filelist
#         points = pd.read_csv(f'{self.dict_folders["input"]}{input_filename}.out', skiprows=7, sep='     ',
#                                 names=['Time', 'Xp', 'Yp', 'Depth', 'X-Windv','Y-Windv', 'Hsig', 'TPsmoo', 'Tm01', 'Tm02', 'Dir'],
#                          dtype={'Time': str, 'Xp': float, 'Yp': float, 'Depth': float, 'X-Windv': float, 'Y-Windv': float, 'Hsig': float, 'TPsmoo': float, 'Tm01': float, 'Tm02': float, 'Dir': float})

#         points['Time'] = pd.to_datetime(points['Time'], format='%Y%m%d.%H%M%S')

#         number_of_points = np.arange(0, 12, 1)
#         dict_data_hs = {}
#         dict_data_tp = {}
#         dict_data_dir = {}
#         for point in number_of_points:
#             hs_point_serie = points['Hsig'][point::len(number_of_points)]
#             dict_data_hs[f'punto {point+1}'] = hs_point_serie
#             tp_point_serie = points['TPsmoo'][point::len(number_of_points)]
#             dict_data_tp[f'punto {point+1}'] = tp_point_serie
#             dir_point_serie = points['Dir'][point::len(number_of_points)]
#             dict_data_dir[f'punto {point+1}'] = dir_point_serie
#             if point==1:
#                 time = points['Time'][point::len(number_of_points)]

#         for point in number_of_points:
#             dict_data_hs[f'punto {point+1}']=np.array(dict_data_hs[f'punto {point+1}'])
#             dict_data_tp[f'punto {point+1}']=np.array(dict_data_tp[f'punto {point+1}'])
#             dict_data_dir[f'punto {point+1}']=np.array(dict_data_dir[f'punto {point+1}'])
#             df_point = pd.DataFrame({'Hsig':dict_data_hs[f'punto {point+1}'],'TPsmoo':dict_data_tp[f'punto {point+1}'],'Dir':dict_data_dir[f'punto {point+1}']},index=time)
#             df_point = df_point[(df_point.index >= self.ini_date) & (df_point.index <= self.end_date)]
#             df_point['Gamma']=np.ones(len(df_point))*3.3
#             df_point['Spr']=np.ones(len(df_point))*10
#             df_point['Dur']=np.ones(len(df_point))*3600
#             df_point['random']=np.ones(len(df_point))*1

#             if point in [0,2,3,4]:
#                 df_point_numpy=df_point.to_numpy()
#                 np.savetxt(f'{self.dict_folders["run"]}jonswap_{point:03d}.txt', df_point_numpy, fmt='%6s', delimiter=' ')

#         pos={'0':[4954777.912, 2803030.289], '2':[20,0], '3':[4954535.456, 2803057.517], '4':[20,250]}

#         with open(f'{self.dict_folders["run"]}loclist.txt','w') as f:
#                 f.write('LOCLIST \n')
#                 for idx in [0,3]:
#                     # Create loclist
#                     str_point = f'{pos[str(idx)][0]} {pos[str(idx)][1]}'
#                     if idx == 3:
#                         f.write(f'{str_point} jonswap_{idx:03d}.txt')
#                     else:
#                         f.write(f'{str_point} jonswap_{idx:03d}.txt\n')
#                 f.close()
#         self.dict_boundaries={'bcfilepath':'loclist.txt'}
#         return self.dict_boundaries

#     def params_from_swan(self,input_filename):
#         points = pd.read_csv(f'{self.dict_folders["input"]}{input_filename}.out', skiprows=7, sep='     ',
#                                 names=['Time', 'Xp', 'Yp', 'Depth', 'X-Windv','Y-Windv', 'Hsig', 'TPsmoo', 'Tm01', 'Tm02', 'Dir'],
#                          dtype={'Time': str, 'Xp': float, 'Yp': float, 'Depth': float, 'X-Windv': float, 'Y-Windv': float, 'Hsig': float, 'TPsmoo': float, 'Tm01': float, 'Tm02': float, 'Dir': float})

#         points['Time'] = pd.to_datetime(points['Time'], format='%Y%m%d.%H%M%S')

#         number_of_points = np.arange(0, 12, 1)
#         dict_data_hs = {}
#         dict_data_tp = {}
#         dict_data_dir = {}
#         for point in number_of_points:
#             hs_point_serie = points['Hsig'][point::len(number_of_points)]
#             dict_data_hs[f'punto {point+1}'] = hs_point_serie
#             tp_point_serie = points['TPsmoo'][point::len(number_of_points)]
#             dict_data_tp[f'punto {point+1}'] = tp_point_serie
#             dir_point_serie = points['Dir'][point::len(number_of_points)]
#             dict_data_dir[f'punto {point+1}'] = dir_point_serie
#             if point==1:
#                 time = points['Time'][point::len(number_of_points)]

#         for point in number_of_points:
#             dict_data_hs[f'punto {point+1}']=np.array(dict_data_hs[f'punto {point+1}'])
#             dict_data_tp[f'punto {point+1}']=np.array(dict_data_tp[f'punto {point+1}'])
#             dict_data_dir[f'punto {point+1}']=np.array(dict_data_dir[f'punto {point+1}'])
#             df_point = pd.DataFrame({'Hsig':dict_data_hs[f'punto {point+1}'],'TPsmoo':dict_data_tp[f'punto {point+1}'],'Dir':dict_data_dir[f'punto {point+1}']},index=time)
#             df_point = df_point[(df_point.index >= self.ini_date) & (df_point.index < self.end_date)]
#             df_point = df_point.round(3)
#             if point == 0:
#                 self.dict_boundaries=dict(hsig_value=df_point['Hsig'].values[0],tp_value=df_point['TPsmoo'].values[0],dir_value=df_point['Dir'].values[0])
#         return self.dict_boundaries

# #