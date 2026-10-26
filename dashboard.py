import json, boto3
import streamlit as st
from google.oauth2 import service_account
from googleapiclient import discovery

def read_idrive( key_prefix="idrive",bucket="flexivue", prefix="", dtype="" ):
    idrive = boto3.client( 
        "s3",
        aws_access_key_id = st.secrets["creds"][key_prefix]["key"], 
        aws_secret_access_key = st.secrets["creds"][key_prefix]["secret"],
        endpoint_url = st.secrets["creds"][key_prefix]["endpoint"],
    )

    data = idrive.get_object( Bucket=bucket, Key="st-sites.json" )
    nested_jsons = json.loads( data['Body'].read().decode() )

    return nested_jsons

def populate_page():
    nested_jsons = read_idrive()
    page_names = []
    for key,value in nested_jsons.items():
        page_names.append( key )

    rows = []
    row_data = []
    full_rows = int( len( page_names ) / 3 )
    part_row = int( len( page_names ) % 3 )
    for i in range( full_rows ): rows.append( st.columns( 3 ) )
    if part_row != 0: rows.append( st.columns( part_row, width=225) )
    for entry in rows: row_data = row_data + entry

    index = 0
    for col in row_data:
        
        key_prefix = nested_jsons[ page_names[index] ]["key_prefix"]
        bucket = nested_jsons[ page_names[index] ]["bucket"]
        owner = nested_jsons[ page_names[index] ]["owner"]
        site = nested_jsons[ page_names[index] ]["site"]
        dtype = nested_jsons[ page_names[index] ]["dtype"]

        unit = page_names[index]
        tile = col.container(height=185, vertical_alignment="top", horizontal_alignment="center" )
        tile.page_link( "pages/telemetry.py", label=page_names[index], width="stretch", query_params=nested_jsons[page_names[index]] )
        tile.image( "img/"+owner+"-"+site+".jpeg", width="stretch")
        index += 1

@st.cache_data(ttl=600)  # Cache IAM lookups for 10 minutes to maintain speed
def check_user_iam_permission(email_to_check: str) -> bool:
    """
    Queries the GCP IAM API via a Service Account to see if the user has 
    access to the project.
    """
    try:
        # Load the service account credentials from st.secrets
        gcp_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(gcp_info)
        
        # Build the Cloud Resource Manager API service
        service = discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
        project_id = gcp_info["project_id"]
        
        # Fetch the complete IAM Policy map for the project
        policy = service.projects().getIamPolicy(resource=project_id, body={}).execute()
        bindings = policy.get('bindings', [])
        
        # Format the identity string Google IAM expects
        target_member = f"user:{email_to_check.lower()}"
        
        # Define what role grants access (e.g., any Project Viewer or higher)
        # You can change this to any specific role you want to enforce
        REQUIRED_ROLE = [
            "roles/owner",
            "roles/viewer",
            "rolex/editor",
            "roles/oauthconfig.viewer"
        ]
        
        for binding in bindings:
            if binding.get('role') in REQUIRED_ROLE:
                members = [m.lower() for m in binding.get('members', [])]
                if target_member in members:
                    return True
                    
        return False
    except Exception as e:
        st.error(f"Authorization Engine Error: Unable to query IAM system.")
        return False
    
if __name__ == "__main__":
    if not st.user.is_logged_in:
        if st.button("Log in with Google", width='stretch'):
            st.login("google")
        st.stop()

    user_email = st.user.get("email")
    if not check_user_iam_permission(user_email):
        st.error(f"⛔ Access Denied. The identity '{user_email}' does not possess the required IAM roles in Google Cloud.")
        if st.button("Log out and/or switch account"):
            st.logout()
        st.stop()

    st.set_page_config( page_title="dashboard", page_icon="⚓" )
    st.write("# FlexiVue Dashboard ⚓")

    populate_page()

    if st.button("Log out"):
        st.logout()