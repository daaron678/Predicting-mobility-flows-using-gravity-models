import pandas as pd
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
import os
from dotenv import load_dotenv
from io import BytesIO

def authorize():
    load_dotenv()
    APP_KEY = os.environ.get("DROPBOX_APP_KEY")
    APP_SECRET = os.environ.get("DROPBOX_APP_SECRET")

    auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY,
                                            use_pkce = True,
                                            consumer_secret=APP_SECRET,
                                            token_access_type='offline',
                                            scope=['files.metadata.read', 'files.content.read'])

    authorize_url = auth_flow.start()
    print("1. Go to: " + authorize_url)
    print("2. Click \"Allow\" (you might have to log in first).")
    print("3. Copy the authorization code.")
    auth_code = input("Enter the authorization code here: ").strip()

    try:
        oauth_result = auth_flow.finish(auth_code)
        assert oauth_result.scope == 'files.metadata.read'
    except Exception as e:
        print('Error: %s' % (e,))
        exit(1)
        
    dbx = dropbox.Dropbox(oauth2_access_token=oauth_result.access_token,
                     oauth2_access_token_expiration=oauth_result.expires_at,
                     oauth2_refresh_token=oauth_result.refresh_token,
                     app_key=APP_KEY,
                     app_secret=APP_SECRET)
    print("Successfully set up client!")
    return dbx

def load_data(dbx: dropbox.Dropbox, data_folder_path:str) -> tuple:
    """
    Returns:
        A tuple containing:
        - A dictionary with keys being each state code and values being the original datasets for that state with columns
        "Otract", "Dtract", "EST"
        - Ditto, but the dataset contains the columns "Id", "Jobs", "Pop" 
    """
    datasets = {}
    data_folder = dbx.files_list_folder(data_folder_path)
    for file in data_folder.entries:
        # file.name.split("_") creates list of items split from the filename -> [-1] access last item -> .split(".") splits last item by "."-> [0] accesses the first item which is the state code
        state_code = file.name.split("_")[-1].split(".")[0]
        file_path = os.path.join(data_folder_path, file.name)
        metaData, data = dbx.files_download(file_path)
        df = pd.read_csv(BytesIO(data.content))
        # Add the DataFrame to the container with the state code as the label
        datasets[state_code] = df
    dbx.close()

    dsets_grouped = {}
    for state_code, df in datasets.items():
        grouped = pd.DataFrame()
        # no_jobs is a datafram of tracts that have a resident population, but don't provide any jobs for commuting workers from other census tracts
        no_jobs = pd.DataFrame(set(df['Otract'].unique()) - set(df['Dtract'].unique()), columns = ['Id'])
        # no_pop is a data frame of tracts that provide jobs,  but do not have any resident population
        no_pop = pd.DataFrame(set(df['Dtract'].unique()) - set(df['Otract'].unique()), columns = ['Id'])
        
        grouped = pd.DataFrame(set(df['Otract'].unique()).union(set(df['Dtract'].unique())), 
                        columns = ["Id"])
        jobs = df.groupby('Dtract')['EST'].sum()
        grouped['Jobs'] = grouped['Id'].map(jobs)
        grouped['Jobs'] = grouped['Jobs'].fillna(0).astype(int)
        pop = df.groupby('Otract')['EST'].sum()
        grouped['Pop'] = grouped['Id'].map(pop)
        grouped['Pop'] = grouped['Pop'].fillna(0).astype(int)
        dsets_grouped[state_code] = grouped
    assert not dsets_grouped['FL'].isna().values.any() and not datasets['FL'].isna().values.any()
    return datasets, dsets_grouped



