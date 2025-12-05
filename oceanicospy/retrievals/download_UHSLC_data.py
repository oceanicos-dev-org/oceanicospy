import requests
import os

class UHSLCDownloader():
    def __init__(self,station_code,output_path):
        self.station_code = station_code
        self.output_path = output_path

    def download(self):
        # Define the base URL and the specific file you want to download
        base_url = 'https://uhslc.soest.hawaii.edu/data/csv/fast/hourly/'
        filename = f'h{self.station_code}.csv'  # Replace with the actual file name

        file_url = base_url + filename

        # Send a GET request to fetch the file
        response = requests.get(file_url)

        if response.status_code == 200:
            # Open a local file to write the content
            with open(filename, 'wb') as file:
                file.write(response.content)
            print(f"Downloaded {filename} successfully.")
        else:
            print(f"Failed to download {filename}. Status code: {response.status_code}")

        os.system(f'mv {filename} {self.output_path}')