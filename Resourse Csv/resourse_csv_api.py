######################################
# Steps to Run the Script
# 1 - Update base_url to your organization url in line # 15
# 3 - Update token for your api token in line # 16
# 4 - Update file_path of file which you want to upload a resources file in line # 17
# 5 - Values for preferred access status are (Public, Private, Restricted)

from time import asctime
import csv
import requests

base_url = 'https://weareavp.aviaryplatform.com/'
token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
file_path = '/Users/weareavp/aviary-api-scripts/resources.csv'

def update_to_aviary(row):

    headers = {
        'Authorization': f'Bearer {token}',
        "Content-Type": "application/x-www-form-urlencoded"

    }
    print(f"Resource id --{row['resource_id']}")
    url = f"{base_url}api/v1/resources/{row['resource_id']}"
    data = {
        "access": row['preferred_access'].lower(),
    }
    r = requests.put(url, headers=headers, data=data)
    if r.status_code == 200:
        response = r.json()
        return response
    return False


def main():
    csv_file = open(file_path, 'rt', encoding='utf-8')
    csv_reader = csv.DictReader(csv_file)
    
    for row in csv_reader:
        update_to_aviary(row)
    csv_file.close()

if __name__ == '__main__':
    main()