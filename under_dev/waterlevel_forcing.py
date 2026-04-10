import glob as glob
import os

class WaterLevelForcing():

    def waterlevel_from_user(self):
        wl_file_path = glob.glob(f'{self.dict_folders["input"]}domain_0{self.domain_number}/*.wl')[0]
        wl_filename = wl_file_path.split('/')[-1]

        os.system(f'cp {self.dict_folders["input"]}domain_0{self.domain_number}/{wl_filename} \
                         {self.dict_folders["run"]}domain_0{self.domain_number}/')

        if self.dict_info is not None:
            self.dict_info.update({"water_levels.wl": wl_filename})
            return self.dict_info
