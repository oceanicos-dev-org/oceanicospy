    # def txt_from_user(self):
    #     """
    #     Link an existing ``.wnd`` file from the input folder into the run folder.

    #     Returns
    #     -------
    #     dict
    #         Dictionary with key ``'windfilepath'`` set to the wind filename.
    #     """
    #     wind_file_path = glob.glob(f'{self.init.dict_folders["input"]}*.wnd')[0]
    #     wind_filename = wind_file_path.split('/')[-1]

    #     if not utils.verify_link(wind_filename, f'{self.init.dict_folders["run"]}'):
    #         utils.create_link(
    #             wind_filename,
    #             self.init.dict_folders["input"],
    #             self.init.dict_folders["run"],
    #         )

    #     self.wind_info = {"windfilepath": wind_filename}
    #     return self.wind_info
